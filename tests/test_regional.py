"""src.analytics.regional 的離線測試（合成資料）。"""

import numpy as np
import pandas as pd

from src.analytics import regional as rg


def _hourly(days=30, sites=6, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-09-01", periods=days * 24, freq="h", tz="Asia/Taipei")
    return pd.DataFrame(12 + rng.normal(0, 1, (len(t), sites)), index=t,
                        columns=[str(i) for i in range(sites)])


def test_regional_day_is_flagged_when_all_sites_rise_together():
    h = _hourly()
    day = h.index.normalize() == pd.Timestamp("2026-09-20", tz="Asia/Taipei")
    h.loc[day] += 14  # 所有測站一起升高到約 26
    d = rg.daily_candidates(h)
    assert d.loc[pd.Timestamp("2026-09-20", tz="Asia/Taipei"), "regional_candidate"]
    assert d["regional_candidate"].sum() == 1


def test_single_site_rise_is_local_not_regional():
    h = _hourly()
    t = pd.Timestamp("2026-09-20 10:00", tz="Asia/Taipei")
    h.loc[t:t + pd.Timedelta(hours=5), "3"] += 30
    prof = rg.hourly_profile(h)
    assert rg.regional_episodes(prof).empty
    loc = rg.local_station_hours(h, prof)
    assert set(loc["siteid"]) == {"3"} and len(loc) == 6


def test_regional_episode_needs_min_duration():
    h = _hourly()
    t = pd.Timestamp("2026-09-20 00:00", tz="Asia/Taipei")
    h.loc[t:t + pd.Timedelta(hours=3)] += 15   # 只有 4 小時：太短
    h.loc[t + pd.Timedelta(days=2):t + pd.Timedelta(days=2, hours=9)] += 15  # 10 小時
    ep = rg.regional_episodes(rg.hourly_profile(h))
    assert len(ep) == 1 and ep.loc[0, "hours"] == 10


def test_daily_mean_requires_enough_hours():
    h = _hourly(days=3)
    h.iloc[24:24 + 10, 0] = np.nan  # 第 2 天第 0 站只剩 14 小時
    d = rg.daily_matrix(h)
    assert np.isnan(d.iloc[1, 0]) and d.iloc[1, 1:].notna().all()
