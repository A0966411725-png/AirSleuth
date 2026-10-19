"""從國家測站歷史資料找「區域型事件」候選（架構模組 ⑤ Analytics Engine；T-21）。

T-20 只有單日微型感測器資料，沒遇到區域型事件，Algorithm 2 的區域型規則（C ≥ 0.6）無從驗證。
國家測站有 60 天以上的小時資料，可以先在測站尺度找出「多站同時升高」的日子與時段，
作為之後用微型感測器驗證區域型判斷的候選事件。

概念與 `spatial.py` 一致：
    升高    = 測站 PM2.5 比自己「之前」一段時間的中位數高 rise_ratio 以上，且至少高 min_abs_rise
              （不含當下，避免偷看；絕對門檻是 T-21 實測後加入，見 reports/T-21.md）
    一致性 C = 同一時間升高的測站比例
    區域型候選 = C ≥ coherence_high 且測站之間差異小（變異係數 CV ≤ max_cv）
    局部型候選 = 單一測站明顯高於其他測站中位數，而且 C < coherence_low

輸入：`src.data.moenv.parse_hourly` 的寬表（siteid、time、pm25…）。
注意：這裡只描述空間型態，**不判斷成因**（境外、天氣或本地排放需要其他證據）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegionalParams:
    rise_ratio: float = 0.5          # 與 spatial.Params 相同：比自己基準高 50% 算升高
    min_abs_rise: float = 5.0        # 同時至少高 5 μg/m³（同 regional_excess_abs），避免低濃度日的小波動被放大
    coherence_high: float = 0.8      # 測站很少（臺中 6 站），用比微型感測器嚴格的門檻
    coherence_low: float = 0.3
    max_cv: float = 0.25             # 測站間變異係數上限：區域型應該「大家差不多高」
    baseline_days: int = 14          # 日尺度基準：前 14 天日平均的中位數
    min_baseline_days: int = 7
    baseline_hours: int = 168        # 時尺度基準：前 7 天的中位數
    min_hours_per_day: int = 18      # 一天至少 18 小時有值才算日平均
    min_episode_hours: int = 6       # 連續 6 小時以上才算一段區域型時段
    local_excess_abs: float = 10.0   # 與 spatial.Params 相同
    local_excess_rel: float = 0.5


def hourly_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """時間 × 測站的 PM2.5 矩陣，時間補成連續每小時。"""
    m = df.pivot_table(index="time", columns="siteid", values="pm25", aggfunc="mean").sort_index()
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="h"))


def daily_matrix(hourly: pd.DataFrame, p: RegionalParams = RegionalParams()) -> pd.DataFrame:
    """日期 × 測站的日平均；當天有效小時數不足的設為缺值。"""
    day = hourly.index.normalize()
    mean = hourly.groupby(day).mean()
    count = hourly.notna().groupby(day).sum()
    return mean.where(count >= p.min_hours_per_day)


def coherence(matrix: pd.DataFrame, base: pd.DataFrame, rise_ratio: float, min_abs_rise: float = 0.0) -> pd.Series:
    """每個時間點升高的測站比例（分母只算有基準、有值的測站）。"""
    valid = matrix.notna() & base.notna()
    rising = ((matrix - base) / base > rise_ratio) & (matrix - base >= min_abs_rise) & valid
    return rising.sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def spatial_cv(matrix: pd.DataFrame) -> pd.Series:
    """每個時間點測站之間的變異係數（標準差 / 平均）。"""
    return matrix.std(axis=1) / matrix.mean(axis=1)


def daily_candidates(hourly: pd.DataFrame, p: RegionalParams = RegionalParams()) -> pd.DataFrame:
    """每天一列：城市平均、最小、最大、升高比例 C、CV，以及是否為區域型候選日。"""
    daily = daily_matrix(hourly, p)
    base = daily.shift(1).rolling(p.baseline_days, min_periods=p.min_baseline_days).median()
    out = pd.DataFrame({
        "mean": daily.mean(axis=1), "min": daily.min(axis=1), "max": daily.max(axis=1),
        "n_sites": daily.notna().sum(axis=1),
        "C": coherence(daily, base, p.rise_ratio, p.min_abs_rise),
        "CV": spatial_cv(daily),
        "ratio_to_base": (daily / base).median(axis=1),
    })
    out["regional_candidate"] = (out["C"] >= p.coherence_high) & (out["CV"] <= p.max_cv)
    return out


def hourly_profile(hourly: pd.DataFrame, p: RegionalParams = RegionalParams()) -> pd.DataFrame:
    """每小時的 C、CV、城市中位數，用來找區域型時段。"""
    base = hourly.shift(1).rolling(p.baseline_hours, min_periods=p.baseline_hours // 2).median()
    return pd.DataFrame({"median": hourly.median(axis=1),
                         "C": coherence(hourly, base, p.rise_ratio, p.min_abs_rise),
                         "CV": spatial_cv(hourly)})


def episodes(flag: pd.Series, min_len: int) -> pd.DataFrame:
    """把連續為 True 的時段合併成事件：start、end、hours。"""
    flag = flag.fillna(False).astype(bool)
    group = (flag != flag.shift()).cumsum()
    rows = [(g.index[0], g.index[-1], len(g)) for _, g in flag.groupby(group) if g.iloc[0] and len(g) >= min_len]
    return pd.DataFrame(rows, columns=["start", "end", "hours"])


def regional_episodes(profile: pd.DataFrame, p: RegionalParams = RegionalParams()) -> pd.DataFrame:
    """C ≥ coherence_high 且 CV ≤ max_cv 連續 min_episode_hours 小時以上的時段。"""
    flag = (profile["C"] >= p.coherence_high) & (profile["CV"] <= p.max_cv)
    ep = episodes(flag, p.min_episode_hours)
    if ep.empty:
        return ep
    stats = [profile.loc[s:e].agg({"median": "max", "C": "mean"}) for s, e in zip(ep["start"], ep["end"])]
    return ep.assign(peak_median=[s["median"] for s in stats], mean_C=[s["C"] for s in stats])


def local_station_hours(hourly: pd.DataFrame, profile: pd.DataFrame,
                        p: RegionalParams = RegionalParams()) -> pd.DataFrame:
    """單一測站明顯高於「其他測站中位數」且城市一致性低的小時（局部型候選）。"""
    rows = []
    for site in hourly.columns:
        others = hourly.drop(columns=site).median(axis=1)
        excess = hourly[site] - others
        hit = (excess >= np.maximum(p.local_excess_abs, p.local_excess_rel * others)) & (profile["C"] < p.coherence_low)
        if hit.any():
            rows.append(pd.DataFrame({"time": hit.index[hit], "siteid": site, "pm25": hourly[site][hit],
                                      "others_median": others[hit], "excess": excess[hit]}))
    if not rows:
        return pd.DataFrame(columns=["time", "siteid", "pm25", "others_median", "excess"])
    return pd.concat(rows, ignore_index=True)
