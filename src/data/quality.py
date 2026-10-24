"""微型感測器資料品質檢查（架構模組 ④ 的前處理）。

輸入：`src.data.colife.aggregate` 產生的長表（每列是一個感測器在一個時間區間）。
輸出：每列加上 `qc_flag`（"ok" 或問題代碼），以及整體品質摘要。

問題代碼：
- pm25_missing：該區間沒有 PM2.5
- pm25_negative：PM2.5 小於 0
- pm25_extreme：PM2.5 超過 `PM25_MAX`，以微型感測器而言多半是故障或局部極端干擾
- rh_invalid：相對濕度不在 (0, 100] 之間（常見是回報 0）
- stuck：同一感測器連續 `STUCK_RUN` 個區間 PM2.5 完全相同，可能是感測器卡住
"""

from __future__ import annotations

import pandas as pd

PM25_MAX = 500.0
STUCK_RUN = 12  # 5 分鐘區間 × 12 = 1 小時


def _stuck_mask(df: pd.DataFrame) -> pd.Series:
    """標出 PM2.5 連續 STUCK_RUN 個區間以上數值完全不變的列。"""
    ordered = df.sort_values(["station_id", "time"])
    changed = ordered.groupby("station_id")["pm25"].transform(lambda s: s.ne(s.shift()).cumsum())
    run_length = ordered.groupby(["station_id", changed])["pm25"].transform("size")
    return (run_length >= STUCK_RUN).reindex(df.index)


def flag(df: pd.DataFrame) -> pd.DataFrame:
    """回傳加上 qc_flag 欄位的副本。一列有多個問題時，取最先符合的那一個。

    索引會重設為 0..n-1：多個日檔合併後索引可能重複，重複索引會讓卡住偵測對錯列。
    """
    out = df.reset_index(drop=True)
    rules = [
        ("pm25_missing", out["pm25"].isna()),
        ("pm25_negative", out["pm25"] < 0),
        ("pm25_extreme", out["pm25"] > PM25_MAX),
        ("stuck", _stuck_mask(out)),
        ("rh_invalid", ~out["rh"].between(0, 100, inclusive="right")),
    ]
    out["qc_flag"] = "ok"
    for name, mask in reversed(rules):  # 倒序覆寫，讓排在前面的規則優先
        out.loc[mask.fillna(False).astype(bool), "qc_flag"] = name
    return out


def summary(flagged: pd.DataFrame, registered_sensors: int | None = None) -> dict:
    """整體品質摘要：各問題的列數比例，以及受影響的感測器數。"""
    total = len(flagged)
    result = {
        "rows": total,
        "active_sensors": int(flagged["station_id"].nunique()),
        "time_start": str(flagged["time"].min()),
        "time_end": str(flagged["time"].max()),
    }
    if registered_sensors:
        result["registered_sensors"] = registered_sensors
        result["active_ratio"] = round(result["active_sensors"] / registered_sensors, 3)
    counts = flagged["qc_flag"].value_counts()
    for name in ("ok", "pm25_missing", "pm25_negative", "pm25_extreme", "stuck", "rh_invalid"):
        n = int(counts.get(name, 0))
        sensors = int(flagged.loc[flagged["qc_flag"] == name, "station_id"].nunique())
        result[name] = {"rows": n, "ratio": round(n / total, 4) if total else 0.0, "sensors": sensors}
    return result
