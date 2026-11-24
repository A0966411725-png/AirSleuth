"""LLM 規劃版的 AirSleuth（Algorithm 1 的 ReAct 版本，OpenSpec 變更 add-llm-planner）。

LLM（Gemini）只負責：理解問題、決定呼叫哪個工具、把工具結果寫成口語。
所有數字都來自確定性的工具；回答送出前會檢查「文中每個帶單位的數字都能在工具結果裡找到」，
找不到就請 LLM 重寫一次，還是不行就改用確定性流程的回答。沒有 key 或模型都無法使用時，同樣改用確定性流程。

用法：
    from src.agent.planner import Planner
    result = Planner().ask("我在高雄前金區，現在可以帶小孩去跑步嗎？", time="2026-10-23 11:30")
    print(result.text)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.agent import geo, tools
from src.agent.llm import GeminiClient, LLMError, LLMUnavailable
from src.agent.pipeline import Query, run
from src.knowledge import health

MAX_TOOL_CALLS = 12
GROUPS = list(health.GROUP_NAMES)          # general, child, elderly, asthma, heart
ACTIVITIES = list(health.ACTIVITY_NAMES)   # rest, walk, exercise
SOURCE_TYPES = ["regional", "subregional", "local", "mixed", "suspected_sensor_fault", "no_clear_event", "insufficient_data"]

PLANNER_TOOLS = [
    {"name": "resolve_place",
     "description": "把使用者提到的地點（行政區名稱或經緯度）轉成縣市與座標。只支援臺中市、高雄市。",
     "parameters": {"type": "OBJECT", "properties": {
         "text": {"type": "STRING", "description": "使用者描述地點的原文，例如「高雄前金區」"}}, "required": ["text"]}},
    {"name": "analyze_air_quality",
     "description": "在指定地點與時間執行完整的空品分析：取得微型感測器、品質檢查、來源判斷（區域／次區域／局部）、"
                    "國家測站與氣象、在地校正、未來 1～6 小時預測，並依使用者族群與活動排出建議與信心程度。"
                    "回傳的所有數字都可以直接引用。",
     "parameters": {"type": "OBJECT", "properties": {
         "city": {"type": "STRING", "enum": geo.SUPPORTED},
         "lat": {"type": "NUMBER"}, "lon": {"type": "NUMBER"},
         "place": {"type": "STRING", "description": "顯示用的地點名稱，例如「高雄前金區」"},
         "group": {"type": "STRING", "enum": GROUPS, "description": "general 一般民眾、child 孩童、elderly 長者、asthma 氣喘、heart 心血管疾病"},
         "activity": {"type": "STRING", "enum": ACTIVITIES, "description": "rest 靜態、walk 散步或通勤、exercise 跑步等運動"},
         "hours": {"type": "NUMBER", "description": "預計在戶外停留幾小時，預設 1"}},
         "required": ["city", "lat", "lon", "group", "activity"]}},
    {"name": "retrieve_knowledge",
     "description": "取得與使用者族群、活動、污染型態相關的領域規則與文獻依據（例如為什麼敏感族群要提前一級）。",
     "parameters": {"type": "OBJECT", "properties": {
         "group": {"type": "STRING", "enum": GROUPS}, "activity": {"type": "STRING", "enum": ACTIVITIES},
         "src_type": {"type": "STRING", "enum": SOURCE_TYPES}}, "required": ["group", "activity", "src_type"]}},
]

SYSTEM_PROMPT = """你是 AirSleuth 空品偵探，一個分析臺灣 PM2.5 的領域 AI Agent。查詢時間（現在）是 {time}（台灣時間）。

規則：
1. 回答空品問題前，先用 resolve_place 確認地點，再用 analyze_air_quality 分析。地點不明確時，先問使用者在哪一區，不要猜。
2. 只支援臺中市、高雄市。其他地方要直接說明不支援，不要編資料。
3. 所有數字（濃度、比例、距離、風速）只能照抄工具結果，不能自己估算或換算出新數字。
4. 不可以改變工具給的建議排序、風險等級與信心程度；可以用口語解釋原因。
5. 從使用者的話判斷族群（孩童、長者、氣喘、心血管疾病，沒提到就是一般民眾）與活動（跑步或運動、散步或通勤、靜態）。
   名詞：B 是 15 km 內感測器的中位數（區域背景），L 是局部範圍內感測器的中位數，E = L − B 是局部超量，
   C 是區域內比自己前 6 小時明顯升高的感測器比例（空間一致性）。中位數不要寫成平均。
6. 用繁體中文，依序寫四段：
   **結論**：一句話說明目前濃度、新版 AQI 等級、污染屬於哪一型，以及最建議的做法。
   **為什麼**：2～4 點證據（區域背景、局部超量、空間一致性、測站、氣象、預測）。
   **建議**：照工具排序列出建議。
   **信心**：信心程度與原因。
   最後一行寫「資料來源：民生公共物聯網微型感測器、環境部國家空品測站、中央氣象署自動氣象站」。
7. 問題和空氣品質無關時，簡短說明你只能回答 PM2.5 與戶外活動的問題。"""

NUMBER_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(μg/m³|µg/m³|μg/m3|ug/m3|微克|%|％|公里|km|m/s|公尺/秒)")


@dataclass
class PlannerResult:
    text: str
    kind: str                    # answer（LLM 回答且通過檢查）、clarify（追問）、refuse（不支援／無關）、fallback（確定性流程）
    model: str | None = None
    trace: list[dict] = field(default_factory=list)
    facts: dict | None = None
    notes: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


class Planner:
    def __init__(self, client: GeminiClient | None = None, root: Path = tools.DATA_ROOT):
        self.client = client or GeminiClient()
        self.root = root

    # ---- 工具執行 -------------------------------------------------------------------------------------------
    def _execute(self, name: str, args: dict, time: str, state: dict) -> dict:
        if name == "resolve_place":
            return geo.resolve_place(str(args.get("text", "")))
        if name == "analyze_air_quality":
            city = args.get("city")
            if city not in geo.SUPPORTED:
                return {"ok": False, "message": f"不支援的縣市：{city}"}
            q = Query(city=city, lat=float(args["lat"]), lon=float(args["lon"]), time=time,
                      group=args.get("group") if args.get("group") in GROUPS else "general",
                      activity=args.get("activity") if args.get("activity") in ACTIVITIES else "exercise",
                      hours=float(args.get("hours") or 1.0), place=str(args.get("place") or "目標地點"))
            answer = run(q, root=self.root)
            state["answer"] = answer
            return {"ok": True, "facts": answer.facts, "reference_answer": answer.to_text()}
        if name == "retrieve_knowledge":
            return tools.retrieve_knowledge(args.get("group", "general"), args.get("activity", "exercise"),
                                            args.get("src_type", "no_clear_event"))
        return {"ok": False, "error": f"沒有這個工具：{name}。可用的工具：{', '.join(t['name'] for t in PLANNER_TOOLS)}"}

    # ---- 主流程 ---------------------------------------------------------------------------------------------
    def ask(self, question: str, time: str, history: list[dict] | None = None) -> PlannerResult:
        contents = list(history or []) + [{"role": "user", "parts": [{"text": question}]}]
        if not self.client.available:
            return self._fallback(question, time, contents, note="沒有設定 GEMINI_API_KEY，改用確定性流程（LLM 未啟用）")
        system = SYSTEM_PROMPT.format(time=time)
        trace: list[dict] = []
        state: dict = {}
        model = None
        try:
            for _ in range(MAX_TOOL_CALLS + 1):
                content, model = self.client.generate(contents, system, PLANNER_TOOLS)
                contents.append(content)
                calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
                if not calls:
                    break
                if len([t for t in trace if "tool" in t]) + len(calls) > MAX_TOOL_CALLS:
                    return self._fallback(question, time, contents, trace, model, "工具呼叫超過 12 次，改用確定性流程")
                responses = []
                for call in calls:
                    result = self._execute(call["name"], call.get("args", {}), time, state)
                    trace.append({"step": len(trace) + 1, "tool": call["name"], "args": call.get("args", {}),
                                  "result": _json_safe(result)})
                    responses.append({"functionResponse": {"name": call["name"], "id": call.get("id"),
                                                           "response": _json_safe(result)}})
                contents.append({"role": "user", "parts": responses})
            text = _text_of(content)
            if "answer" not in state:  # 沒有做分析：追問地點、不支援或與空品無關
                return PlannerResult(text, classify_reply(text, trace), model, trace, None, history=contents)
            bad = unsupported_numbers(text, trace)
            if bad:
                contents.append({"role": "user", "parts": [{"text":
                    f"以下數字在工具結果中找不到：{'、'.join(bad)}。請只使用工具結果裡的數字重寫完整回答，不要新增任何數字。"}]})
                content, model = self.client.generate(contents, system, PLANNER_TOOLS)
                contents.append(content)
                text = _text_of(content)
                bad = unsupported_numbers(text, trace)
                if bad:
                    return self._fallback(question, time, contents, trace, model,
                                          f"LLM 回答中有找不到出處的數字（{'、'.join(bad)}），改用確定性流程的回答", state)
            notes = [] if _mentions(text, state["answer"].facts["top_action"]) else ["LLM 回答沒有逐字寫出第一順位建議"]
            return PlannerResult(text, "answer", model, trace, state["answer"].facts, notes, contents)
        except (LLMUnavailable, LLMError) as exc:
            return self._fallback(question, time, contents, trace, model, f"LLM 暫時無法使用（{exc}），改用確定性流程", state)

    def _fallback(self, question: str, time: str, contents: list[dict], trace: list[dict] | None = None,
                  model: str | None = None, note: str = "", state: dict | None = None) -> PlannerResult:
        """不靠 LLM：用規則解析問題，跑確定性流程（Algorithm 1 的固定順序版）。"""
        trace = list(trace or [])
        answer = (state or {}).get("answer")
        if answer is None:
            parsed = parse_question(question, contents)
            if not parsed["ok"]:
                return PlannerResult(parsed["message"] + "（LLM 未使用）", "clarify" if parsed["reason"] != "unsupported" else "refuse",
                                     model, trace, None, [note], contents)
            answer = run(Query(**parsed["query"], time=time), root=self.root)
            trace += answer.trace
        text = answer.to_text() + f"\n\n_（{note}）_"
        return PlannerResult(text, "fallback", model, trace, answer.facts, [note], contents)


# ---- 沒有 LLM 時的規則式問題解析 ------------------------------------------------------------------------------
GROUP_WORDS = [("child", ["小孩", "孩子", "孩童", "兒童", "小朋友", "寶寶", "嬰兒", "幼兒"]),
               ("elderly", ["長輩", "長者", "老人", "阿公", "阿嬤", "爺爺", "奶奶", "外公", "外婆"]),
               ("asthma", ["氣喘", "哮喘"]), ("heart", ["心臟", "心血管", "高血壓"])]
ACTIVITY_WORDS = [("exercise", ["跑步", "慢跑", "運動", "打球", "騎車", "健身", "爬山", "游泳"]),
                  ("walk", ["散步", "走路", "通勤", "遛狗", "逛", "等公車"]), ("rest", ["坐", "休息", "看書", "野餐"])]


def parse_question(question: str, contents: list[dict] | None = None) -> dict:
    """從問題（與先前的對話）找出地點、族群、活動。"""
    texts = [p.get("text", "") for c in (contents or []) if c.get("role") == "user" for p in c.get("parts", [])]
    full = " ".join(texts + [question])
    place = geo.resolve_place(full)
    if not place["ok"]:
        return {"ok": False, "reason": place["reason"], "message": place["message"]}
    group = next((g for g, words in GROUP_WORDS if any(w in full for w in words)), "general")
    activity = next((a for a, words in ACTIVITY_WORDS if any(w in full for w in words)), "exercise")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:個)?小時", full)
    return {"ok": True, "query": {"city": place["city"], "lat": place["lat"], "lon": place["lon"], "group": group,
                                  "activity": activity, "hours": float(m.group(1)) if m else 1.0,
                                  "place": f"{place['city']}{place['district']}"}}


# ---- 數字可追溯檢查 ---------------------------------------------------------------------------------------------
def _numbers_in(obj) -> list[float]:
    out: list[float] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += _numbers_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += _numbers_in(v)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float, np.integer, np.floating)) and not np.isnan(obj):
        out.append(float(obj))
    elif isinstance(obj, str):
        out += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", obj)]
    return out


def unsupported_numbers(text: str, trace: list[dict]) -> list[str]:
    """回傳文中帶單位、但在工具結果裡找不到的數字（容許四捨五入到整數的誤差；比例可寫成百分比）。"""
    known = _numbers_in([t.get("result") for t in trace])
    bad = []
    for value, unit in NUMBER_WITH_UNIT.findall(text):
        x = float(value)
        percent = unit in ("%", "％")
        ok = any(abs(x - v) <= 0.5 + 1e-9 or (percent and abs(x - 100 * v) <= 0.5 + 1e-9) for v in known)
        if not ok:
            bad.append(f"{value}{unit}")
    return bad


def fix_bold(text: str) -> str:
    """把「**結論：**文字」改成「**結論**：文字」：粗體結尾緊接全形標點再接中文時，Markdown 不會轉成粗體。"""
    return re.sub(r"\*\*([^*\n]+?)([：:。，；])\*\*", r"**\1**\2", text)


def classify_reply(text: str, trace: list[dict]) -> str:
    """沒有做分析的回覆：clarify（追問地點等資訊）或 refuse（不支援的地點、與空品無關）。"""
    if any(t.get("result", {}).get("reason") == "unsupported" for t in trace):
        return "refuse"
    if re.search(r"請(告訴|提供|問)|哪一?區|哪裡|在哪|哪個地方", text):
        return "clarify"
    if re.search(r"不在.{0,6}範圍|不支援|無法查詢|只支援|僅支援|只能回答", text):
        return "refuse"
    return "clarify"


def _mentions(text: str, action: str) -> bool:
    core = re.split(r"[，,（(]", action)[0]
    return core in text


def _text_of(content: dict) -> str:
    return fix_bold("".join(p.get("text", "") for p in content.get("parts", []) if "text" in p and not p.get("thought")).strip())


def _json_safe(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, default=lambda o: None if isinstance(o, float) and np.isnan(o) else str(o)))
