"""LLM 規劃版 Agent 的離線測試：用照腳本回應的假 LLM，不打真實 API（OpenSpec 變更 add-llm-planner）。"""

import requests

from src.agent import geo
from src.agent.llm import GeminiClient, LLMUnavailable
from src.agent.planner import Planner, classify_reply, parse_question, unsupported_numbers
from tests.test_agent import LAT, LON, _synthetic_store

TIME = "2026-10-23 11:30"


class FakeClient:
    """依序回傳預先寫好的模型回應；記錄每次收到的對話。"""

    available = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate(self, contents, system=None, tools=None):
        self.calls.append(list(contents))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, "fake-model"


def call(name, **args):
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args, "id": name}}]}


def text(t):
    return {"role": "model", "parts": [{"text": t}]}


def analyze_args(**extra):
    return {"city": "高雄市", "lat": LAT, "lon": LON, "group": "child", "activity": "exercise", "place": "測試點", **extra}


def test_resolve_place_districts_and_unsupported_cities():
    assert geo.resolve_place("我在台中西屯")["district"] == "西屯區"
    assert geo.resolve_place("高雄前金區")["city"] == "高雄市"
    assert geo.resolve_place("臺中市")["reason"] == "need_district"
    assert geo.resolve_place("台北信義區")["reason"] == "unsupported"
    assert geo.resolve_place("臺中")["ok"] is False   # 「臺中」不能被誤判成「中區」


def test_tool_loop_produces_traceable_answer(tmp_path):
    _synthetic_store(tmp_path)
    planner = Planner(None, root=tmp_path)
    # 先跑一次確定性流程，拿到真實數字，讓假 LLM 的回答引用正確的值
    facts = planner._execute("analyze_air_quality", analyze_args(), TIME, {})["facts"]
    final = text(f"**結論：**目前約 {facts['pm25_now']} μg/m³，屬於區域型。建議：{facts['top_action']}。")
    fake = FakeClient([call("resolve_place", text="高雄前金"), call("analyze_air_quality", **analyze_args()), final])
    result = Planner(fake, root=tmp_path).ask("前金現在可以帶小孩跑步嗎？", TIME)
    assert result.kind == "answer"
    assert [t["tool"] for t in result.trace] == ["resolve_place", "analyze_air_quality"]
    assert result.facts["source_type"] == "regional"
    assert result.notes == []


def test_unknown_tool_is_rejected_and_logged(tmp_path):
    _synthetic_store(tmp_path)
    fake = FakeClient([call("delete_everything"), text("請告訴我您在哪一區？")])
    result = Planner(fake, root=tmp_path).ask("隨便", TIME)
    assert result.trace[0]["tool"] == "delete_everything"
    assert "沒有這個工具" in result.trace[0]["result"]["error"]
    assert result.kind == "clarify"


def test_asks_for_place_without_calling_data_tools(tmp_path):
    fake = FakeClient([text("請問您目前在哪一區？目前支援臺中市、高雄市。")])
    result = Planner(fake, root=tmp_path).ask("現在適合跑步嗎？", TIME)
    assert result.kind == "clarify"
    assert result.trace == []


def test_unsupported_city_is_refused():
    assert classify_reply("台北信義區不在服務範圍內，僅支援臺中市與高雄市。", []) == "refuse"
    assert classify_reply("請告訴我您在哪一區（僅支援臺中市、高雄市）", []) == "clarify"


def test_hallucinated_number_falls_back_to_pipeline(tmp_path):
    _synthetic_store(tmp_path)
    wrong = text("目前 PM2.5 高達 87 μg/m³，建議待在室內。")
    fake = FakeClient([call("analyze_air_quality", **analyze_args()), wrong, wrong])  # 重寫後還是錯
    result = Planner(fake, root=tmp_path).ask("前金現在空氣如何？", TIME)
    assert result.kind == "fallback"
    assert "87μg/m³" in result.notes[0]
    assert "區域型" in result.text            # 改用確定性流程的回答
    assert len(fake.calls) == 3                # 分析、第一次回答、要求重寫


def test_unsupported_numbers_accepts_rounding_and_percent():
    trace = [{"tool": "x", "result": {"pm25": 20.43, "C": 0.88, "km": 0.7}}]
    assert unsupported_numbers("約 20 μg/m³，88% 感測器升高，距離 1 km", trace) == []
    assert unsupported_numbers("約 35 μg/m³", trace) == ["35μg/m³"]


def test_no_key_uses_deterministic_pipeline(tmp_path):
    _synthetic_store(tmp_path)
    planner = Planner(GeminiClient(key=""), root=tmp_path)
    result = planner.ask(f"我在高雄 {LAT}, {LON}，帶小孩跑步可以嗎？", TIME)
    assert result.kind == "fallback"
    assert "LLM 未啟用" in result.text
    assert result.facts["query"]["group"] == "child"


def test_llm_outage_falls_back(tmp_path):
    _synthetic_store(tmp_path)
    fake = FakeClient([LLMUnavailable("所有模型都忙碌")])
    result = Planner(fake, root=tmp_path).ask(f"高雄 {LAT}, {LON} 現在可以散步嗎？", TIME)
    assert result.kind == "fallback"
    assert result.facts["query"]["activity"] == "walk"


def test_parse_question_reads_group_activity_and_hours():
    q = parse_question("我在台中西屯，想帶阿嬤去散步 2 小時")["query"]
    assert (q["city"], q["group"], q["activity"], q["hours"]) == ("臺中市", "elderly", "walk", 2.0)


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.ok = status == 200

    def json(self):
        return self._body


class _Session:
    def __init__(self, responses):
        self.responses, self.urls = list(responses), []

    def post(self, url, headers=None, json=None, timeout=None):
        self.urls.append(url)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_model_fallback_on_overload_quota_and_timeout():
    ok = _Resp(200, {"candidates": [{"content": {"role": "model", "parts": [{"text": "好"}]}}], "modelVersion": "m3"})
    session = _Session([_Resp(503, {}), _Resp(503, {}), requests.Timeout(), ok])
    client = GeminiClient(key="test", models=["m1", "m2", "m3"], session=session, retry_wait=0)
    content, model = client.generate([{"role": "user", "parts": [{"text": "hi"}]}])
    assert model == "m3"
    assert [u.split("/models/")[1].split(":")[0] for u in session.urls] == ["m1", "m1", "m2", "m3"]
    assert all("key=" not in u for u in session.urls)   # key 只放在標頭


def test_concept_question_uses_knowledge_tool(tmp_path):
    fake = FakeClient([call("retrieve_knowledge"), text("新版 AQI 的「普通」是 12.5～30.4 μg/m³（S-029）。")])
    result = Planner(fake, root=tmp_path).ask("新版 AQI 的普通是多少？", TIME)
    assert result.kind == "knowledge"
    assert result.trace[0]["tool"] == "retrieve_knowledge"
    assert len(result.trace[0]["result"]["rules"]) >= 6     # 不帶參數 → 全部規則


def test_concept_answer_with_invented_number_is_not_returned(tmp_path):
    wrong = text("新版 AQI 的「普通」是 15.5～35.4 μg/m³。")   # E4 實際發生過：舊版範圍
    fake = FakeClient([wrong, wrong])                        # 重寫時仍沒查工具、仍是錯的數字
    result = Planner(fake, root=tmp_path).ask("新版 AQI 的普通是多少？", TIME)
    assert result.kind == "fallback"
    assert "15.5" not in result.text and "12.5–30.4" in result.text


def test_concept_question_falls_back_to_rules_when_llm_fails(tmp_path):
    # E4 實際發生：已查過領域知識，LLM 寫回答時 503 → 應列出規則，而不是「找不到地點」
    fake = FakeClient([call("retrieve_knowledge"), LLMUnavailable("503")])
    result = Planner(fake, root=tmp_path).ask("區域型污染和局部型污染有什麼不同？", TIME)
    assert result.kind == "fallback"
    assert "區域型" in result.text and "局部型" in result.text
    assert "找不到這個地點" not in result.text
    no_key = Planner(GeminiClient(key=""), root=tmp_path).ask("為什麼小孩要比大人更早注意空氣品質？", TIME)
    assert "敏感族群" in no_key.text
