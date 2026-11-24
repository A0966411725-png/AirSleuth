"""E3 來源判斷實驗：半合成注入（已知答案）＋真實事件，比較 AirSleuth 的 Algorithm 2 與基準方法。

為什麼用半合成：真實資料沒有「這次是局部還是區域」的標準答案，人工標記也有爭議（Proposal 3.2 節）。
所以在真實的乾淨背景（城市內幾乎沒有感測器升高的時刻）上，人工加入已知型態的升高，答案就是注入的型態。
背景、感測器位置與密度、雜訊都來自真實資料，只有升高的部分是人工的。

注入情境（每個背景：一個查詢點＋一個乾淨的整點）：
- local：查詢點 2 km 內所有感測器 +Δ（Δ = 10、15、25）→ 局部型
- subregional：6 km 內所有感測器 +Δ，外環不變（Δ = 8、12、20）→ 次區域型
- regional：15 km 內所有感測器 +Δ±雜訊（Δ = 8、12、20）→ 區域型
- fault：只有最近的一個感測器 +40 → 不應判成局部型（可接受：沒有明顯事件或疑似感測器異常）
- control：不注入 → 沒有明顯事件

比較方法：
- AirSleuth（Algorithm 2，預設參數）
- 消融：拿掉 8 km 次區域層（r_sub=None）
- 基準 A「只看 AQI」：查詢點最近感測器超過「普通」上限（30.4）就當成整區事件，否則無事件（現行只看顏色的做法）
- 基準 B「最近感測器超量」：最近一個感測器比 15 km 中位數高 10 以上 → 局部型；否則區域內 60% 以上升高 → 區域型

用法（從專案根目錄）：
    .venv\\Scripts\\python -m experiments.e3_attribution
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common import (BLUE, CITIES, GREY, INK, MICRO_END, MICRO_START, ORANGE, RAW, RESULTS, SEED, TZ, plt,
                                save_table)
from src.analytics import spatial as sp

N_BACKGROUNDS = 40           # 每個城市的背景數（查詢點 × 乾淨整點）
SCENARIOS = [("local", 10), ("local", 15), ("local", 25), ("subregional", 8), ("subregional", 12), ("subregional", 20),
             ("regional", 8), ("regional", 12), ("regional", 20), ("fault", 40), ("control", 0)]
EXPECTED = {"local": {"local"}, "subregional": {"subregional"}, "regional": {"regional"},
            "fault": {"no_clear_event", "suspected_sensor_fault"}, "control": {"no_clear_event"}}
REAL_EVENTS = [("高雄 10/23 區域型", "高雄市", 22.6276, 120.2880, "2026-10-23 11:30", "regional"),
               ("臺中沿海 10/19 次區域型", "臺中市", 24.2369, 120.5385, "2026-10-19 14:40", "subregional"),
               ("臺中 10/21 平常日", "臺中市", 24.1438, 120.6844, "2026-10-21 10:00", "no_clear_event")]
METHODS = ["AirSleuth", "消融：無 8 km 層", "基準 A：只看 AQI", "基準 B：最近感測器"]


def load_city(city: str):
    parts = []
    for day in pd.date_range(MICRO_START.normalize(), MICRO_END.normalize(), freq="D"):
        f = RAW / "colife" / city / f"{day:%Y-%m-%d}.csv.gz"
        if f.exists():
            parts.append(pd.read_csv(f, dtype={"station_id": str}, usecols=["station_id", "lat", "lon", "time", "pm25", "rh"]))
    df = pd.concat(parts, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    df = df.drop_duplicates(["station_id", "time"])
    df = df[(df["time"] >= MICRO_START) & (df["time"] <= MICRO_END)]
    matrix, stations = sp.to_matrix(sp.usable(df))
    return matrix, stations, sp.baseline(matrix, 6.0)


def clean_hours(matrix: pd.DataFrame, base: pd.DataFrame) -> list[pd.Timestamp]:
    """整點、八成以上感測器有值、城市內升高的感測器少於 5%：當作沒有事件的背景。"""
    hours = matrix.index[(matrix.index.minute == 0)]
    out = []
    for t in hours:
        now, b = matrix.loc[t], base.loc[t]
        ok = now.notna() & b.notna()
        if ok.mean() < 0.8:
            continue
        if sp.is_rising(now[ok], b[ok]).mean() < 0.05:
            out.append(t)
    return out


def dense_points(stations: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    """2 km 內至少 8 個、6 km 內少於 15 km 內的 60% 的感測器位置當查詢點（後者確保次區域注入不會變成全區）。"""
    lat, lon = stations["lat"].to_numpy(), stations["lon"].to_numpy()
    d = sp.haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    n2, n6, n15 = (d <= 2).sum(1), (d <= 6).sum(1), (d <= 15).sum(1)
    keep = (n2 >= 8) & (n6 < 0.6 * n15) & (n15 >= 30)
    return stations[keep]


def nearest_baseline(now: pd.Series, b: pd.Series, dist: pd.Series) -> str:
    region = dist.index[(dist <= 15) & now.notna()]
    nearest = dist[now.notna()].idxmin()
    B = now[region].median()
    if now[nearest] - B >= 10:
        return "local"
    ok = region[b[region].notna()]
    if len(ok) and sp.is_rising(now[ok], b[ok]).mean() >= 0.6:
        return "regional"
    return "no_clear_event"


def classify_all(now: pd.Series, b: pd.Series, stations: pd.DataFrame, t, lat: float, lon: float) -> dict:
    m1, b1 = now.to_frame().T, b.to_frame().T
    m1.index = b1.index = [t]
    full = sp.classify(sp.metrics_at(m1, stations, b1, t, lat, lon))
    p_no_sub = sp.Params(r_sub_km=None)
    no_sub = sp.classify(sp.metrics_at(m1, stations, b1, t, lat, lon, p_no_sub), p_no_sub)
    dist = pd.Series(sp.haversine_km(lat, lon, stations["lat"].to_numpy(), stations["lon"].to_numpy()), index=stations.index)
    nearest = dist[now.notna()].idxmin()
    aqi = "regional" if now[nearest] > 30.4 else "no_clear_event"
    return {"AirSleuth": full, "消融：無 8 km 層": no_sub, "基準 A：只看 AQI": aqi,
            "基準 B：最近感測器": nearest_baseline(now, b, dist)}


def inject(now: pd.Series, dist: pd.Series, kind: str, delta: float, rng) -> pd.Series:
    out = now.copy()
    valid = now.notna()
    if kind == "local":
        out[valid & (dist <= 2)] += delta
    elif kind == "subregional":
        out[valid & (dist <= 6)] += delta
    elif kind == "regional":
        ids = valid & (dist <= 15)
        out[ids] += delta + rng.normal(0, 1.5, int(ids.sum()))
    elif kind == "fault":
        out[dist[valid].idxmin()] += delta
    return out


def run_city(city: str, rng) -> pd.DataFrame:
    matrix, stations, base = load_city(city)
    hours = clean_hours(matrix, base)
    points = dense_points(stations, matrix)
    print(f"{city}：感測器 {matrix.shape[1]}、乾淨整點 {len(hours)}、候選查詢點 {len(points)}", flush=True)
    rows = []
    picked = 0
    for _ in range(N_BACKGROUNDS * 20):
        if picked >= N_BACKGROUNDS:
            break
        t = hours[rng.integers(len(hours))]
        sid = points.index[rng.integers(len(points))]
        lat, lon = float(points.at[sid, "lat"]), float(points.at[sid, "lon"])
        now, b = matrix.loc[t], base.loc[t]
        dist = pd.Series(sp.haversine_km(lat, lon, stations["lat"].to_numpy(), stations["lon"].to_numpy()), index=stations.index)
        if (now.notna() & (dist <= 2)).sum() < 5:
            continue
        picked += 1
        for kind, delta in SCENARIOS:
            pred = classify_all(inject(now, dist, kind, delta, rng), b, stations, t, lat, lon)
            for method, label in pred.items():
                rows.append({"city": city, "background": picked, "time": t, "point": sid, "scenario": kind, "delta": delta,
                             "method": method, "predicted": label, "correct": label in EXPECTED[kind]})
    real = []
    for name, c, lat, lon, time, truth in REAL_EVENTS:
        if c != city:
            continue
        t = matrix.index[matrix.index <= pd.Timestamp(time, tz=TZ)].max()
        pred = classify_all(matrix.loc[t], base.loc[t], stations, t, lat, lon)
        real += [{"event": name, "truth": truth, "method": m, "predicted": p, "correct": p == truth} for m, p in pred.items()]
    return pd.DataFrame(rows), pd.DataFrame(real)


def macro_f1(df: pd.DataFrame) -> float:
    """以 local／subregional／regional／none 四類計算 macro-F1（fault 情境另外看「誤判成局部」的比例）。"""
    d = df[df["scenario"] != "fault"].copy()
    d["truth"] = d["scenario"].replace({"control": "none"})
    d["pred"] = d["predicted"].replace({"no_clear_event": "none", "suspected_sensor_fault": "none", "mixed": "local"})
    scores = []
    for c in ["local", "subregional", "regional", "none"]:
        tp = ((d["truth"] == c) & (d["pred"] == c)).sum()
        fp = ((d["truth"] != c) & (d["pred"] == c)).sum()
        fn = ((d["truth"] == c) & (d["pred"] != c)).sum()
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(scores))


def main() -> None:
    rng = np.random.default_rng(SEED)
    cases, real = zip(*(run_city(c, rng) for c in CITIES))
    cases, real = pd.concat(cases, ignore_index=True), pd.concat(real, ignore_index=True)
    save_table(cases, "e3_cases.csv")
    save_table(real, "e3_real_events.csv")
    acc = cases.groupby(["method", "scenario", "delta"])["correct"].mean().unstack(["scenario", "delta"])
    summary = []
    for m in METHODS:
        d = cases[cases["method"] == m]
        summary.append({"method": m, "accuracy": d["correct"].mean(), "macro_F1": macro_f1(d),
                        **{f"recall_{s}": d[d["scenario"] == s]["correct"].mean() for s in EXPECTED},
                        "false_local_under_fault": (d[d["scenario"] == "fault"]["predicted"] == "local").mean()})
    summary = pd.DataFrame(summary)
    save_table(summary.round(4), "e3_summary.csv")
    save_table(acc.round(3).reset_index(), "e3_accuracy_by_scenario.csv")
    conf = pd.crosstab([cases["method"], cases["scenario"]], cases["predicted"])
    save_table(conf.reset_index(), "e3_confusion.csv")
    print(f"案例數：{cases['background'].groupby(cases['city']).nunique().to_dict()} 個背景 × {len(SCENARIOS)} 種情境 × {len(METHODS)} 種方法")
    print(summary.round(3).to_string(index=False))
    print(acc.round(2).to_string())
    print(real.pivot_table(index="event", columns="method", values="predicted", aggfunc="first").to_string())
    plot(summary)


def plot(summary: pd.DataFrame) -> None:
    cols = ["recall_local", "recall_subregional", "recall_regional", "recall_control", "recall_fault"]
    names = ["局部型", "次區域型", "區域型", "無事件", "單一感測器異常\n（不誤判為局部）"]
    colors = [ORANGE, BLUE, GREY, INK]
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    width = 0.2
    for i, (m, c) in enumerate(zip(METHODS, colors)):
        vals = summary.set_index("method").loc[m, cols].to_numpy(dtype=float)
        ax.bar(np.arange(len(cols)) + (i - 1.5) * width, vals, width, label=m, color=c)
    ax.set_xticks(range(len(cols)), names)
    ax.set_ylabel("正確率")
    ax.set_ylim(0, 1.1)
    ax.set_title("E3：來源判斷的半合成注入實驗（臺中＋高雄，80 個真實背景）", loc="left", fontsize=12)
    ax.legend(frameon=False, ncols=4, loc="upper center", fontsize=8.5, bbox_to_anchor=(0.5, -0.18))
    fig.tight_layout()
    fig.savefig(RESULTS / "e3_attribution.png", dpi=180)


if __name__ == "__main__":
    main()
