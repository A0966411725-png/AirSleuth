"""空間型態分析與來源判斷（架構模組 ⑤ Analytics Engine；Algorithm 2）。

核心概念（見 proposal/04_proposed_scheme.md 4.4 節）：
    區域背景 B  = 半徑 r_region 內可信感測器的 PM2.5 中位數
    局部濃度 L  = 目標點半徑 r_local 內的中位數
    局部超量 E  = L − B
    空間一致性 C = 區域內「比自己前 baseline_hours 小時中位數升高超過 rise」的感測器比例

輸入：`src.data.colife.aggregate` 產生的長表（station_id、lon、lat、time、pm25、rh…）。
輸出：每個時間點、每個目標位置的指標與來源類型。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data import quality

EARTH_RADIUS_KM = 6371.0

REGIONAL = "regional"
LOCAL = "local"
MIXED = "mixed"
SENSOR_FAULT = "suspected_sensor_fault"
NO_EVENT = "no_clear_event"
INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class Params:
    """來源判斷的參數。預設值是 DESIGN.md 第 8 節的初始值，T-20 用真實資料校準。"""
    r_local_km: float = 2.0
    r_region_km: float = 15.0
    min_sensors: int = 5
    baseline_hours: float = 6.0
    rise_ratio: float = 0.5        # 比自己基準高 50% 算「升高」
    coherence_high: float = 0.6
    coherence_low: float = 0.3
    regional_excess_abs: float = 5.0
    regional_excess_rel: float = 0.3
    local_excess_abs: float = 10.0
    local_excess_rel: float = 0.5
    min_local_elevated: int = 2


def haversine_km(lat1, lon1, lat2, lon2):
    """兩點（可為陣列）之間的大圓距離，單位公里。"""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def usable(df: pd.DataFrame) -> pd.DataFrame:
    """依品質旗標保留可用於 PM2.5 空間分析的列。

    濕度無效（rh_invalid）只影響濕度欄位，PM2.5 仍保留；缺值、負值、極端值、卡住則排除。
    """
    flagged = quality.flag(df)
    keep = flagged["qc_flag"].isin(["ok", "rh_invalid"])
    return flagged.loc[keep].copy()


def to_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """轉成「時間 × 感測器」的 PM2.5 矩陣，以及感測器座標表。"""
    matrix = df.pivot_table(index="time", columns="station_id", values="pm25", aggfunc="mean").sort_index()
    stations = (df.drop_duplicates("station_id").set_index("station_id")[["lon", "lat"]]
                .reindex(matrix.columns))
    return matrix, stations


def baseline(matrix: pd.DataFrame, hours: float) -> pd.DataFrame:
    """每個感測器在每個時間點「之前」hours 小時的中位數（不含當下）。"""
    return matrix.shift(1).rolling(f"{int(hours * 60)}min", min_periods=3).median()


def metrics_at(matrix: pd.DataFrame, stations: pd.DataFrame, base: pd.DataFrame,
               t, lat: float, lon: float, p: Params = Params()) -> dict:
    """計算一個時間點、一個目標位置的 B、L、E、C。"""
    dist = pd.Series(haversine_km(lat, lon, stations["lat"].to_numpy(), stations["lon"].to_numpy()),
                     index=stations.index)
    now = matrix.loc[t]
    region_ids = dist.index[(dist <= p.r_region_km) & now.notna()]
    local_ids = dist.index[(dist <= p.r_local_km) & now.notna()]
    out = {"time": t, "n_region": len(region_ids), "n_local": len(local_ids)}
    if len(region_ids) < p.min_sensors or len(local_ids) == 0:
        return {**out, "B": np.nan, "L": np.nan, "E": np.nan, "C": np.nan, "n_local_elevated": 0}

    B = float(now[region_ids].median())
    L = float(now[local_ids].median())
    E = L - B
    b = base.loc[t, region_ids]
    rising = ((now[region_ids] - b) / b) > p.rise_ratio
    C = float(rising[b.notna()].mean()) if b.notna().any() else np.nan
    n_local_elevated = int((now[local_ids] > B + max(E, 0) / 2).sum()) if E > 0 else 0
    return {**out, "B": B, "L": L, "E": E, "C": C, "n_local_elevated": n_local_elevated}


def classify(m: dict, p: Params = Params()) -> str:
    """依 Algorithm 2 的規則判斷來源類型。"""
    if np.isnan(m.get("B", np.nan)) or np.isnan(m.get("C", np.nan)):
        return INSUFFICIENT
    B, E, C = m["B"], m["E"], m["C"]
    small_excess = E < max(p.regional_excess_abs, p.regional_excess_rel * B)
    large_excess = E >= max(p.local_excess_abs, p.local_excess_rel * B)
    if C >= p.coherence_high and small_excess:
        return REGIONAL
    if large_excess and C < p.coherence_low:
        return LOCAL if m["n_local_elevated"] >= p.min_local_elevated else SENSOR_FAULT
    if C >= p.coherence_high and large_excess:
        return MIXED
    return NO_EVENT


def station_excess(matrix: pd.DataFrame, stations: pd.DataFrame, p: Params = Params()) -> pd.DataFrame:
    """對每個感測器、每個時間點計算「自己 − 區域背景」與鄰近一起升高的感測器數。

    用來在整個城市中找出候選的局部事件。回傳長表：time、station_id、pm25、B、excess、n_near_elevated。
    """
    lat = stations["lat"].to_numpy()
    lon = stations["lon"].to_numpy()
    dist = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    region = dist <= p.r_region_km
    near = (dist <= p.r_local_km) & (dist > 0)

    values = matrix.to_numpy()
    rows = []
    for i, t in enumerate(matrix.index):
        v = values[i]
        valid = ~np.isnan(v)
        masked = np.where(region & valid[None, :], v[None, :], np.nan)
        B = np.nanmedian(masked, axis=1)
        n_region = (region & valid[None, :]).sum(axis=1)
        excess = v - B
        threshold = B + np.maximum(excess, 0) / 2
        near_elevated = ((near & valid[None, :]) & (v[None, :] > threshold[:, None])).sum(axis=1)
        rows.append(pd.DataFrame({"time": t, "station_id": matrix.columns, "pm25": v, "B": B,
                                  "excess": excess, "n_region": n_region,
                                  "n_near_elevated": near_elevated}))
    out = pd.concat(rows, ignore_index=True)
    return out[out["pm25"].notna() & (out["n_region"] >= p.min_sensors)]


def label_station_events(ex: pd.DataFrame, base: pd.DataFrame, p: Params = Params(),
                         persistent_share: float = 0.8) -> pd.DataFrame:
    """把 station_excess 的結果分成三種型態（T-20 實測後加入）：

    - local_event：高於區域背景，而且比自己過去的基準升高（暫時性），並有鄰近感測器一起升高
    - single_spike：同上，但只有自己升高 → 疑似感測器異常或極近距離干擾
    - persistent_high：在 persistent_share 以上的時間都高於區域背景 → 長期熱點或感測器偏差，不算「事件」

    參考 S-045 把訊號分成「短期事件」與「相對區域背景的持續性偏高」。
    """
    b = base.stack().rename("own_base").reset_index()
    b.columns = ["time", "station_id", "own_base"]
    out = ex.merge(b, on=["time", "station_id"], how="left")
    above = out["excess"] >= np.maximum(p.local_excess_abs, p.local_excess_rel * out["B"])
    rising = out["pm25"] >= (1 + p.rise_ratio) * out["own_base"]
    share_above = above.groupby(out["station_id"]).transform("mean")

    out["pattern"] = "normal"
    out.loc[above, "pattern"] = "above_background"
    out.loc[above & (share_above >= persistent_share), "pattern"] = "persistent_high"
    event = above & rising & (share_above < persistent_share)
    out.loc[event & (out["n_near_elevated"] >= p.min_local_elevated - 1), "pattern"] = "local_event"
    out.loc[event & (out["n_near_elevated"] == 0), "pattern"] = "single_spike"
    return out


def city_coherence(matrix: pd.DataFrame, base: pd.DataFrame, p: Params = Params()) -> pd.Series:
    """整個城市每個時間點的空間一致性：比自己基準升高超過 rise_ratio 的感測器比例。"""
    rising = (matrix - base) / base > p.rise_ratio
    valid = matrix.notna() & base.notna()
    return (rising & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)
