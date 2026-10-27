"""Agent 工具的 JSON 規格（function calling／tool use 用），對應 `src/agent/tools.py`。

LLM Planner（架構模組 ③）只看得到這些規格：名稱、用途、參數。它決定呼叫順序與參數，
實際計算由 tools.py 執行，結果再交回 LLM 解釋（ReAct 式的「推理 → 行動 → 觀察」，S-035）。
`python -m src.agent.schema` 會印出 JSON，可直接放進 LLM API 的 tools 參數。
"""

from __future__ import annotations

import json

_LOC = {
    "city": {"type": "string", "description": "縣市名稱，要用「臺」，例如 臺中市、高雄市"},
    "time": {"type": "string", "description": "查詢時間（台灣時間），例如 2026-10-23 11:30"},
    "lat": {"type": "number", "description": "目標位置緯度"},
    "lon": {"type": "number", "description": "目標位置經度"},
}
_REQ = ["city", "time", "lat", "lon"]


def _tool(name: str, module: str, description: str, extra: dict | None = None, required: list | None = None) -> dict:
    props = {**_LOC, **(extra or {})}
    return {"name": name, "module": module, "description": description,
            "input_schema": {"type": "object", "properties": props, "required": required or _REQ}}


TOOLS = [
    _tool("get_microsensors", "④", "取得目標位置半徑內、查詢時間前數小時的微型感測器 5 分鐘資料（PM2.5、濕度、溫度）。",
          {"radius_km": {"type": "number", "description": "搜尋半徑，預設 15"}}),
    {"name": "assess_quality", "module": "④", "description": "檢查微型感測器資料品質：缺值、負值、極端值、卡住、濕度無效的比例。",
     "input_schema": {"type": "object", "properties": {"data_ref": {"type": "string", "description": "get_microsensors 回傳的資料代號"}},
                      "required": ["data_ref"]}},
    _tool("get_station", "④", "取得最近的環境部國家測站在上一個完整小時的 PM2.5、濕度、風向風速。"),
    _tool("get_weather", "④", "取得最近的中央氣象署自動氣象站的最新觀測：風向、風速、濕度、溫度。"),
    _tool("source_attribution", "⑤", "Algorithm 2：計算區域背景 B、局部超量 E、空間一致性 C，判斷區域型／次區域型／局部型／混合型／感測器異常。",
          {"r_local_km": {"type": "number", "description": "局部半徑，預設 2；感測器不足時可加倍"}}),
    _tool("forecast_trend", "⑤", "以最近國家測站的歷史資料訓練多元線性迴歸，預測未來 1、3、6 小時的 PM2.5。"),
    {"name": "calibrate", "module": "⑤", "description": "以在地校正係數（線性＋氣象站濕度）校正微型感測器讀數。",
     "input_schema": {"type": "object", "properties": {
         "city": _LOC["city"], "sensor_pm25": {"type": "number"}, "rh": {"type": "number", "description": "相對濕度（%）"}},
         "required": ["city", "sensor_pm25"]}},
    {"name": "retrieve_knowledge", "module": "⑥", "description": "取出相關的領域規則：新版 AQI、敏感族群、運動取捨、換地點是否有效。",
     "input_schema": {"type": "object", "properties": {
         "group": {"type": "string", "enum": ["general", "child", "elderly", "asthma", "heart"]},
         "activity": {"type": "string", "enum": ["rest", "walk", "exercise"]},
         "src_type": {"type": "string"}}, "required": ["group", "activity"]}},
]


def main() -> None:
    print(json.dumps([{k: v for k, v in t.items() if k != "module"} for t in TOOLS], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
