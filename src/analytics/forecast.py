"""PM2.5 短期預測基準模型（架構模組 ⑤ Analytics Engine；T-11）。

為什麼用多元線性迴歸（MLR）：
- 可解釋：每個係數都能說明（例如「風速越大，下一小時 PM2.5 越低」），符合 AirSleuth「每個結論附證據」的原則
- 輕量：用 numpy 最小平方法即可，不需要額外套件
- 作為基準：之後若要換成更複雜的模型（S-048、S-049 的圖神經網路），先要能贏過這個基準

比較對象：持續性預測（persistence，未來 h 小時 = 現在），空品預測最常用的基準。

輸入：`src.data.moenv.parse_hourly` 的寬表（siteid、time、pm25、rh、temp、wind_speed、wind_dir、rain）。
輸出：預測值、評估指標（MAE、RMSE、新版 AQI 等級的命中率）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 2025 年起新版 AQI 的 PM2.5（24 小時平均）分段上限，見 DESIGN.md 第 7 節（S-029）
AQI_PM25_BOUNDS = [12.4, 30.4, 50.4, 125.4, 225.4]

FEATURES = ["pm25", "pm25_lag1", "pm25_lag2", "pm25_lag3", "pm25_mean6",
            "rh", "temp", "wind_u", "wind_v", "rain", "hour_sin", "hour_cos"]


def aqi_band(pm25) -> np.ndarray:
    """PM2.5 濃度 → 新版 AQI 等級（0 良好、1 普通、2 對敏感族群不健康…）。"""
    return np.searchsorted(AQI_PM25_BOUNDS, np.asarray(pm25, dtype=float), side="left")


def build_features(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """依測站建立特徵與 horizon 小時後的目標值。

    時間先補齊成連續的每小時，避免缺一小時時 lag 對錯位置；有缺值的列在訓練前丟掉。
    風向（氣象慣例：風「吹來」的方向）轉成 u、v 分量，避免 359° 與 1° 被當成相差很遠。
    """
    parts = []
    for siteid, g in df.sort_values("time").groupby("siteid"):
        g = g.set_index("time")
        full = pd.date_range(g.index.min(), g.index.max(), freq="h")
        g = g.reindex(full)
        out = pd.DataFrame(index=full)
        out["siteid"] = siteid
        out["pm25"] = g["pm25"]
        for k in (1, 2, 3):
            out[f"pm25_lag{k}"] = g["pm25"].shift(k)
        out["pm25_mean6"] = g["pm25"].rolling(6, min_periods=4).mean()
        out["rh"], out["temp"], out["rain"] = g["rh"], g["temp"], g["rain"]
        rad = np.radians(g["wind_dir"])
        out["wind_u"] = -g["wind_speed"] * np.sin(rad)
        out["wind_v"] = -g["wind_speed"] * np.cos(rad)
        hour = full.hour
        out["hour_sin"], out["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
        out["target"] = g["pm25"].shift(-horizon)
        parts.append(out)
    feats = pd.concat(parts)
    feats.index.name = "time"
    return feats.reset_index()


class MLR:
    """多元線性迴歸（含截距），以 numpy 最小平方法求解。"""

    def __init__(self, features: list[str] = FEATURES):
        self.features = features
        self.coef_: np.ndarray | None = None

    def _design(self, X: pd.DataFrame) -> np.ndarray:
        return np.column_stack([np.ones(len(X)), X[self.features].to_numpy(dtype=float)])

    def fit(self, X: pd.DataFrame, y) -> "MLR":
        self.coef_, *_ = np.linalg.lstsq(self._design(X), np.asarray(y, dtype=float), rcond=None)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.clip(self._design(X) @ self.coef_, 0, None)  # 濃度不會是負的

    def coefficients(self) -> pd.Series:
        return pd.Series(self.coef_, index=["intercept"] + self.features)


def split_by_time(feats: pd.DataFrame, test_fraction: float = 0.25):
    """依時間切分訓練與測試（不能隨機切，否則等於偷看未來）。"""
    cut = feats["time"].quantile(1 - test_fraction)
    return feats[feats["time"] < cut], feats[feats["time"] >= cut], cut


def metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = y_pred - y_true
    return {"MAE": float(np.mean(np.abs(err))), "RMSE": float(np.sqrt(np.mean(err ** 2))),
            "AQI_hit": float(np.mean(aqi_band(y_true) == aqi_band(y_pred))), "n": int(len(y_true))}


def evaluate(df: pd.DataFrame, horizons=(1, 3, 6), test_fraction: float = 0.25) -> pd.DataFrame:
    """對每個預測時距，比較持續性預測與 MLR 在測試期的表現。"""
    rows = []
    for h in horizons:
        feats = build_features(df, h).dropna(subset=FEATURES + ["target"])
        train, test, cut = split_by_time(feats, test_fraction)
        model = MLR().fit(train, train["target"])
        for name, pred in (("persistence", test["pm25"]), ("MLR", model.predict(test))):
            rows.append({"horizon_h": h, "model": name, "test_start": cut, **metrics(test["target"], pred)})
    return pd.DataFrame(rows)
