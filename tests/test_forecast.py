"""src.analytics.forecast 的離線測試。"""

import numpy as np
import pandas as pd

from src.analytics import forecast as fc


def _series(n=200, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-09-01", periods=n, freq="h", tz="Asia/Taipei")
    pm = 15 + 5 * np.sin(np.arange(n) / 6) + rng.normal(0, 0.5, n)
    return pd.DataFrame({"siteid": "1", "time": t, "pm25": pm, "rh": 70.0, "temp": 28.0,
                         "wind_speed": 2.0, "wind_dir": 90.0, "rain": 0.0})


def test_aqi_band_uses_2025_thresholds():
    assert list(fc.aqi_band([0, 12.4, 12.5, 30.4, 30.5, 60])) == [0, 0, 1, 1, 2, 3]


def test_features_align_lags_and_target_after_gap():
    df = _series(30)
    df = df.drop(index=10)  # 少一小時：lag 與 target 不能錯位
    f = fc.build_features(df, horizon=1).set_index("time")
    t9, t11 = df.loc[9, "time"], df.loc[11, "time"]
    assert np.isnan(f.loc[t9, "target"])          # t9 的下一小時缺值
    assert np.isnan(f.loc[t11, "pm25_lag1"])      # t11 的前一小時缺值
    assert f.loc[t11, "pm25_lag2"] == df.loc[9, "pm25"]


def test_wind_components_from_direction():
    df = _series(10)
    df["wind_dir"], df["wind_speed"] = 90.0, 2.0  # 東風：從東邊吹來，往西走
    f = fc.build_features(df, 1)
    assert np.allclose(f["wind_u"], -2.0) and np.allclose(f["wind_v"], 0.0, atol=1e-9)


def test_mlr_beats_persistence_on_smooth_signal():
    res = fc.evaluate(_series(400), horizons=(3,))
    mae = res.set_index("model")["MAE"]
    assert mae["MLR"] < mae["persistence"]
