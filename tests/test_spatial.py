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
            ids.append(f"S{i}{j}" if n <= 10 else f"S{i:02d}{j:02d}")
            lats.append(lat0 + i * dlat)
            lons.append(lon0 + j * dlon)
    return pd.DataFrame({"lat": lats, "lon": lons}, index=pd.Index(ids, name="station_id"))


def _matrix(stations, base=20.0, hours=8):
    times = pd.date_range("2026-10-19 08:00", periods=hours * 12, freq="5min", tz=TZ)
    return pd.DataFrame(base, index=times, columns=stations.index)


def _run(matrix, stations, target_id, p=spatial.Params()):
    base = spatial.baseline(matrix, 6)
    t = matrix.index[-1]
    lat, lon = stations.loc[target_id, ["lat", "lon"]]
    m = spatial.metrics_at(matrix, stations, base, t, lat, lon, p)
    return m, spatial.classify(m, p)


def _subregional_case(radius_km=6.0):
    """約 22 km 見方的網格，中心 radius_km 內的感測器一起升高，外圍不變（模擬 T-20 的沿海群聚）。"""
    st = _grid(n=16, spacing_km=1.5)
    mx = _matrix(st)
    c = st.loc["S0808"]
    d = spatial.haversine_km(c["lat"], c["lon"], st["lat"].to_numpy(), st["lon"].to_numpy())
    mx.loc[mx.index[-6:], st.index[d <= radius_km]] = 40.0
    return st, mx


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


def test_subregional_event():
    st, mx = _subregional_case()
    m, kind = _run(mx, st, "S0808")
    assert kind == spatial.SUBREGIONAL, m
    assert m["C_sub"] >= 0.3 and m["C_ring"] < 0.3 and m["C"] < 0.6


def test_two_tier_mode_calls_subregional_event_local():
    """r_sub_km=None 回到原本兩層判斷：同一個約 6 km 的群聚只能被判為局部型（T-20 指出的尺度問題）。"""
    st, mx = _subregional_case()
    m, kind = _run(mx, st, "S0808", spatial.Params(r_sub_km=None))
    assert kind == spatial.LOCAL, m
    assert "C_sub" not in m


def test_small_cluster_is_not_subregional():
    st = _grid(n=16, spacing_km=1.5)
    mx = _matrix(st)
    for sid in ("S0808", "S0809", "S0908"):  # 只有三個相鄰感測器升高
        mx.loc[mx.index[-6:], sid] = 80.0
    m, kind = _run(mx, st, "S0808")
    assert kind == spatial.LOCAL, m
    assert m["C_sub"] < 0.3


def test_coherence_scan_matches_metrics_at():
    st, mx = _subregional_case()
    base = spatial.baseline(mx, 6)
    sc = spatial.coherence_scan(mx, st, base)
    t = mx.index[-1]
    lat, lon = st.loc["S0808", ["lat", "lon"]]
    m = spatial.metrics_at(mx, st, base, t, lat, lon)
    for k in ("C", "C_sub", "C_ring"):
        assert abs(sc[k].loc[t, "S0808"] - m[k]) < 1e-9, k
    assert sc["n_sub"].loc[t, "S0808"] == m["n_sub"]
