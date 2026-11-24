"""demo 網站用的事件樣本（data/sample/demo/）必須能單獨重播事件，結果與完整資料一致（OpenSpec 變更 add-demo-site）。

完整資料的結果在產生樣本時已核對過（scripts/make_demo_sample.py）；這裡只用版本控制內的樣本，不需要 data/raw/。
"""

import json
from pathlib import Path

from src.agent.pipeline import Query, run

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample" / "demo"
EXPECTED = {"kaohsiung_regional": "regional", "taichung_subregional": "subregional", "taichung_clear": "no_clear_event",
            "kaohsiung_local": "local"}


def test_each_recorded_event_replays_from_the_sample_alone():
    events = json.loads((SAMPLE / "events.json").read_text(encoding="utf-8"))
    assert {e["id"] for e in events} == set(EXPECTED)
    for e in events:
        facts = run(Query(e["city"], e["lat"], e["lon"], e["time"], group="child"), root=SAMPLE).facts
        assert facts["source_type"] == EXPECTED[e["id"]], e["id"]
        assert facts["forecast_local"], e["id"]          # 測站 60 天歷史足夠做預測
        assert facts["indicators"]["n_local"] >= 5, e["id"]


def test_regional_event_never_suggests_moving_away():
    e = next(x for x in json.loads((SAMPLE / "events.json").read_text(encoding="utf-8")) if x["id"] == "kaohsiung_regional")
    for group in ("general", "child", "asthma"):
        facts = run(Query(e["city"], e["lat"], e["lon"], e["time"], group=group), root=SAMPLE).facts
        assert not any("換到" in a for a in facts["actions"])
