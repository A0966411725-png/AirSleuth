"""E4 Agent 端到端評估：40 題、4 種做法（OpenSpec 變更 add-evaluation-suite）。

題目：experiments/e4_questions.json
- 24 題可回答（6 個真實時間點：高雄 10/23 區域型、臺中 10/19 沿海次區域型、10/21、臺中 10/29 測站尖峰、
  臺中 11/14 區域升高、高雄 11/17 局部型）
- 6 題該追問地點、5 題該拒答（其他縣市、與空品無關）、5 題領域知識

做法：
- (a) 只看 AQI：最近國家測站的最新小時值 → 新版 AQI（敏感族群提前一級）→ 環境部建議。只評可回答的 24 題。
- (b) 純 LLM：同一個 Gemini 模型，沒有任何工具。
- (c) LLM＋原始資料工具：可以查原始感測器中位數、測站、氣象、測站預測，但沒有品質檢查、校正、來源判斷與領域知識。
- (d) AirSleuth：src/agent/planner.py 的完整系統。

標準答案（只有可回答題）：確定性流程（Algorithm 1～3）在同一時間、地點、族群、活動下的第一順位建議與來源型態。
這套規則依環境部 2025 年 AQI 活動建議（S-032）與文獻設計，所以「建議一致率」衡量的是是否遵守官方指引與空間邏輯，
不是使用者的實際健康結果。

指標：
- 數字可追溯率：帶單位的數字能在資料中找到的比例。(b) 沒有工具，改和同一時間地點的真實資料比對。
- 建議一致率：第一順位建議的類別（照常、降低強度、改時段、換地點、改室內）與標準答案相同。類別用關鍵字判斷。
- 空間錯誤：區域型事件卻建議換地點。
- 追問、拒答、領域知識的正確率。

LLM 的回應會快取在 experiments/results/e4_cache/，中斷後重跑會接續；免費額度用完時隔天再跑。

用法（從專案根目錄，需要 GEMINI_API_KEY 與本機 data/raw）：
    .venv\\Scripts\\python -m experiments.e4_agent
"""

from __future__ import annotations

import json
import re
import time as clock

import numpy as np
import pandas as pd

from experiments.common import BLUE, GREY, INK, ORANGE, RESULTS, plt, save_table
from src.agent import geo, tools
from src.agent.llm import GeminiClient, LLMUnavailable
from src.agent.pipeline import Query, run
from src.agent.planner import NUMBER_WITH_UNIT, Planner, _json_safe, _text_of, unsupported_numbers
from src.knowledge import health

MODEL = "gemini-3.5-flash-lite"
MIN_INTERVAL = 4.5            # 秒；免費額度每分鐘次數有限
CACHE = RESULTS / "e4_cache"
QUESTIONS = json.loads((RESULTS.parent / "e4_questions.json").read_text(encoding="utf-8"))
CONFIGS = {"a": "只看 AQI", "b": "純 LLM", "c": "LLM＋原始資料工具", "d": "AirSleuth"}

SYSTEM_B = "你是空氣品質助理。現在時間是 {time}（台灣時間）。請用繁體中文回答使用者的問題，並給出具體建議。"
SYSTEM_C = """你是空氣品質助理。現在時間是 {time}（台灣時間）。你可以用工具查詢臺中市、高雄市的空品資料。
先用 resolve_place 確認地點，再用 get_air_data 取得資料；地點不明確就問使用者。數字要引用工具結果。
請用繁體中文回答，包含結論、原因與具體建議。"""
TOOLS_C = [
    {"name": "resolve_place", "description": "把地點文字轉成縣市與座標（只支援臺中市、高雄市）",
     "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}},
    {"name": "get_air_data", "description": "取得地點附近的空品資料：2 km 內微型感測器的原始讀數中位數、最近國家測站最新小時值、"
                                            "最近氣象站、測站未來 1/3/6 小時預測",
     "parameters": {"type": "OBJECT", "properties": {"city": {"type": "STRING"}, "lat": {"type": "NUMBER"},
                                                    "lon": {"type": "NUMBER"}}, "required": ["city", "lat", "lon"]}},
]
ACTION_WORDS = [  # 依出現位置最早者判定第一順位建議的類別
    ("shift_place", ["換到", "換個地點", "換地點", "其他地區", "別的地方", "別區", "移動到", "8 km", "8 公里", "8公里", "其他區"]),
    ("shift_time", ["延後", "晚一點", "稍後再", "等到", "改天", "傍晚再", "晚上再", "明天再", "小時後再", "改時段", "避開"]),
    ("move_indoor", ["室內", "待在家", "留在家", "關閉門窗", "關窗", "在家運動", "健身房"]),
    ("lower_intensity", ["降低強度", "降低運動強度", "輕度", "緩和", "伸展", "改成散步", "縮短", "減少戶外", "減少時間",
                         "不要太激烈", "放慢", "強度"]),
    ("as_planned", ["照原計畫", "照常", "可以正常", "放心", "適合", "可以去", "可以出門", "沒問題", "可以進行", "可以帶"]),
]
NEGATIONS = ["不適合", "不建議", "不太適合", "不宜", "避免", "不要"]


class ThrottledClient(GeminiClient):
    """固定模型、每次呼叫間隔至少 MIN_INTERVAL 秒，並計算呼叫次數。"""

    def __init__(self):
        super().__init__(models=[MODEL], timeout=60)
        self.calls, self._last = 0, 0.0

    def generate(self, contents, system=None, tools=None):
        wait = MIN_INTERVAL - (clock.time() - self._last)
        if wait > 0:
            clock.sleep(wait)
        self._last = clock.time()
        self.calls += 1
        return super().generate(contents, system, tools)


def place_of(q: dict) -> dict:
    row = geo.DISTRICTS[(geo.DISTRICTS["city"] == q["city"]) & (geo.DISTRICTS["district"] == q["district"])].iloc[0]
    return {"city": q["city"], "lat": float(row["lat"]), "lon": float(row["lon"]), "place": f"{q['city']}{q['district']}"}


def gold(q: dict) -> dict:
    p = place_of(q)
    a = run(Query(p["city"], p["lat"], p["lon"], q["time"], q["group"], q["activity"], q["hours"], p["place"]))
    return {"key": a.facts["action_keys"][0], "type": a.facts["source_type"], "trace": _json_safe(a.trace),
            "facts": _json_safe(a.facts)}


# ---- 四種做法 ------------------------------------------------------------------------------------------------
def run_a(q: dict) -> dict:
    p = place_of(q)
    st = tools.get_station(p["city"], q["time"], p["lat"], p["lon"])
    level = health.personal_level(st["pm25"], q["group"])
    key = "as_planned" if level <= 1 else ("lower_intensity" if level == 2 and q["activity"] == "exercise"
                                           else "as_planned" if level == 2 else "move_indoor")
    text = (f"最近測站「{st['sitename']}」{st['time'][11:16]} 為 {st['pm25']:.0f} μg/m³（新版 AQI「{health.AQI_NAMES[health.aqi_level(st['pm25'])]}」）。"
            f"建議：{ {'as_planned': '照常活動', 'lower_intensity': '降低強度', 'move_indoor': '改到室內'}[key] }")
    return {"text": text, "key": key, "trace": [{"tool": "get_station", "result": _json_safe(st)}], "calls": 0}


def raw_air_data(city: str, lat: float, lon: float, time: str) -> dict:
    micro = tools.get_microsensors(city, time, lat, lon, 2.0)
    df = micro["data"]
    out = {}
    if not df.empty:
        latest = df.sort_values("time").groupby("station_id").tail(1)
        latest = latest[latest["time"] >= latest["time"].max() - pd.Timedelta(minutes=10)]
        out["微型感測器_2km_原始中位數"] = round(float(latest["pm25"].median()), 1)
        out["微型感測器數"] = int(latest["station_id"].nunique())
    st, w, fc = (tools.get_station(city, time, lat, lon), tools.get_weather(city, time, lat, lon),
                 tools.forecast_trend(city, time, lat, lon))
    if st.get("ok"):
        out["國家測站"] = {k: st[k] for k in ("sitename", "distance_km", "time", "pm25")}
    if w.get("ok"):
        out["氣象站"] = {k: w[k] for k in ("station_name", "wind_dir", "wind_speed", "rh")}
    if fc.get("ok"):
        out["測站預測"] = fc["forecast"]
    return _json_safe(out)


def llm_loop(client: ThrottledClient, system: str, tool_decls: list, executor, question: str) -> dict:
    contents, trace = [{"role": "user", "parts": [{"text": question}]}], []
    for _ in range(8):
        content, model = client.generate(contents, system, tool_decls)
        contents.append(content)
        calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
        if not calls:
            return {"text": _text_of(content), "trace": trace, "model": model}
        parts = []
        for c in calls:
            result = executor(c["name"], c.get("args", {}))
            trace.append({"tool": c["name"], "args": c.get("args", {}), "result": result})
            parts.append({"functionResponse": {"name": c["name"], "id": c.get("id"), "response": result}})
        contents.append({"role": "user", "parts": parts})
    return {"text": "（超過工具呼叫上限）", "trace": trace, "model": model}


def run_b(q: dict, client: ThrottledClient) -> dict:
    before = client.calls
    content, model = client.generate([{"role": "user", "parts": [{"text": q["question"]}]}], SYSTEM_B.format(time=q["time"]))
    return {"text": _text_of(content), "trace": [], "model": model, "calls": client.calls - before}


def run_c(q: dict, client: ThrottledClient) -> dict:
    before = client.calls

    def execute(name, args):
        if name == "resolve_place":
            return geo.resolve_place(str(args.get("text", "")))
        if name == "get_air_data" and args.get("city") in geo.SUPPORTED:
            return raw_air_data(args["city"], float(args["lat"]), float(args["lon"]), q["time"])
        return {"ok": False, "error": "不支援"}

    out = llm_loop(client, SYSTEM_C.format(time=q["time"]), TOOLS_C, execute, q["question"])
    return {**out, "calls": client.calls - before}


def run_d(q: dict, client: ThrottledClient) -> dict:
    before = client.calls
    r = Planner(client).ask(q["question"], time=q["time"])
    return {"text": r.text, "kind": r.kind, "trace": r.trace, "model": r.model, "notes": r.notes,
            "facts_key": (r.facts or {}).get("action_keys", [None])[0], "calls": client.calls - before}


# ---- 評分 ----------------------------------------------------------------------------------------------------
def recommendation_part(text: str) -> str:
    m = re.search(r"建議[^\n]{0,6}\n?(.*?)(\n\*\*|\Z)", text, re.S)
    return m.group(1) if m and m.group(1).strip() else text


def classify_action(text: str) -> str:
    part = recommendation_part(text)
    for neg in NEGATIONS:
        part = part.replace(neg, "＃" * len(neg))
    best, pos = "unknown", len(part) + 1
    for key, words in ACTION_WORDS:
        for w in words:
            i = part.find(w)
            if 0 <= i < pos:
                best, pos = key, i
    return best


def mentions_shift_place(text: str) -> bool:
    part = recommendation_part(text)
    for neg in NEGATIONS:
        part = part.replace(neg, "＃" * len(neg))
    return any(w in part for w in ACTION_WORDS[0][1])


ASKS = re.compile(r"哪一?區|哪裡|在哪|哪個地方|什麼地方|請(告訴|提供|問)|您的位置|所在")
DECLINES = re.compile(r"不支援|無法|只支援|僅支援|不在.{0,6}範圍|只能回答|僅能|沒有.{0,6}資料|不提供|專注|範圍外|僅限")


def score(q: dict, cfg: str, out: dict, g: dict | None) -> dict:
    text = out["text"]
    numbers = NUMBER_WITH_UNIT.findall(text)
    row = {"id": q["id"], "type": q["type"], "config": CONFIGS[cfg], "n_numbers": len(numbers),
           "calls": out.get("calls", 0), "seconds": out.get("seconds", 0.0)}
    if q["type"] == "answer":
        ref = out["trace"] if cfg in "acd" else g["trace"]
        bad = unsupported_numbers(text, ref)
        key = out.get("key") or classify_action(text)
        row.update(untraceable=len(bad), any_untraceable=len(bad) > 0, action=key, gold=g["key"], gold_type=g["type"],
                   agree=key == g["key"], spatial_error=g["type"] == "regional" and mentions_shift_place(text),
                   missed_shift_place=g["key"] == "shift_place" and not mentions_shift_place(text))
    elif q["type"] == "clarify":
        row["correct"] = bool(ASKS.search(text)) and not re.search(r"μg/m³|µg/m³", text)
    elif q["type"] == "refuse":
        row["correct"] = bool(DECLINES.search(text)) and not re.search(r"\d+(\.\d+)?\s*(μg/m³|µg/m³)", text)
    else:
        row["correct"] = all(re.search(k, text) for k in q["keywords"])
    return row


def main() -> None:
    client = ThrottledClient()
    if not client.available:
        raise SystemExit("需要 GEMINI_API_KEY")
    rows, golds = [], {}
    for q in QUESTIONS:
        g = gold(q) if q["type"] == "answer" else None
        golds[q["id"]] = g
        for cfg in CONFIGS:
            if cfg == "a" and q["type"] != "answer":
                continue
            path = CACHE / cfg / f"{q['id']}.json"
            if path.exists():
                out = json.loads(path.read_text(encoding="utf-8"))
            else:
                start = clock.time()
                try:
                    out = {"a": lambda: run_a(q), "b": lambda: run_b(q, client), "c": lambda: run_c(q, client),
                           "d": lambda: run_d(q, client)}[cfg]()
                except LLMUnavailable as exc:
                    print(f"LLM 無法使用（{exc}），已完成的結果都在快取，稍後重跑會接續")
                    return
                out["seconds"] = round(clock.time() - start, 1)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(_json_safe(out), ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"{q['id']} {CONFIGS[cfg]}：{out.get('seconds')} 秒", flush=True)
            rows.append(score(q, cfg, out, g))
    res = pd.DataFrame(rows)
    save_table(res, "e4_scores.csv")
    summarize(res)


def summarize(res: pd.DataFrame) -> None:
    out = []
    for name in CONFIGS.values():
        d = res[res["config"] == name]
        a = d[d["type"] == "answer"]
        num = a["n_numbers"].sum()
        out.append({"做法": name,
                    "數字可追溯率": 1 - a["untraceable"].sum() / num if num else np.nan,
                    "含無法追溯數字的回答": a["any_untraceable"].mean(),
                    "建議一致率": a["agree"].mean(),
                    "區域型卻建議換地點": int(a["spatial_error"].sum()),
                    "局部／次區域型沒建議換地點": int(a["missed_shift_place"].sum()),
                    "追問正確率": d[d["type"] == "clarify"]["correct"].mean(),
                    "拒答正確率": d[d["type"] == "refuse"]["correct"].mean(),
                    "領域知識正確率": d[d["type"] == "knowledge"]["correct"].mean(),
                    "平均 LLM 呼叫次數": d["calls"].mean(), "平均秒數": d["seconds"].mean()})
    summary = pd.DataFrame(out)
    save_table(summary.round(3), "e4_summary.csv")
    print(summary.round(3).to_string(index=False))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    cols = ["數字可追溯率", "建議一致率", "追問正確率", "拒答正確率"]
    width = 0.2
    for i, (name, c) in enumerate(zip(CONFIGS.values(), [GREY, INK, BLUE, ORANGE])):
        vals = summary.set_index("做法").loc[name, cols].to_numpy(dtype=float)
        bars = ax.bar(np.arange(len(cols)) + (i - 1.5) * width, np.nan_to_num(vals), width, label=name, color=c)
        ax.bar_label(bars, labels=["—" if np.isnan(v) else f"{v:.0%}" for v in vals], fontsize=7, padding=2)
    ax.set_xticks(range(len(cols)), cols)
    ax.set_ylim(0, 1.15)
    ax.set_title(f"E4：40 題 Agent 評估（{MODEL}）", loc="left", fontsize=12)
    ax.legend(frameon=False, ncols=4, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8.5)
    fig.tight_layout()
    fig.savefig(RESULTS / "e4_agent.png", dpi=180)


if __name__ == "__main__":
    main()
