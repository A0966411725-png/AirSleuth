"""AirSleuth 空品偵探 demo 網站（OpenSpec 變更 add-demo-site）。

本機執行（從專案根目錄）：
    streamlit run app/streamlit_app.py

資料：預設讀 data/sample/demo/（由 scripts/make_demo_sample.py 產生的真實事件樣本），公開部署不需要 data/raw/。
LLM：有 GEMINI_API_KEY（.env 或 Streamlit Secrets）就用 Gemini 規劃；沒有就用確定性流程，網站一樣能用。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402

from src.agent import tools  # noqa: E402
from src.agent.llm import GeminiClient, configured_models  # noqa: E402
from src.agent.pipeline import TYPE_NAMES, Query, run  # noqa: E402
from src.agent.planner import Planner  # noqa: E402
from src.knowledge import health  # noqa: E402

SAMPLE = ROOT / "data" / "sample" / "demo"
EVENTS = json.loads((SAMPLE / "events.json").read_text(encoding="utf-8"))
GITHUB = "https://github.com/A0966411725-png/AirSleuth"
# 新版 AQI（2025）PM2.5 分級顏色：良好、普通、對敏感族群不健康、對所有族群不健康、非常不健康、危害
AQI_COLORS = [(0, 153, 102), (255, 222, 51), (255, 153, 51), (204, 0, 51), (102, 0, 153), (126, 0, 35)]
EXAMPLES = ["我在高雄前金區，現在可以帶小孩去公園跑步嗎？", "我住台中龍井，等一下想去散步一小時，我有氣喘",
            "現在適合出去跑步嗎？", "台北信義區空氣好嗎？"]

st.set_page_config(page_title="AirSleuth 空品偵探", page_icon="🔎", layout="wide")


def secret_key() -> None:
    """Streamlit Cloud 的 Secrets 也放進環境變數，讓 src/agent/llm.py 用同一種方式讀取。"""
    try:
        if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = str(st.secrets["GEMINI_API_KEY"])
    except FileNotFoundError:
        pass


@st.cache_data(show_spinner=False)
def replay(city: str, lat: float, lon: float, time: str, group: str, activity: str, root: str, place: str) -> dict:
    a = run(Query(city, lat, lon, time, group=group, activity=activity, place=place), root=Path(root))
    return {"text": a.to_text(), "facts": a.facts, "trace": a.trace}


@st.cache_data(show_spinner=False)
def sensors_at(city: str, lat: float, lon: float, time: str, root: str) -> pd.DataFrame:
    micro = tools.get_microsensors(city, time, lat, lon, 15, root=Path(root))
    df = micro["data"]
    if df.empty:
        return df
    latest = df.sort_values("time").groupby("station_id").tail(1)
    latest = latest[latest["time"] >= latest["time"].max() - pd.Timedelta(minutes=10)].dropna(subset=["pm25"])
    level = latest["pm25"].apply(health.aqi_level)
    latest = latest.assign(r=[AQI_COLORS[i][0] for i in level], g=[AQI_COLORS[i][1] for i in level],
                           b=[AQI_COLORS[i][2] for i in level], aqi=[health.AQI_NAMES[i] for i in level])
    return latest[["station_id", "lat", "lon", "pm25", "aqi", "r", "g", "b"]]


def sensor_map(points: pd.DataFrame, lat: float, lon: float) -> None:
    rings = pd.DataFrame({"lat": [lat] * 3, "lon": [lon] * 3, "radius": [2000, 8000, 15000]})
    layers = [
        pdk.Layer("ScatterplotLayer", rings, get_position="[lon, lat]", get_radius="radius", filled=False,
                  stroked=True, get_line_color=[20, 33, 61, 160], line_width_min_pixels=1),
        pdk.Layer("ScatterplotLayer", points, get_position="[lon, lat]", get_fill_color="[r, g, b, 200]",
                  get_radius=180, pickable=True),
        pdk.Layer("ScatterplotLayer", pd.DataFrame({"lat": [lat], "lon": [lon]}), get_position="[lon, lat]",
                  get_fill_color=[20, 33, 61, 255], get_radius=450),
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=10.2),
                             tooltip={"text": "PM2.5 {pm25} μg/m³（{aqi}）"}, map_style="light"),
                    use_container_width=True)
    st.caption("圓圈：查詢點周圍 2 km、8 km、15 km。點的顏色是新版 AQI 等級（綠：良好、黃：普通、橘：對敏感族群不健康、紅：不健康）。")


def show_trace(trace: list[dict]) -> None:
    for step in trace:
        if "tool" not in step:
            continue
        result = {k: v for k, v in (step.get("result") or {}).items() if k not in ("reference_answer",)}
        with st.container(border=True):
            st.markdown(f"**{step.get('step', '')}. `{step['tool']}`**　參數：`{json.dumps(step.get('args', {}), ensure_ascii=False)}`")
            st.json(result, expanded=False)


def page_ask(root: Path, client: GeminiClient) -> None:
    st.header("💬 問 AirSleuth")
    labels = {f"{e['time']}　{e['title']}": e for e in EVENTS}
    choice = st.selectbox("查詢時間（重播已收集的真實資料）", list(labels), index=0)
    time = labels[choice]["time"]
    st.caption("民生公共物聯網的憑證在 2026-11-21 過期，微型感測器暫時無法即時取得，所以 demo 以真實事件的時間點重播。"
               "在這個時間點，臺中市與高雄市的資料都能查。")
    if "history" not in st.session_state or st.session_state.get("time") != time:
        st.session_state.update(history=[], messages=[], time=time)
    cols = st.columns(len(EXAMPLES))
    clicked = next((q for c, q in zip(cols, EXAMPLES) if c.button(q, use_container_width=True)), None)
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("trace"):
                with st.expander(f"工具呼叫紀錄（{len([s for s in m['trace'] if 'tool' in s])} 次）"):
                    show_trace(m["trace"])
            if m.get("meta"):
                st.caption(m["meta"])
    question = st.chat_input("例如：我在臺中西屯區，想帶爸媽去散步，可以嗎？") or clicked
    if not question:
        return
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("查資料、分析中…"):
            result = Planner(client, root=root).ask(question, time=time, history=st.session_state.history)
        st.session_state.history = result.history
        meta = f"{'LLM：' + result.model if result.model else 'LLM 未使用'}｜類型：{result.kind}｜查詢時間：{time}"
        st.markdown(result.text)
        if result.trace:
            with st.expander(f"工具呼叫紀錄（{len([s for s in result.trace if 'tool' in s])} 次）"):
                show_trace(result.trace)
        st.caption(meta)
    st.session_state.messages.append({"role": "assistant", "content": result.text, "trace": result.trace, "meta": meta})


def page_replay(root: Path) -> None:
    st.header("🗺️ 真實事件重播")
    event = st.selectbox("選擇事件", EVENTS, format_func=lambda e: f"{e['title']}（{e['time']}）")
    c1, c2 = st.columns(2)
    group = c1.radio("使用者", list(health.GROUP_NAMES), format_func=health.GROUP_NAMES.get, horizontal=True, index=1)
    activity = c2.radio("活動", list(health.ACTIVITY_NAMES), format_func=health.ACTIVITY_NAMES.get, horizontal=True, index=2)
    st.info(event["story"])
    with st.spinner("重播中…"):
        res = replay(event["city"], event["lat"], event["lon"], event["time"], group, activity, str(root), event["place"])
        points = sensors_at(event["city"], event["lat"], event["lon"], event["time"], str(root))
    f = res["facts"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前 PM2.5（校正後）", f"{f['pm25_now']} μg/m³")
    m2.metric("新版 AQI", f["aqi_category"].replace("對敏感族群", "敏感族群").replace("對所有族群", "所有族群"))
    m3.metric("來源型態", TYPE_NAMES[f["source_type"]].split("（")[0])
    m4.metric("信心", f["confidence"])
    left, right = st.columns([3, 2])
    with left:
        sensor_map(points, event["lat"], event["lon"])
    with right:
        ind = f["indicators"]
        st.markdown("**空間指標（Algorithm 2）**")
        st.dataframe(pd.DataFrame([
            ("B 區域背景（15 km 中位數）", ind["B"], "μg/m³"), ("L 局部濃度（中位數）", ind["L"], "μg/m³"),
            ("E = L − B 局部超量", ind["E"], "μg/m³"), ("C 空間一致性（升高比例）", ind["C"], ""),
            ("C_sub 8 km 內升高比例", ind["C_sub"], ""), ("C_ring 8～15 km 外環", ind["C_ring"], ""),
            ("局部範圍可信感測器", ind["n_local"], "個")], columns=["指標", "數值", "單位"]),
            hide_index=True, use_container_width=True)
        st.markdown("**不同族群拿到的第一順位建議**")
        rows = []
        for g in health.GROUP_NAMES:
            other = replay(event["city"], event["lat"], event["lon"], event["time"], g, activity, str(root), event["place"])["facts"]
            rows.append((health.GROUP_NAMES[g], other["personal_level"], other["top_action"]))
        st.dataframe(pd.DataFrame(rows, columns=["族群", "個人風險等級", "第一順位建議"]), hide_index=True,
                     use_container_width=True)
    st.subheader("AirSleuth 的回答")
    st.markdown(res["text"])
    with st.expander("工具呼叫紀錄"):
        show_trace(res["trace"])


def page_about() -> None:
    st.header("📊 資料與方法")
    st.markdown(f"""
**AirSleuth 空品偵探**是一個空氣品質的 Domain AI Agent：LLM 負責理解問題、規劃查詢與解釋，
所有數字與判斷都由確定性的程式產生，並記錄每一次工具呼叫。原始碼、規格（OpenSpec）與文件：[{GITHUB}]({GITHUB})

| 資料 | 內容 | 本 demo 使用 |
|---|---|---|
| 民生公共物聯網 SensorThings API | 環境部智慧城鄉空品微型感測器，約每 5 分鐘 | 事件前 7 小時，臺中 1,191 個、高雄 1,369 個感測器 |
| 環境部環境資料開放平臺 | 國家空品測站小時值 | 臺中 6 站、高雄 12 站，事件前 60 天 |
| 中央氣象署開放資料平臺 | 自動氣象站風向、風速、濕度 | 事件當天 |

**核心方法**
1. **品質檢查**：缺值、負值、極端值、卡住、濕度無效。
2. **來源判斷（Algorithm 2）**：區域背景 B、局部超量 E、空間一致性 C，把升高分成區域型、次區域型、局部型、混合型或疑似感測器異常。
3. **在地校正**：依縣市與氣象站濕度校正微型感測器讀數。
4. **短期預測**：國家測站 1／3／6 小時預測。
5. **個人化建議（Algorithm 3）**：敏感族群提前一級；只有局部或次區域事件才建議換地點；依效益減暴露風險排序。

**限制**：微型感測器 API 的憑證在 2026-11-21 過期，所以 demo 使用已收集的真實事件重播；判斷門檻來自臺中、高雄的資料，
套用到其他縣市前需要重新校準；建議僅供參考，不取代醫療專業意見。
""")
    st.image(str(ROOT / "diagrams" / "architecture_overview.png"), caption="系統架構（①～⑧ 模組）")


def main() -> None:
    secret_key()
    client = GeminiClient()
    raw_available = (ROOT / "data" / "raw" / "colife").exists()
    with st.sidebar:
        st.title("🔎 AirSleuth")
        st.caption("結合 IoT 微型感測器與領域知識的空氣品質 Domain AI Agent")
        page = st.radio("頁面", ["💬 問 AirSleuth", "🗺️ 真實事件重播", "📊 資料與方法"])
        st.divider()
        if client.available:
            st.success(f"Gemini 已啟用\n\n模型順序：{'、'.join(configured_models())}")
        else:
            st.warning("沒有設定 GEMINI_API_KEY：使用確定性流程回答（LLM 未啟用）")
        use_raw = st.toggle("使用本機完整資料", value=False, disabled=not raw_available,
                            help="只有在本機有 data/raw/ 時可用；公開網站使用事件樣本")
        st.caption(f"[GitHub]({GITHUB})")
    root = tools.DATA_ROOT if use_raw else SAMPLE
    if page.startswith("💬"):
        page_ask(root, client)
    elif page.startswith("🗺️"):
        page_replay(root)
    else:
        page_about()


main()
