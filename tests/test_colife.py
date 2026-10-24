"""src.data.colife 與 src.data.quality 的離線測試（不呼叫真實 API）。"""

import pandas as pd

from src.data import colife, quality


def _raw(rows):
    df = pd.DataFrame(rows, columns=["station_id", "device_name", "city", "township", "area_type",
                                     "lon", "lat", "variable", "time", "value"])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(colife.TZ)
    return df


STATION = ["A", "dev", "臺中市", None, None, 120.6, 24.1]


def test_aggregate_averages_and_pivots():
    raw = _raw([
        STATION + ["pm25", "2026-10-19 10:01", 10.0],
        STATION + ["pm25", "2026-10-19 10:03", 20.0],
        STATION + ["rh", "2026-10-19 10:02", 80.0],
        STATION + ["temp", "2026-10-19 10:02", 25.0],
    ])
    out = colife.aggregate(raw, freq="5min")
    assert len(out) == 1
    row = out.iloc[0]
    assert row["pm25"] == 15.0 and row["rh"] == 80.0 and row["temp"] == 25.0
    assert row["n_obs"] == 2
    assert list(out.columns) == colife.OBS_COLUMNS


def test_save_daily_keeps_most_complete_interval(tmp_path):
    raw_first = _raw([STATION + ["pm25", "2026-10-19 10:01", 10.0]])
    raw_later = _raw([
        STATION + ["pm25", "2026-10-19 10:01", 10.0],
        STATION + ["pm25", "2026-10-19 10:04", 30.0],
    ])
    colife.save_daily(colife.aggregate(raw_first), tmp_path)
    colife.save_daily(colife.aggregate(raw_later), tmp_path)
    saved = pd.read_csv(tmp_path / "2026-10-19.csv.gz")
    assert len(saved) == 1
    assert saved.loc[0, "n_obs"] == 2 and saved.loc[0, "pm25"] == 20.0


def test_quality_flags():
    times = pd.date_range("2026-10-19 10:00", periods=14, freq="5min", tz=colife.TZ)
    stuck = pd.DataFrame({"station_id": "S", "time": times, "pm25": 7.0, "rh": 70.0})
    bad = pd.DataFrame({
        "station_id": "B",
        "time": times[:4],
        "pm25": [-1.0, 900.0, None, 12.0],
        "rh": [70.0, 70.0, 70.0, 0.0],
    })
    flagged = quality.flag(pd.concat([stuck, bad], ignore_index=True))
    assert (flagged.loc[flagged["station_id"] == "S", "qc_flag"] == "stuck").all()
    assert flagged.loc[flagged["station_id"] == "B", "qc_flag"].tolist() == [
        "pm25_negative", "pm25_extreme", "pm25_missing", "rh_invalid"]


def test_quality_flag_handles_duplicate_index():
    """多個日檔合併後索引會重複；品質檢查不能因此出錯或對錯列。"""
    times = pd.date_range("2026-10-19 10:00", periods=14, freq="5min", tz=colife.TZ)
    a = pd.DataFrame({"station_id": "S", "time": times[:7], "pm25": 7.0, "rh": 70.0})
    b = pd.DataFrame({"station_id": "S", "time": times[7:], "pm25": 7.0, "rh": 70.0})
    merged = pd.concat([a, b])  # 不加 ignore_index，索引 0..6 重複兩次
    flagged = quality.flag(merged)
    assert len(flagged) == 14 and (flagged["qc_flag"] == "stuck").all()
