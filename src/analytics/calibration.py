"""微型感測器與國家測站的共置比對與初步校正（架構模組 ⑤ Analytics Engine；T-22）。

做法（S-008、S-009 的共置校正概念）：
1. 共置：國家測站半徑 radius_km 內的微型感測器，先各自算小時平均，再取中位數（降低單一感測器的影響）
2. 比對：微型感測器 vs 國家測站的同一小時 PM2.5
3. 校正：線性迴歸 ref = a + b·raw，以及加入濕度的 ref = a + b·raw + c·RH；
   用「留一站交叉驗證」評估，避免同一站的資料同時出現在訓練與測試

濕度來源（T-20 發現臺中微型感測器自己回報的濕度不可靠）：
- 國家測站的濕度（與 PM2.5 同一地點）
- 最近的中央氣象署自動氣象站濕度
- 微型感測器自己回報的濕度（只用來比較，不用於校正）

輸入：`src.data.colife` 的 5 分鐘長表、`src.data.moenv.parse_hourly` 的寬表、`src.data.cwa` 的觀測表。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.spatial import haversine_km, usable


def hourly_sensor_means(colife: pd.DataFrame, label: str = "end") -> pd.DataFrame:
    """把 5 分鐘資料轉成每個感測器的小時平均。

    label="end"：13:00 代表 12:00～12:59（整點結束）；label="start"：13:00 代表 13:00～13:59。
    兩種都提供，因為國家測站小時值的時間標記慣例要用資料確認（見 `best_alignment`）。
    一小時至少要有 6 個 5 分鐘區間才計算。
    """
    df = usable(colife)
    t = df["time"].dt.floor("h")
    if label == "end":
        t = t + pd.Timedelta(hours=1)
    df = df.assign(hour=t)
    g = df.groupby(["station_id", "hour"])
    out = g.agg(pm25=("pm25", "mean"), rh=("rh", lambda s: s[s.between(0, 100, inclusive="right")].mean()),
                n=("pm25", "size")).reset_index()
    out = out[out["n"] >= 6].drop(columns="n").rename(columns={"hour": "time"})
    pos = colife.drop_duplicates("station_id").set_index("station_id")[["lon", "lat"]]
    return out.join(pos, on="station_id")


def collocate(sensor_hourly: pd.DataFrame, stations: pd.DataFrame, radius_km: float = 1.0,
              min_sensors: int = 2) -> pd.DataFrame:
    """每個國家測站、每小時：半徑內微型感測器的 PM2.5 中位數與濕度中位數。

    stations：國家測站寬表（siteid、sitename、lon、lat、time、pm25、rh…）。
    """
    pos = sensor_hourly.drop_duplicates("station_id")
    rows = []
    for site, s in stations.groupby("siteid"):
        lat, lon = s["lat"].iloc[0], s["lon"].iloc[0]
        d = haversine_km(lat, lon, pos["lat"].to_numpy(), pos["lon"].to_numpy())
        near = set(pos["station_id"].to_numpy()[d <= radius_km])
        if len(near) < min_sensors:
            continue
        sub = sensor_hourly[sensor_hourly["station_id"].isin(near)]
        agg = sub.groupby("time").agg(sensor_pm25=("pm25", "median"), sensor_rh=("rh", "median"),
                                      n_sensors=("pm25", "size")).reset_index()
        agg = agg[agg["n_sensors"] >= min_sensors]
        ref = s[["time", "siteid", "sitename", "pm25", "rh", "lat", "lon"]].rename(
            columns={"pm25": "ref_pm25", "rh": "station_rh"})
        rows.append(ref.merge(agg, on="time"))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).dropna(subset=["ref_pm25", "sensor_pm25"])


def best_alignment(colife: pd.DataFrame, stations: pd.DataFrame, radius_km: float = 1.0) -> pd.DataFrame:
    """比較兩種小時標記慣例下，微型感測器與測站的相關係數與 MAE。"""
    rows = []
    for label in ("end", "start"):
        pairs = collocate(hourly_sensor_means(colife, label), stations, radius_km)
        rows.append({"label": label, "n_pairs": len(pairs),
                     "r": pairs["sensor_pm25"].corr(pairs["ref_pm25"]),
                     "MAE": (pairs["sensor_pm25"] - pairs["ref_pm25"]).abs().mean()})
    return pd.DataFrame(rows)


def nearest_weather(points: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """每個點（siteid、lat、lon）最近的氣象站：station_id、距離。"""
    w = weather.drop_duplicates("station_id")
    out = []
    for _, p in points.drop_duplicates("siteid").iterrows():
        d = haversine_km(p["lat"], p["lon"], w["lat"].to_numpy(), w["lon"].to_numpy())
        i = int(np.argmin(d))
        out.append({"siteid": p["siteid"], "cwa_id": w["station_id"].iloc[i],
                    "cwa_name": w["station_name"].iloc[i], "cwa_km": float(d[i])})
    return pd.DataFrame(out)


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def fit(pairs: pd.DataFrame, features: list[str]) -> pd.Series:
    """ref_pm25 = a + Σ b_i·feature_i 的係數。"""
    coef = _ols(pairs[features].to_numpy(dtype=float), pairs["ref_pm25"].to_numpy(dtype=float))
    return pd.Series(coef, index=["intercept"] + features)


def leave_one_site_out(pairs: pd.DataFrame, models: dict[str, list[str]]) -> pd.DataFrame:
    """留一站交叉驗證：每次拿掉一個測站當測試，其餘訓練。回傳各模型的 MAE、RMSE、平均偏差。

    models：名稱 → 特徵清單；空清單代表不校正（直接用 sensor_pm25）。
    """
    preds = {name: pd.Series(np.nan, index=pairs.index) for name in models}
    for site in pairs["siteid"].unique():
        test = pairs["siteid"] == site
        train = pairs[~test]
        for name, feats in models.items():
            if not feats:
                preds[name][test] = pairs.loc[test, "sensor_pm25"]
                continue
            sub = train.dropna(subset=feats)
            ok = test & pairs[feats].notna().all(axis=1)
            if len(sub) < len(feats) + 3 or not ok.any():
                continue
            c = _ols(sub[feats].to_numpy(dtype=float), sub["ref_pm25"].to_numpy(dtype=float))
            preds[name][ok] = c[0] + pairs.loc[ok, feats].to_numpy(dtype=float) @ c[1:]
    rows = []
    for name, p in preds.items():
        err = (p - pairs["ref_pm25"]).dropna()
        rows.append({"model": name, "n": len(err), "MAE": err.abs().mean(),
                     "RMSE": float(np.sqrt((err ** 2).mean())), "bias": err.mean()})
    return pd.DataFrame(rows)
