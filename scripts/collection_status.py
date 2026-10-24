"""資料收集狀況報告：每種資料收到多少、涵蓋哪些小時、哪裡有缺口。

用法（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.collection_status
    .venv\\Scripts\\python -m scripts.collection_status --since 2026-10-19 --png docs/collection_status.png

輸出：終端機表格；加 --png 時另存每小時覆蓋圖（每格 = 該小時有沒有收到資料、收到幾個感測器／站）。
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TZ = "Asia/Taipei"
SOURCES = {  # 資料夾 → (顯示名稱, 感測器／站的欄位)
    "colife": ("微型感測器", "station_id"),
    "moenv": ("國家測站", "siteid"),
    "cwa": ("氣象站", "station_id"),
}


def load(source: str, city: str, since: pd.Timestamp) -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW / source / city / "*.csv.gz")))
    files = [f for f in files if Path(f).name[:10] >= since.strftime("%Y-%m-%d")]
    if not files:
        return pd.DataFrame()
    key = SOURCES[source][1]
    df = pd.concat([pd.read_csv(f, usecols=lambda c: c in (key, "time"), dtype={key: str}) for f in files])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_convert(TZ)
    return df[df["time"] >= since]


def hourly_counts(df: pd.DataFrame, key: str, start, end) -> pd.Series:
    """每小時有幾個不同的感測器／站有資料（0 = 該小時沒有資料）。"""
    hours = pd.date_range(start, end, freq="h")
    if df.empty:
        return pd.Series(0, index=hours)
    return df.groupby(df["time"].dt.floor("h"))[key].nunique().reindex(hours, fill_value=0)


def gaps(counts: pd.Series) -> list[str]:
    """把連續沒資料的小時合併成區段文字。"""
    empty = counts[counts == 0].index
    if len(empty) == 0:
        return []
    out, start, prev = [], empty[0], empty[0]
    for t in list(empty[1:]) + [None]:
        if t is not None and t - prev == pd.Timedelta(hours=1):
            prev = t
            continue
        out.append(f"{start:%m/%d %H:00}" + ("" if start == prev else f"～{prev:%m/%d %H:00}"))
        if t is not None:
            start = prev = t
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="資料收集狀況")
    parser.add_argument("--since", default="2026-10-19", help="從哪一天開始統計（臺灣時間）")
    parser.add_argument("--cities", nargs="+", default=["臺中市", "高雄市"])
    parser.add_argument("--png", type=Path, default=None, help="另存每小時覆蓋圖")
    args = parser.parse_args()

    since = pd.Timestamp(args.since, tz=TZ)
    now = pd.Timestamp.now(tz=TZ).floor("h")
    rows, grid = [], {}
    for city in args.cities:
        for source, (name, key) in SOURCES.items():
            df = load(source, city, since)
            # 目前這個小時排程可能還沒跑，統計到上一個小時；國家測站資料約晚 1～2 小時發布，再往前一小時
            end = now - pd.Timedelta(hours=2 if source == "moenv" else 1)
            start = df["time"].min().floor("h") if not df.empty else since
            counts = hourly_counts(df, key, start, end)
            grid[(city, name)] = counts
            covered = int((counts > 0).sum())
            rows.append({
                "縣市": city, "資料": name, "資料列": len(df),
                "感測器／站": df[key].nunique() if not df.empty else 0,
                "最早": f"{start:%m/%d %H:%M}", "最新": f"{df['time'].max():%m/%d %H:%M}" if not df.empty else "—",
                "有資料的小時": f"{covered}／{len(counts)}（{covered / max(len(counts), 1):.0%}）",
                "缺口": "、".join(gaps(counts)) or "無",
            })
    table = pd.DataFrame(rows)
    with pd.option_context("display.max_colwidth", 80, "display.width", 200):
        print(f"統計時間：{pd.Timestamp.now(tz=TZ):%Y-%m-%d %H:%M}（從 {since:%Y-%m-%d} 起）\n")
        print(table.to_string(index=False))

    log = RAW / "logs" / "scheduled.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8").splitlines()
        errors = [l for l in lines if "失敗" in l]
        print(f"\n排程紀錄：共 {len(lines)} 行，失敗 {len(errors)} 行；最後一行：{lines[-1] if lines else '—'}")
        for l in errors[-5:]:
            print("  ", l)

    if args.png:
        import matplotlib.pyplot as plt
        plt.rcParams.update({"font.sans-serif": ["Microsoft JhengHei", "Noto Sans CJK TC", "sans-serif"],
                             "axes.unicode_minus": False, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
        keys = list(grid)
        hours = pd.date_range(min(s.index.min() for s in grid.values()), now, freq="h")
        mat = np.array([(grid[k].reindex(hours, fill_value=0) > 0).astype(float) for k in keys])
        fig, ax = plt.subplots(figsize=(min(16, 4 + len(hours) * 0.12), 0.45 * len(keys) + 1.6))
        ax.imshow(mat, aspect="auto", cmap=plt.matplotlib.colors.ListedColormap(["#ece9e2", "#2a78d6"]),
                  vmin=0, vmax=1, interpolation="nearest")
        ax.set_yticks(range(len(keys)), [f"{c} {n}" for c, n in keys], fontsize=9)
        ticks = [i for i, h in enumerate(hours) if h.hour in (0, 12)]
        ax.set_xticks(ticks, [f"{hours[i]:%m/%d %H時}" for i in ticks], fontsize=8, rotation=30, ha="right")
        ax.set_xticks(np.arange(-0.5, len(hours), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(keys), 1), minor=True)
        ax.grid(which="minor", color="#fcfcfb", linewidth=1)
        ax.tick_params(which="minor", length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title("每小時是否收到資料（藍＝有、灰＝沒有）", loc="left", fontsize=11)
        fig.tight_layout()
        args.png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.png, dpi=150)
        print(f"\n覆蓋圖已存到 {os.path.relpath(args.png, ROOT)}")


if __name__ == "__main__":
    main()
