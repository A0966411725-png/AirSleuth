"""AirSleuth 主流程（Algorithm 1）的確定性版本：依序呼叫工具，產生四段式回答與追溯紀錄。

Proposal 階段先用固定的規劃流程代替 LLM Planner（架構模組 ③），驗證「工具 → 判斷 → 建議」整條路可行；
期末把 `run()` 裡的固定順序換成 LLM 依 `schema.TOOLS` 自行規劃呼叫，工具與輸出格式不變。

用法：見 `src/agent/demo.py`。
輸入：Query（縣市、經緯度、時間、族群、活動、停留時數）。
輸出：Answer（結論、原因與證據、建議、信心程度、資料來源）與每一步工具呼叫的紀錄。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.agent import tools
from src.knowledge import health

N_MIN = 5            # Algorithm 1 第 10 行：局部範圍內至少要有的可信感測器數
TYPE_NAMES = {
    "regional": "區域型（整個區域一起升高）", "subregional": "次區域型（約 8 km 內的群聚升高）",
    "local": "局部型（附近有污染來源）", "mixed": "混合型（區域升高加上局部來源）",
    "suspected_sensor_fault": "疑似單一感測器異常", "no_clear_event": "沒有明顯的污染事件",
    "insufficient_data": "資料不足，無法判斷",
}


@dataclass
class Query:
    city: str
    lat: float
    lon: float
    time: str
    group: str = "general"
    activity: str = "exercise"
    hours: float = 1.0
    place: str = "目標地點"


@dataclass
class Answer:
    conclusion: str
    reasons: list[str]
    actions: list[str]
    confidence: str
    confidence_reasons: list[str]
    sources: list[str]
    trace: list[dict] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [f"**結論：**{self.conclusion}", "", "**為什麼：**"] + [f"- {r}" for r in self.reasons]
        lines += ["", "**建議：**"] + [f"{i}. {a}" for i, a in enumerate(self.actions, 1)]
        lines += ["", f"**信心：{self.confidence}。**" + "；".join(self.confidence_reasons)]
        lines += ["", "**資料來源：**" + "；".join(self.sources)]
        return "\n".join(lines)


def _log(trace: list, tool: str, args: dict, result: dict) -> dict:
    trace.append({"step": len(trace) + 1, "tool": tool, "args": args,
                  "result": {k: v for k, v in result.items() if k != "data"}})
    return result


def _confidence(n_local: int, r_local: float, rh: float | None, src_type: str, stale: float | None,
                calibrated: bool) -> tuple[str, list]:
    """Algorithm 1 第 19 行、Algorithm 3 第 10 行：依可信感測器數、濕度、來源判斷與資料新舊決定信心。"""
    score, why = 2, [f"{r_local:g} km 內可信感測器 {n_local} 個"]
    if n_local < N_MIN:
        score -= 1
        why.append("感測器偏少")
    if rh is not None and not np.isnan(rh) and rh >= 85:
        score -= 1
        why.append(f"濕度 {rh:.0f}%，微型感測器可能高估")
    if src_type in ("insufficient_data", "suspected_sensor_fault", "mixed"):
        score -= 1
        why.append("來源判斷不確定")
    if stale is not None and stale > 30:
        score -= 1
        why.append(f"最新資料是 {stale:.0f} 分鐘前")
    why.append("已用在地係數校正" if calibrated else "未校正")
    return ["低", "中", "高"][max(score, 0)], why


def run(q: Query, root: Path = tools.DATA_ROOT) -> Answer:
    trace: list[dict] = []
    common = {"city": q.city, "time": q.time, "lat": q.lat, "lon": q.lon}

    # Algorithm 1 第 5～11 行：取得資料、品質檢查；局部感測器不足時擴大範圍（最多 2 次）
    micro = _log(trace, "get_microsensors", {**common, "radius_km": 15},
                 tools.get_microsensors(q.city, q.time, q.lat, q.lon, 15, root=root))
    src = {"type": "insufficient_data", "n_local": 0, "L": np.nan}
    if micro["ok"]:
        _log(trace, "assess_quality", {"rows": len(micro["data"])}, tools.assess_quality(micro["data"]))
        radius_local = 2.0
        for attempt in range(3):
            src = _log(trace, "source_attribution", {**common, "r_local_km": radius_local},
                       tools.source_attribution(micro["data"], q.time, q.lat, q.lon,
                                                tools.sp.Params(r_local_km=radius_local)))
            if src.get("n_local", 0) >= N_MIN:
                break
            radius_local *= 2
        src["r_local_km"] = radius_local

    station = _log(trace, "get_station", common, tools.get_station(q.city, q.time, q.lat, q.lon, root=root))
    weather = _log(trace, "get_weather", common, tools.get_weather(q.city, q.time, q.lat, q.lon, root=root))
    rh = weather.get("rh") if weather.get("ok") else (station.get("rh") if station.get("ok") else None)

    if not micro["ok"] or src.get("type") == "insufficient_data" or np.isnan(src.get("L", np.nan)):
        # Algorithm 1 第 13 行：改用最近的國家測站，信心上限為低
        src = {"type": "insufficient_data", "n_local": 0, "L": np.nan}
        local_raw = station.get("pm25", np.nan)
        cal = {"calibrated": False, "pm25": local_raw, "note": "微型感測器不足，改用國家測站"}
    else:
        local_raw = src["L"]
        cal = _log(trace, "calibrate", {"city": q.city, "sensor_pm25": local_raw, "rh": rh},
                   tools.calibrate(q.city, local_raw, rh))
    c_now = float(cal["pm25"])
    sources = ["民生公共物聯網微型感測器", "環境部國家空品測站", "中央氣象署自動氣象站", f"查詢時間 {q.time}"]
    if np.isnan(c_now):  # 例外處理：微型感測器與國家測站都沒有資料
        return Answer("查詢時間附近沒有可用的空品資料，無法判斷。", ["本地資料庫與國家測站在這個時間都沒有資料"],
                      ["請改查其他時間或地點，或稍後再試"], "低", ["沒有可用資料"], sources, trace)

    fcst = _log(trace, "forecast_trend", common, tools.forecast_trend(q.city, q.time, q.lat, q.lon, root=root))
    # 測站預測的變化量套到目標位置：c(h) = c_now + (預測值 − 測站現值)
    future = {h: max(c_now + v - fcst["station_now"], 0.0) for h, v in fcst.get("forecast", {}).items()}
    best_h, c_best = min(future.items(), key=lambda kv: kv[1]) if future else (0, c_now)
    if c_best >= c_now:
        best_h, c_best = 0, c_now

    know = _log(trace, "retrieve_knowledge", {"group": q.group, "activity": q.activity, "src_type": src["type"]},
                tools.retrieve_knowledge(q.group, q.activity, src["type"]))

    # Algorithm 3：個人化建議
    level = health.personal_level(c_now, q.group)
    B = src.get("B")
    c_away = tools.calibrate(q.city, B, rh)["pm25"] if B is not None and not np.isnan(B) else None
    ranked = health.rank_actions(health.candidate_actions(c_now, c_best, best_h, src["type"], c_away, q.activity),
                                 level, q.hours)
    conf, conf_why = _confidence(src.get("n_local", 0), src.get("r_local_km", 2.0), rh, src["type"],
                                 micro.get("stale_minutes"),
                                 cal.get("calibrated", False))
    actions = [a.text + (f"（{a.note}）" if a.note else "") for a in ranked]
    if conf == "低":
        actions.append("資料可信度偏低：敏感族群請以國家測站數值為準，保守安排活動")

    # 組成四段式回答（Algorithm 1 第 20 行）
    aqi = health.AQI_NAMES[health.aqi_level(c_now)]
    group_name = health.GROUP_NAMES.get(q.group, q.group)
    conclusion = (f"{q.place}目前 PM2.5 約 {c_now:.0f} μg/m³（新版 AQI「{aqi}」），"
                  f"屬於{TYPE_NAMES[src['type']]}。對{group_name}的建議是：{ranked[0].text}。")
    reasons = []
    if not np.isnan(src.get("L", np.nan)):
        reasons.append(f"{src['r_local_km']:g} km 內微型感測器中位數 {src['L']:.1f}、15 km 區域背景 {src['B']:.1f} μg/m³，"
                       f"局部超量 E = {src['E']:+.1f}；區域內 {src['C']:.0%} 的感測器比自己前 6 小時明顯升高（空間一致性 C）")
        if src.get("C_sub") is not None and not np.isnan(src.get("C_sub", np.nan)):
            reasons.append(f"8 km 內升高比例 {src['C_sub']:.0%}、8～15 km 外環 {src['C_ring']:.0%}")
    if station.get("ok") and not np.isnan(src.get("L", np.nan)) and c_now - station["pm25"] >= 5:
        reasons.append(f"國家測站的小時值要等整點結束才發布（最新是 {station['time'][11:16]} 那一小時），"
                       f"微型感測器已經看到比測站高 {c_now - station['pm25']:.0f} μg/m³ 的升高")
    if station.get("ok"):
        reasons.append(f"最近的國家測站「{station['sitename']}」（{station['distance_km']} km）{station['time'][11:16]} 為 "
                       f"{station['pm25']:.0f} μg/m³，風速 {station['wind_speed']} m/s")
    if weather.get("ok"):
        reasons.append(f"氣象站「{weather['station_name']}」：風向 {weather['wind_dir']:.0f}°、風速 {weather['wind_speed']} m/s、"
                       f"濕度 {weather['rh']:.0f}%")
    if future:
        reasons.append("未來趨勢（MLR）：" + "、".join(f"{h} 小時後約 {v:.0f}" for h, v in sorted(future.items())) + " μg/m³")
    reasons += know["rules"][:2]
    return Answer(conclusion, reasons, actions, conf, conf_why, sources, trace)
