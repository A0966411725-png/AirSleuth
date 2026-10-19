"""產生 notebooks/T-20_spatial_eda.ipynb（T-20 空間型態資料探索）。

用法（從專案根目錄）：
    .venv\\Scripts\\python notebooks\\make_t20_notebook.py
    .venv\\Scripts\\jupyter nbconvert --to notebook --execute --inplace notebooks\\T-20_spatial_eda.ipynb
"""
import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = []

cells.append(md("""# T-20 空間型態資料探索：區域型 vs 局部型事件

**目的：**用民生公共物聯網的真實微型感測器資料，檢驗 AirSleuth 判斷污染來源的核心直覺（Algorithm 2）：
- **區域型**：大範圍感測器一起升高、彼此差異小
- **局部型**：少數相鄰感測器一起升高，周圍正常

**資料：**`data/raw/colife/<縣市>/YYYY-MM-DD.csv.gz`（Windows 排程每 2 小時收集，5 分鐘平均）。
**方法：**`src/analytics/spatial.py`。圖檔輸出到 `notebooks/figures/`。"""))

cells.append(code('''import os, sys, glob
from pathlib import Path
ROOT = Path.cwd() if (Path.cwd() / "src").exists() else Path.cwd().parent
os.chdir(ROOT); sys.path.insert(0, str(ROOT))
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from src.analytics import spatial as sp
from src.data import colife, quality

plt.rcParams.update({"font.sans-serif": ["Microsoft JhengHei", "Noto Sans CJK TC", "sans-serif"],
                     "axes.unicode_minus": False, "figure.dpi": 110, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6, "axes.edgecolor": "#52514e", "text.color": "#0b0b0b",
                     "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
BLUE, ORANGE, INK2 = "#2a78d6", "#eb6834", "#52514e"
import matplotlib.dates as mdates
from zoneinfo import ZoneInfo
HHMM = mdates.DateFormatter("%H:%M", tz=ZoneInfo(colife.TZ))
FIG = ROOT / "notebooks" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
P = sp.Params()

def load(city):
    files = sorted(glob.glob(str(ROOT / "data" / "raw" / "colife" / city / "*.csv.gz")))
    df = pd.concat([pd.read_csv(f, dtype={"station_id": str}) for f in files], ignore_index=True)
    df["time"] = pd.to_datetime(df["time"]).dt.tz_convert(colife.TZ)
    return df.drop_duplicates(["station_id", "time"])

CITIES = ["臺中市", "高雄市"]
raw = {c: load(c) for c in CITIES}
for c, d in raw.items():
    print(f"{c}: {d['station_id'].nunique()} 個感測器，{len(d)} 列，"
          f"{d['time'].min():%m-%d %H:%M} ～ {d['time'].max():%m-%d %H:%M}")'''))

cells.append(md("## 1. 資料品質"))
cells.append(code('''qc = {c: quality.summary(quality.flag(d)) for c, d in raw.items()}
keys = ("rows", "active_sensors", "ok", "stuck", "rh_invalid", "pm25_extreme", "pm25_negative")
pd.DataFrame({c: {k: (v["ratio"] if isinstance(v, dict) else v) for k, v in s.items() if k in keys}
              for c, s in qc.items()})'''))

cells.append(md("## 2. 城市整體：區域中位數與空間一致性"))
cells.append(code('''res = {}
for c, d in raw.items():
    mx, st = sp.to_matrix(sp.usable(d)); base = sp.baseline(mx, P.baseline_hours)
    res[c] = dict(mx=mx, st=st, base=base, coh=sp.city_coherence(mx, base, P))

fig, axes = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
for c, color in zip(CITIES, (BLUE, ORANGE)):
    q = res[c]["mx"].quantile([0.25, 0.5, 0.75], axis=1).T
    axes[0].fill_between(q.index, q[0.25], q[0.75], color=color, alpha=0.15, linewidth=0)
    axes[0].plot(q.index, q[0.5], color=color, linewidth=2, label=f"{c}（中位數與四分位距）")
    axes[1].plot(res[c]["coh"].index, res[c]["coh"], color=color, linewidth=2, label=c)
axes[0].set_ylabel("PM2.5（μg/m³）"); axes[0].legend(frameon=False, loc="upper left")
axes[0].set_title("各城市所有感測器的 PM2.5 分布", loc="left", fontsize=12)
axes[1].axhline(P.coherence_high, color=INK2, linewidth=1, linestyle="--")
axes[1].annotate(f"區域型門檻 C = {P.coherence_high}", (0.01, P.coherence_high), xycoords=("axes fraction", "data"),
                 va="bottom", fontsize=8, color=INK2)
axes[1].set_ylim(0, 1); axes[1].set_ylabel("空間一致性 C"); axes[1].legend(frameon=False, loc="upper right")
[a.xaxis.set_major_formatter(HHMM) for a in fig.axes]; fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(FIG / "t20_fig1_city_overview.png", dpi=160)
{c: round(float(r["coh"].max()), 3) for c, r in res.items()}'''))

cells.append(md("## 3. 每個感測器的型態：局部事件、單點飆高、持續性偏高"))
cells.append(code('''labels = {c: sp.label_station_events(sp.station_excess(r["mx"], r["st"], P), r["base"], P) for c, r in res.items()}
order = ["local_event", "single_spike", "persistent_high", "above_background"]
names = {"local_event": "局部事件\\n（有鄰近一起升高）", "single_spike": "單點飆高\\n（疑似感測器異常）",
         "persistent_high": "持續性偏高\\n（長期熱點或偏差）", "above_background": "其他短暫高於背景"}
counts = pd.DataFrame({c: l[l.pattern != "normal"].groupby("pattern")["station_id"].nunique()
                       .reindex(order).fillna(0).astype(int) for c, l in labels.items()})
fig, ax = plt.subplots(figsize=(9, 3.6))
x = np.arange(len(order)); w = 0.38
for i, (c, color) in enumerate(zip(CITIES, (BLUE, ORANGE))):
    bars = ax.bar(x + (i - 0.5) * w, counts[c], width=w - 0.03, color=color, label=c)
    ax.bar_label(bars, fontsize=8, color=INK2, padding=2)
ax.set_xticks(x, [names[o] for o in order], fontsize=9); ax.set_ylabel("涉及的感測器數")
ax.set_title("各型態涉及的感測器數", loc="left", fontsize=12); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(FIG / "t20_fig2_patterns.png", dpi=160)
counts'''))

cells.append(md("## 4. 案例：臺中市的局部型群聚事件"))
cells.append(code('''c = "臺中市"; r = res[c]; lab = labels[c]
ev = lab[lab.pattern == "local_event"]
peak_t = ev.groupby("time").size().idxmax()
ids = ev[ev.time == peak_t].station_id.unique()
lat0, lon0 = r["st"].loc[ids, "lat"].median(), r["st"].loc[ids, "lon"].median()
series = pd.DataFrame([sp.metrics_at(r["mx"], r["st"], r["base"], t, lat0, lon0, P) for t in r["mx"].index]).set_index("time")
series["type"] = [sp.classify(m, P) for m in series.reset_index().to_dict("records")]
print(f"高峰時間 {peak_t:%H:%M}，事件感測器 {len(ids)} 個，中心 ({lat0:.4f}, {lon0:.4f})")
series.loc[[peak_t], ["n_region", "n_local", "B", "L", "E", "C", "n_local_elevated", "type"]].round(2)'''))

cells.append(code('''snap = lab[lab.time == peak_t].set_index("station_id").join(r["st"])
d = sp.haversine_km(lat0, lon0, snap["lat"].values, snap["lon"].values); snap = snap[d <= 20]
fig, ax = plt.subplots(figsize=(7.2, 6.4))
sc = ax.scatter(snap["lon"], snap["lat"], c=snap["pm25"], cmap="Blues", vmin=10, vmax=50, s=14, linewidths=0)
ev_now = snap[snap.pattern == "local_event"]
ax.scatter(ev_now["lon"], ev_now["lat"], facecolors="none", edgecolors=ORANGE, s=60, linewidths=1.6,
           label="判定為局部事件的感測器")
r_deg = 2 / (111 * np.cos(np.radians(lat0)))
ax.add_patch(plt.Circle((lon0, lat0), r_deg, fill=False, color=INK2, linestyle="--", linewidth=1))
ax.set_aspect(1 / np.cos(np.radians(lat0)))
cb = fig.colorbar(sc, ax=ax, shrink=0.8); cb.set_label("PM2.5（μg/m³）")
ax.set_xlabel("經度"); ax.set_ylabel("緯度"); ax.legend(frameon=False, loc="lower left", fontsize=9)
ax.set_title(f"臺中市 {peak_t:%m/%d %H:%M} 微型感測器 PM2.5（虛線為事件中心 2 km）", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(FIG / "t20_fig3_taichung_event_map.png", dpi=160)'''))

cells.append(code('''fig, ax = plt.subplots(figsize=(9, 3.8))
ax.plot(series.index, series["L"], color=ORANGE, linewidth=2, label="事件中心 2 km 內中位數 L")
ax.plot(series.index, series["B"], color=BLUE, linewidth=2, label="15 km 區域背景 B")
for t in series.index[series["type"] == sp.LOCAL]:
    ax.axvspan(t - pd.Timedelta("2.5min"), t + pd.Timedelta("2.5min"), color=ORANGE, alpha=0.12, linewidth=0)
ax.set_ylabel("PM2.5（μg/m³）"); ax.legend(frameon=False, loc="upper left")
ax.set_title("Algorithm 2 判斷為「局部型」的時段（淺橘色底）", loc="left", fontsize=12)
[a.xaxis.set_major_formatter(HHMM) for a in fig.axes]; fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(FIG / "t20_fig4_taichung_event_timeseries.png", dpi=160)
series["type"].value_counts()'''))

cells.append(md("## 5. 單點飆高：為什麼要求鄰近感測器一起升高"))
cells.append(code('''spikes = pd.concat([l.assign(city=c) for c, l in labels.items()])
spikes = spikes[spikes.pattern == "single_spike"]
top = spikes.groupby(["city", "station_id"]).agg(n=("time", "count"), peak=("pm25", "max")).sort_values("n", ascending=False)
c, sid = top.index[0]; r = res[c]
lat, lon = r["st"].loc[sid, ["lat", "lon"]]
dist = pd.Series(sp.haversine_km(lat, lon, r["st"]["lat"].values, r["st"]["lon"].values), index=r["st"].index)
near = dist[(dist <= P.r_local_km) & (dist > 0)].index
fig, ax = plt.subplots(figsize=(9, 3.6))
for i, n in enumerate(near):
    ax.plot(r["mx"].index, r["mx"][n], color=BLUE, alpha=0.35, linewidth=1, label="2 km 內其他感測器" if i == 0 else None)
ax.plot(r["mx"].index, r["mx"][sid], color=ORANGE, linewidth=2, label="單點飆高的感測器")
ax.set_ylabel("PM2.5（μg/m³）"); ax.legend(frameon=False, loc="upper left")
ax.set_title(f"{c}：只有一個感測器飆高，鄰近 {len(near)} 個感測器都正常", loc="left", fontsize=12)
[a.xaxis.set_major_formatter(HHMM) for a in fig.axes]; fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(FIG / "t20_fig5_single_spike.png", dpi=160)
top.head(5)'''))

cells.append(md("## 6. 濕度與微型感測器讀數"))
cells.append(code('''rows = []
for c, d in raw.items():
    f = quality.flag(d); f = f[f.qc_flag == "ok"].copy()
    f["rh_bin"] = pd.cut(f["rh"], [0, 50, 60, 70, 80, 90, 100])
    g = f.groupby("rh_bin", observed=True)["pm25"].agg(["median", "count"]); g["city"] = c
    rows.append(g)
rh = pd.concat(rows)
bins = list(dict.fromkeys(rh.index))
fig, ax = plt.subplots(figsize=(8, 3.6))
for c, color, off in zip(CITIES, (BLUE, ORANGE), (-0.2, 0.2)):
    g = rh[rh.city == c].reindex(bins)
    ax.bar(np.arange(len(bins)) + off, g["median"], width=0.38, color=color, label=c)
ax.set_xticks(np.arange(len(bins)), [str(b) for b in bins])
ax.set_xlabel("感測器回報的相對濕度（%）"); ax.set_ylabel("PM2.5 中位數（μg/m³）")
ax.set_title("不同濕度區間的 PM2.5 中位數（只含品質正常的資料）", loc="left", fontsize=12)
ax.legend(frameon=False); fig.tight_layout(); fig.savefig(FIG / "t20_fig6_humidity.png", dpi=160)
rh'''))

cells.append(md("""## 7. 小結

文字結論整理在 `coordination/reports/T-20.md`。資料只有約一天時，**不能**據此校準門檻；累積更多天後重跑本 notebook。"""))

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, "notebooks/T-20_spatial_eda.ipynb")
print("notebooks/T-20_spatial_eda.ipynb written")
