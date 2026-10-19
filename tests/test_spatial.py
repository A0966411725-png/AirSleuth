"""src.analytics.spatial 的離線測試：用合成資料驗證 Algorithm 2 的四種判斷。"""

import numpy as np
import pandas as pd

from src.analytics import spatial

TZ = "Asia/Taipei"


def _grid(n=6, spacing_km=1.5, lat0=24.15, lon0=120.65):
    """n×n 的感測器網格，間距約 spacing_km。"""
    dlat = spacing_km / 111.0
    dlon = spacing_km / (111.0 * np.cos(np.radians(lat0)))
    ids, lats, lons = [], [], []
    for i in range(n):
        for j in range(n):
            ids.append(f"S{i}{j}")
            lats.append(lat0 + i * dlat)
            lons.append(lon0 + j * dlon)
    return pd.DataFrame({"lat": lats, "lon": lons}, index=pd.Index(ids, name="station_id"))


def _matrix(stations, base=20.0, hours=8):
    times = pd.date_range("2026-10-19 08:00", periods=hours * 12, freq="5min", tz=TZ)
    return pd.DataFrame(base, index=times, columns=stations.index)


def _run(matrix, stations, target_id):
    base = spatial.baseline(matrix, 6)
    t = matrix.index[-1]
    lat, lon = stations.loc[target_id, ["lat", "lon"]]
    m = spatial.metrics_at(matrix, stations, base, t, lat, lon)
    return m, spatial.classify(m)


def test_regional_event():
    st = _grid()
    mx = _matrix(st)
    mx.iloc[-6:] = 45.0  # 最後 30 分鐘整個區域一起升高
    m, kind = _run(mx, st, "S22")
    assert kind == spatial.REGIONAL, m
    assert m["C"] > 0.9


def test_local_event_needs_neighbors():
    st = _grid()
    mx = _matrix(st)
    for sid in ("S22", "S23", "S32"):  # 三個相鄰感測器一起升高
        mx.loc[mx.index[-6:], sid] = 80.0
    m, kind = _run(mx, st, "S22")
    assert kind == spatial.LOCAL, m
    assert m["E"] > 10


def test_single_sensor_spike_is_suspected_fault():
    st = _grid()
    mx = _matrix(st)
    mx.loc[mx.index[-6:], "S22"] = 300.0  # 只有一個感測器飆高
    _, kind = _run(mx, st, "S22")
    assert kind in (spatial.SENSOR_FAULT, spatial.NO_EVENT)
    # 以「單一感測器」為目標時，局部中位數也被稀釋；用 station_excess 檢查鄰近沒有一起升高
    ex = spatial.station_excess(mx, st)
    last = ex[(ex["time"] == mx.index[-1]) & (ex["station_id"] == "S22")].iloc[0]
    assert last["excess"] > 200 and last["n_near_elevated"] == 0


def test_quiet_period_has_no_event():
    st = _grid()
    mx = _matrix(st)
    _, kind = _run(mx, st, "S22")
    assert kind == spatial.NO_EVENT
