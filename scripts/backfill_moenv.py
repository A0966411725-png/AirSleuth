"""一次補抓國家測站的歷史小時值（環境部縣市小時值資料集可回溯好幾個月）。

用法（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.backfill_moenv --days 60
輸出：data/raw/moenv/<縣市>/YYYY-MM-DD.csv.gz（和排程收集的檔案相同格式，重複的小時會合併）
"""

from __future__ import annotations

import argparse

from scripts.collect_scheduled import CITIES, RAW, save_daily
from src.data import moenv


def main() -> None:
    parser = argparse.ArgumentParser(description="補抓國家測站歷史小時值")
    parser.add_argument("--days", type=float, default=60)
    parser.add_argument("--city", action="append", help="可重複指定；預設為排程收集的縣市")
    args = parser.parse_args()
    for city in args.city or CITIES:
        df = moenv.hourly(city, days=args.days)
        files = save_daily(df, RAW / "moenv" / city, ["siteid", "time"])
        print(f"{city}：{df['siteid'].nunique()} 站、{len(df)} 列，{df['time'].min()} ～ {df['time'].max()}，"
              f"寫入 {len(files)} 個日檔", flush=True)


if __name__ == "__main__":
    main()
