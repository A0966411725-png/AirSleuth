"""Agent 的工具（架構模組 ④⑤⑥ 的確定性函式），讀取排程收集的本地資料。

LLM 只負責決定「呼叫哪個工具、帶什麼參數」與解釋結果；所有數字都由這些函式算出來（設計原則 P1）。
每個工具回傳 dict，可以直接序列化成 JSON 交給 LLM，也會被記錄在回答的追溯紀錄裡。
工具的 JSON 規格（function calling 用）見 `src/agent/schema.py`。

資料來源：`data/raw/{colife,moenv,cwa}/<縣市>/YYYY-MM-DD.csv.gz`（`scripts/collect_scheduled.py` 每小時收集）。
時間一律是台灣時間；查詢時間 t 只會用到 t 之前已經存在的資料（例如國家測站只用到上一個完整小時），
所以拿歷史時間點來重跑，結果和當時即時查詢會得到的一樣。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics import forecast as fc
from src.analytics import spatial as sp
from src.data import quality
from src.knowledge import health

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data" / "raw"
TZ = "Asia/Taipei"

# T-22 以 5 天共置資料估計的「線性＋濕度」校正係數：ref = a + b·sensor + c·RH（濕度用最近氣象站）
CALIBRATION = {
    "臺中市": {"intercept": 3.212, "sensor": 1.101, "rh": -0.105},
    "高雄市": {"intercept": 5.445, "sensor": 1.226, "rh": -0.095},
}


def _ts(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize(TZ) if t.tzinfo is None else t.tz_convert(TZ)


def _read(source: str, city: str, start: pd.Timestamp, end: pd.Timestamp, root: Path, key: str) -> pd.DataFrame:
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    files = [root / source / city / f"{d:%Y-%m-%d}.csv.gz" for d in days]
    parts = [pd.read_csv(f, dtype={key: str}) for f in files if f.exists()]
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    df = df.drop_duplicates([key, "time"])
    return df[(df["time"] >= start) & (df["time"] <= end)].reset_index(drop=True)


def _nearest(df: pd.DataFrame, key: str, lat: float, lon: float) -> tuple[str, float]:
    pos = df.drop_duplicates(key)
    d = sp.haversine_km(lat, lon, pos["lat"].to_numpy(), pos["lon"].to_numpy())
    i = int(np.argmin(d))
    return pos[key].iloc[i], float(d[i])


def get_microsensors(city: str, time, lat: float, lon: float, radius_km: float = 15.0,
                     hours: float = 7.0, root: Path = DATA_ROOT) -> dict:
    """④ 取得目標位置 radius_km 內、查詢時間前 hours 小時的微型感測器 5 分鐘資料。"""
    t = _ts(time)
    df = _read("colife", city, t - pd.Timedelta(hours=hours), t, root, "station_id")
    if df.empty:
        return {"ok": False, "reason": "本地資料庫沒有這段時間的微型感測器資料", "data": df}
    pos = df.drop_duplicates("station_id")
    d = pd.Series(sp.haversine_km(lat, lon, pos["lat"].to_numpy(), pos["lon"].to_numpy()), index=pos["station_id"])
    df = df[df["station_id"].isin(d.index[d <= radius_km])]
    latest = df["time"].max() if len(df) else None
    stale_min = (t - latest).total_seconds() / 60 if latest is not None else None
    return {"ok": len(df) > 0, "n_sensors": int(df["station_id"].nunique()), "radius_km": radius_km,
            "latest_time": str(latest), "stale_minutes": stale_min, "data": df}


def assess_quality(data: pd.DataFrame) -> dict:
    """④ 資料品質檢查：各品質旗標的比例（`src/data/quality.py`）。"""
    flagged = quality.flag(data)
    counts = flagged["qc_flag"].value_counts(normalize=True)
    usable_ratio = float(counts.get("ok", 0) + counts.get("rh_invalid", 0))
    return {"rows": int(len(flagged)), "usable_ratio": round(usable_ratio, 3),
            "rh_invalid_ratio": round(float(counts.get("rh_invalid", 0)), 3),
            "excluded_ratio": round(1 - usable_ratio, 3)}


def get_station(city: str, time, lat: float, lon: float, root: Path = DATA_ROOT) -> dict:
    """④ 最近的國家測站在上一個完整小時的 PM2.5（測站小時值 13:00 代表 13:00～13:59，T-22）。"""
    t = _ts(time)
    hour = t.floor("h") - pd.Timedelta(hours=1)
    df = _read("moenv", city, hour - pd.Timedelta(hours=6), hour, root, "siteid")
    if df.empty:
        return {"ok": False, "reason": "沒有國家測站資料"}
    siteid, km = _nearest(df, "siteid", lat, lon)
    s = df[df["siteid"] == siteid].sort_values("time")
    row = s.iloc[-1]
    return {"ok": True, "siteid": siteid, "sitename": row["sitename"], "distance_km": round(km, 1),
            "time": str(row["time"]), "pm25": float(row["pm25"]), "rh": float(row["rh"]),
            "wind_speed": float(row["wind_speed"]), "wind_dir": float(row["wind_dir"])}


def get_weather(city: str, time, lat: float, lon: float, root: Path = DATA_ROOT) -> dict:
    """④ 最近的中央氣象署自動氣象站在查詢時間前的最新觀測。"""
    t = _ts(time)
    df = _read("cwa", city, t - pd.Timedelta(hours=3), t, root, "station_id")
    if df.empty:
        return {"ok": False, "reason": "沒有氣象站資料"}
    sid, km = _nearest(df, "station_id", lat, lon)
    row = df[df["station_id"] == sid].sort_values("time").iloc[-1]
    return {"ok": True, "station_id": sid, "station_name": row["station_name"], "distance_km": round(km, 1),
            "time": str(row["time"]), "wind_dir": row["wind_dir"], "wind_speed": row["wind_speed"],
            "rh": row["rh"], "temp": row["temp"]}


def source_attribution(data: pd.DataFrame, time, lat: float, lon: float, p: sp.Params = sp.Params()) -> dict:
    """⑤ Algorithm 2：區域背景 B、局部濃度 L、局部超量 E、空間一致性 C 與來源類型。"""
    t = _ts(time)
    matrix, stations = sp.to_matrix(sp.usable(data))
    if matrix.empty:
        return {"type": sp.INSUFFICIENT}
    t_used = matrix.index[matrix.index <= t].max()
    base = sp.baseline(matrix, p.baseline_hours)
    m = sp.metrics_at(matrix, stations, base, t_used, lat, lon, p)
    out = {k: (round(float(v), 2) if isinstance(v, (float, np.floating)) and not np.isnan(v) else v)
           for k, v in m.items() if k != "time"}
    return {**out, "time": str(t_used), "type": sp.classify(m, p)}


def forecast_trend(city: str, time, lat: float, lon: float, horizons=(1, 3, 6), root: Path = DATA_ROOT) -> dict:
    """⑤ 以最近國家測站在查詢時間之前的資料訓練多元線性迴歸，預測未來 1～6 小時（T-11 的基準模型）。"""
    t = _ts(time)
    hour = t.floor("h") - pd.Timedelta(hours=1)
    hist = _read("moenv", city, hour - pd.Timedelta(days=60), hour, root, "siteid")
    if hist.empty:
        return {"ok": False, "reason": "沒有測站歷史資料"}
    siteid, _ = _nearest(hist, "siteid", lat, lon)
    hist = hist[hist["siteid"] == siteid]
    preds = {}
    for h in horizons:
        feats = fc.build_features(hist, h)
        train = feats.dropna(subset=fc.FEATURES + ["target"])
        train = train[train["time"] <= hour - pd.Timedelta(hours=h)]   # 目標值也必須在查詢時間之前
        now = feats[feats["time"] == hour].dropna(subset=fc.FEATURES)
        if len(train) < 50 or now.empty:
            continue
        model = fc.MLR().fit(train, train["target"])
        preds[h] = round(float(model.predict(now)[0]), 1)
    if not preds:
        return {"ok": False, "reason": "資料不足，無法預測"}
    current = float(hist.loc[hist["time"] == hour, "pm25"].iloc[0])
    return {"ok": True, "siteid": siteid, "base_time": str(hour), "station_now": current, "forecast": preds}


def calibrate(city: str, sensor_pm25: float, rh: float | None) -> dict:
    """⑤ 以 T-22 的在地係數校正微型感測器讀數；沒有係數或濕度時回傳原值並註明。"""
    c = CALIBRATION.get(city)
    if c is None or rh is None or np.isnan(rh):
        return {"calibrated": False, "pm25": round(float(sensor_pm25), 1), "note": "沒有在地校正係數或濕度，使用原始讀數"}
    value = c["intercept"] + c["sensor"] * sensor_pm25 + c["rh"] * rh
    return {"calibrated": True, "pm25": round(max(value, 0.0), 1),
            "note": f"T-22 在地校正（{city}，線性＋氣象站濕度 {rh:.0f}%）"}


def retrieve_knowledge(group: str, activity: str, src_type: str) -> dict:
    """⑥ 取出與這次問題相關的領域規則與依據。"""
    keys = ["aqi_2025", "exposure", "exercise" if activity != "rest" else "no_threshold"]
    if group in health.SENSITIVE_GROUPS:
        keys.append("sensitive")
    if src_type in ("local", "subregional", "regional"):
        keys.append("shift_place")
    return {"rules": [health.RULES[k] for k in keys]}
