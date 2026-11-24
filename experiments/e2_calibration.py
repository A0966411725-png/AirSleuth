"""E2 校正實驗：用整個實驗期間（10/19～11/18）的共置資料，評估微型感測器的在地校正。

和 Proposal 階段的 T-22（5 天資料）相同做法，資料量增加約 6 倍：
- 共置：國家測站 1 km 內的微型感測器，各自算小時平均後取中位數（時間標記用 T-22 確認的「整點開始」慣例）
- 模型：不校正、線性、線性＋測站濕度、線性＋最近氣象站濕度（Agent 實際使用的版本：沒有測站的地方只有氣象站濕度）
- 評估：留一站交叉驗證（每次拿掉一個測站當測試），兩市分開
- 另外輸出整個期間擬合的係數，以及依濕度分組的偏差

用法（從專案根目錄）：
    .venv\\Scripts\\python -m experiments.e2_calibration
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common import (BLUE, CITIES, GREY, MICRO_END, MICRO_START, ORANGE, RAW, RESULTS, TZ, plt,
                                read_source, save_table)
from src.analytics import calibration as cal
from src.analytics.spatial import haversine_km

MODELS = {"不校正": [], "線性": ["sensor_pm25"], "線性＋測站濕度": ["sensor_pm25", "station_rh"],
          "線性＋氣象站濕度": ["sensor_pm25", "cwa_rh"]}
NEAR_KM = 1.5   # 先粗篩測站 1.5 km 內的感測器，降低記憶體；正式共置半徑是 1 km
T22 = {"臺中市": {"不校正": 4.99, "線性": 3.98, "線性＋測站濕度": 3.83},
       "高雄市": {"不校正": 3.43, "線性": 3.18, "線性＋測站濕度": 3.05}}


def micro_near_stations(city: str, stations: pd.DataFrame) -> pd.DataFrame:
    sites = stations.drop_duplicates("siteid")[["lat", "lon"]].to_numpy()
    parts = []
    days = pd.date_range(MICRO_START.normalize(), MICRO_END.normalize(), freq="D")
    for day in days:
        f = RAW / "colife" / city / f"{day:%Y-%m-%d}.csv.gz"
        if not f.exists():
            continue
        df = pd.read_csv(f, dtype={"station_id": str}, usecols=["station_id", "lat", "lon", "time", "pm25", "rh"])
        pos = df.drop_duplicates("station_id")
        d = haversine_km(pos["lat"].to_numpy()[:, None], pos["lon"].to_numpy()[:, None], sites[:, 0][None, :], sites[:, 1][None, :])
        keep = set(pos["station_id"].to_numpy()[(d <= NEAR_KM).any(axis=1)])
        parts.append(df[df["station_id"].isin(keep)])
    df = pd.concat(parts, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    df = df.drop_duplicates(["station_id", "time"])
    return df[(df["time"] >= MICRO_START) & (df["time"] <= MICRO_END)]


def pairs_for(city: str) -> pd.DataFrame:
    stations = read_source("moenv", city, MICRO_START.floor("h"), MICRO_END, "siteid")
    micro = micro_near_stations(city, stations)
    pairs = cal.collocate(cal.hourly_sensor_means(micro, "start"), stations, radius_km=1.0)
    weather = read_source("cwa", city, MICRO_START.floor("h"), MICRO_END, "station_id")
    near = cal.nearest_weather(pairs, weather)
    w = weather[["station_id", "time", "rh"]].rename(columns={"station_id": "cwa_id", "rh": "cwa_rh"})
    w = w.assign(time=w["time"].dt.floor("h")).groupby(["cwa_id", "time"], as_index=False)["cwa_rh"].mean()
    return pairs.merge(near[["siteid", "cwa_id"]], on="siteid").merge(w, on=["cwa_id", "time"], how="left").assign(city=city)


def main() -> None:
    rows, coefs, rh_rows = [], [], []
    all_pairs = []
    for city in CITIES:
        p = pairs_for(city)
        all_pairs.append(p)
        cv = cal.leave_one_site_out(p.reset_index(drop=True), MODELS)
        cv["MAE 改善"] = 1 - cv["MAE"] / cv.loc[cv["model"] == "不校正", "MAE"].iloc[0]
        cv["T-22（5 天）MAE"] = cv["model"].map(T22[city])
        cv.insert(0, "city", city)
        cv.insert(1, "測站數", p["siteid"].nunique())
        cv.insert(2, "測站‧小時", len(p))
        rows.append(cv)
        for name, feats in MODELS.items():
            if feats:
                c = cal.fit(p, feats)
                coefs.append({"city": city, "model": name, **c.round(4).to_dict()})
        bins = pd.cut(p["cwa_rh"], [0, 60, 70, 80, 90, 101], right=False)
        g = p.assign(bias=p["sensor_pm25"] - p["ref_pm25"], ratio=p["sensor_pm25"] / p["ref_pm25"].replace(0, np.nan))
        for b, sub in g.groupby(bins, observed=True):
            rh_rows.append({"city": city, "氣象站濕度": str(b), "n": len(sub), "平均偏差": sub["bias"].mean(),
                            "感測器／測站 中位數比": sub["ratio"].median()})
    res = pd.concat(rows, ignore_index=True)
    save_table(res.round(4), "e2_calibration.csv")
    save_table(pd.DataFrame(coefs), "e2_coefficients.csv")
    save_table(pd.DataFrame(rh_rows).round(3), "e2_humidity_bias.csv")
    print(res.round(3).to_string(index=False))
    print(pd.DataFrame(coefs).to_string(index=False))
    print(pd.DataFrame(rh_rows).round(3).to_string(index=False))
    plot(pd.concat(all_pairs, ignore_index=True), pd.DataFrame(coefs))


def plot(pairs: pd.DataFrame, coefs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharex=True, sharey=True)
    lim = [0, float(np.nanpercentile(pairs[["sensor_pm25", "ref_pm25"]].to_numpy(), 99.5)) + 3]
    for ax, city in zip(axes, CITIES):
        p = pairs[pairs["city"] == city]
        ax.scatter(p["sensor_pm25"], p["ref_pm25"], s=6, alpha=0.35, color=BLUE, edgecolor="none")
        ax.plot(lim, lim, color=GREY, lw=1, ls="--", label="1:1")
        c = coefs[(coefs["city"] == city) & (coefs["model"] == "線性")].iloc[0]
        x = np.array(lim)
        ax.plot(x, c["intercept"] + c["sensor_pm25"] * x, color=ORANGE, lw=1.8, label="線性校正")
        ax.set_title(f"{city}（{p['siteid'].nunique()} 站、{len(p)} 個測站‧小時）", loc="left", fontsize=11)
        ax.set_xlabel("微型感測器 1 km 中位數（μg/m³）")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
    axes[0].set_ylabel("國家測站（μg/m³）")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("E2：微型感測器與國家測站共置比對（10/19～11/18）", x=0.02, ha="left", fontsize=12)
    fig.tight_layout()
    fig.savefig(RESULTS / "e2_calibration_scatter.png", dpi=180)


if __name__ == "__main__":
    main()
