"""src.analytics.calibration 的離線測試（合成資料）。"""

import numpy as np
import pandas as pd

from src.analytics import calibration as cal


def _colife(hours=6):
    """測站旁 3 個感測器，讀數 = 1.5 × 真值；遠處 1 個感測器不該被納入。"""
    t = pd.date_range("2026-10-19 12:00", periods=hours * 12, freq="5min", tz="Asia/Taipei")
    truth = 10 + np.arange(len(t)) // 12 * 2.0  # 每小時升 2
    wiggle = np.where(np.arange(len(t)) % 2, 0.1, -0.1)  # 小時平均為 0；避免被品質檢查判為「卡住」
    rows = []
    for sid, lat, lon in [("a", 24.0, 120.6), ("b", 24.002, 120.6), ("c", 24.0, 120.602), ("far", 24.2, 120.6)]:
        rows.append(pd.DataFrame({"station_id": sid, "lat": lat, "lon": lon, "time": t,
                                  "pm25": 1.5 * (truth + wiggle) + (100 if sid == "far" else 0), "rh": 70.0}))
    return pd.concat(rows, ignore_index=True)


def _station(label_end=True):
    hours = pd.date_range("2026-10-19 12:00", periods=6, freq="h", tz="Asia/Taipei")
    t = hours + pd.Timedelta(hours=1) if label_end else hours
    return pd.DataFrame({"siteid": "1", "sitename": "測試", "lat": 24.0, "lon": 120.6, "time": t,
                         "pm25": 10 + np.arange(6) * 2.0, "rh": 70.0})


def test_collocate_uses_only_nearby_sensors_and_hour_ending_label():
    pairs = cal.collocate(cal.hourly_sensor_means(_colife(), "end"), _station(), radius_km=1.0)
    assert len(pairs) == 6
    assert (pairs["n_sensors"] == 3).all()
    assert np.allclose(pairs["sensor_pm25"], 1.5 * pairs["ref_pm25"])


def test_best_alignment_prefers_matching_label():
    res = cal.best_alignment(_colife(), _station(label_end=True)).set_index("label")
    assert res.loc["end", "MAE"] < res.loc["start", "MAE"]


def test_linear_calibration_removes_multiplicative_bias():
    rng = np.random.default_rng(0)
    raw = rng.uniform(5, 40, 60)
    pairs = pd.DataFrame({"siteid": np.repeat(list("abc"), 20), "sensor_pm25": raw,
                          "ref_pm25": raw / 1.5 + rng.normal(0, 0.3, 60), "station_rh": 70.0})
    res = cal.leave_one_site_out(pairs, {"raw": [], "linear": ["sensor_pm25"]}).set_index("model")
    assert res.loc["linear", "MAE"] < 0.5 < res.loc["raw", "MAE"]
    assert abs(cal.fit(pairs, ["sensor_pm25"])["sensor_pm25"] - 1 / 1.5) < 0.02


def test_fit_skips_rows_with_missing_humidity():
    """多天資料中測站濕度偶有缺值；fit 要略過缺值列，不能讓最小平方法失敗（2026-10-24 實測）。"""
    rng = np.random.default_rng(1)
    raw = rng.uniform(5, 40, 40)
    pairs = pd.DataFrame({"sensor_pm25": raw, "ref_pm25": raw / 1.5, "station_rh": rng.uniform(50, 90, 40)})
    pairs.loc[[3, 17], "station_rh"] = np.nan
    coef = cal.fit(pairs, ["sensor_pm25", "station_rh"])
    assert coef.notna().all() and abs(coef["sensor_pm25"] - 1 / 1.5) < 0.01
