"""實驗共用：資料期間、讀檔與圖表樣式（OpenSpec 變更 add-evaluation-suite）。

實驗資料期間固定（docs/analysis/T-25_期末實驗資料集.md），之後新收到的資料不會改變結果。
"""

from __future__ import annotations

import glob
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "experiments" / "results"
TZ = "Asia/Taipei"
CITIES = ["臺中市", "高雄市"]
SEED = 42

# 國家測站：8/20～11/24；微型感測器：10/19 11:00～11/18 15:35（之後憑證過期）
STATION_START = pd.Timestamp("2026-08-20 00:00", tz=TZ)
STATION_END = pd.Timestamp("2026-11-24 13:00", tz=TZ)
MICRO_START = pd.Timestamp("2026-10-19 11:00", tz=TZ)
MICRO_END = pd.Timestamp("2026-11-18 15:35", tz=TZ)

BLUE, ORANGE, GREEN, GREY, INK = "#2a78d6", "#eb6834", "#2e9c6a", "#9aa6bd", "#14213d"
plt.rcParams.update({"font.sans-serif": ["Microsoft JhengHei", "Noto Sans CJK TC", "Arial Unicode MS", "sans-serif"],
                     "axes.unicode_minus": False, "figure.dpi": 110, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6,
                     "axes.edgecolor": "#52514e", "axes.labelcolor": "#52514e", "xtick.color": "#52514e",
                     "ytick.color": "#52514e", "figure.facecolor": "white", "axes.facecolor": "white"})


def read_source(source: str, city: str, start: pd.Timestamp, end: pd.Timestamp, key: str) -> pd.DataFrame:
    files = [f for f in sorted(glob.glob(str(RAW / source / city / "*.csv.gz")))
             if start.normalize().strftime("%Y-%m-%d") <= Path(f).name[:10] <= end.strftime("%Y-%m-%d")]
    df = pd.concat([pd.read_csv(f, dtype={key: str}) for f in files], ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    df = df.drop_duplicates([key, "time"])
    return df[(df["time"] >= start) & (df["time"] <= end)].reset_index(drop=True)


def save_table(df: pd.DataFrame, name: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    df.to_csv(path, index=False, encoding="utf-8")
    return path
