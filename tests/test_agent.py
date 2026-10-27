"""Agent 原型（src/agent、src/knowledge）的離線測試：用合成資料跑完整流程，不打真實 API。"""

import numpy as np
import pandas as pd

from src.agent import schema, tools
from src.agent.pipeline import Query, run
from src.knowledge import health

LAT, LON = 22.63, 120.29


def test_sensitive_groups_are_warned_one_level_earlier():
    assert health.aqi_level(20) == 1
    assert health.personal_level(20, "general") == 1
    assert health.personal_level(20, "child") == 2


def test_shift_place_is_offered_only_for_local_or_subregional_events():
    for src_type, offered in (("local", True), ("subregional", True), ("regional", False), ("no_clear_event", False)):
        keys = [a.key for a in health.candidate_actions(35, 35, 0, src_type, 15, "exercise")]
        assert ("shift_place" in keys) == offered


def test_ranking_follows_moenv_guidance():
    # 「普通」時一般人照常運動；敏感族群提前一級 → 改成降低強度（S-032）
    general = health.rank_actions(health.candidate_actions(20, 20, 0, "regional", None, "exercise"), 1)
    child = health.rank_actions(health.candidate_actions(20, 20, 0, "regional", None, "exercise"), 2)
    assert general[0].key == "as_planned"
    assert child[0].key == "lower_intensity"


def test_schema_matches_tool_functions():
    for t in schema.TOOLS:
        assert callable(getattr(tools, t["name"])), t["name"]
        assert "description" in t and t["input_schema"]["type"] == "object"


def _write(df, root, source, city, key):
    df = df.copy()
    df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S%z").str.replace(r"(\d\d)(\d\d)$", r"\1:\2", regex=True)
    for day, g in df.groupby(df["time"].str[:10]):
        path = root / source / city
        path.mkdir(parents=True, exist_ok=True)
        g.to_csv(path / f"{day}.csv.gz", index=False)


def _synthetic_store(root):
    """30 個感測器在目標點周圍；最後 30 分鐘全部由 5 升到 20 μg/m³（區域型）。"""
    city = "高雄市"
    rng = np.random.default_rng(0)
    times = pd.date_range("2026-10-23 04:00", "2026-10-23 11:30", freq="5min", tz="Asia/Taipei")
    rows = []
    for i in range(30):
        lat, lon = LAT + rng.uniform(-0.08, 0.08), LON + rng.uniform(-0.08, 0.08)
        if i < 8:  # 確保 2 km 內有足夠感測器
            lat, lon = LAT + rng.uniform(-0.008, 0.008), LON + rng.uniform(-0.008, 0.008)
        for t in times:
            pm = 5 + rng.normal(0, 0.3) + (15 if t >= times[-6] else 0)
            rows.append({"station_id": str(1000 + i), "device_name": f"S{i}", "city": city, "township": np.nan,
                         "area_type": np.nan, "lon": lon, "lat": lat, "time": t, "pm25": pm, "rh": 70.0,
                         "temp": 25.0, "n_obs": 5})
    _write(pd.DataFrame(rows), root, "colife", city, "station_id")
    hours = pd.date_range("2026-10-13 00:00", "2026-10-23 11:00", freq="h", tz="Asia/Taipei")
    st = pd.DataFrame({"siteid": "56", "sitename": "前金", "county": city, "lon": LON, "lat": LAT, "time": hours,
                       "pm25": 8 + 3 * np.sin(np.arange(len(hours)) / 5), "pm10": 20.0, "rh": 72.0, "temp": 26.0,
                       "wind_speed": 2.0, "wind_dir": 330.0, "rain": 0.0})
    _write(st, root, "moenv", city, "siteid")
    w = pd.DataFrame({"station_id": "C0V490", "station_name": "新興", "county": city, "town": "新興區",
                      "lon": LON + 0.01, "lat": LAT, "time": hours[-12:], "wind_dir": 330.0, "wind_speed": 4.0,
                      "temp": 27.0, "rh": 75.0, "pressure": 1000.0})
    _write(w, root, "cwa", city, "station_id")


def test_pipeline_end_to_end_on_synthetic_regional_event(tmp_path):
    _synthetic_store(tmp_path)
    q = Query("高雄市", LAT, LON, "2026-10-23 11:30", group="child", activity="exercise")
    ans = run(q, root=tmp_path)
    called = [t["tool"] for t in ans.trace]
    assert called[:3] == ["get_microsensors", "assess_quality", "source_attribution"]
    assert {"get_station", "get_weather", "calibrate", "forecast_trend", "retrieve_knowledge"} <= set(called)
    src = next(t["result"] for t in ans.trace if t["tool"] == "source_attribution")
    assert src["type"] == "regional"
    assert "區域型" in ans.conclusion
    assert not any("換到 8 km" in a for a in ans.actions)   # 區域型不建議換地點
    assert ans.confidence in ("高", "中", "低")


def test_pipeline_falls_back_to_station_without_microsensors(tmp_path):
    _synthetic_store(tmp_path)
    ans = run(Query("高雄市", LAT, LON, "2026-10-25 11:30"), root=tmp_path)
    assert ans.trace[0]["result"]["ok"] is False
    assert ans.confidence == "低"
    assert "沒有可用" in ans.conclusion
