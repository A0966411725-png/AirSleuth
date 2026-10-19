"""給 Windows 工作排程器呼叫的收集腳本：每次執行就把各縣市抓一次。

排程設定見 scripts/register_task.ps1。紀錄寫到 data/raw/logs/scheduled.log。

手動執行（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.collect_scheduled
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # 排程器的工作目錄不一定是專案根目錄

from src.data import colife  # noqa: E402

CITIES = ["臺中市", "高雄市"]
LOG = ROOT / "data" / "raw" / "logs" / "scheduled.log"


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG, encoding="utf-8", level=logging.INFO,
                        format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    session = colife.make_session()
    for city in CITIES:
        try:
            df = colife.fetch_city(city, session=session)
            paths = colife.save_daily(df, ROOT / "data" / "raw" / "colife" / city)
            logging.info("%s：%d 個感測器、%d 列 → %s", city, df["station_id"].nunique(), len(df),
                         ", ".join(p.name for p in paths))
        except Exception as exc:  # 一個縣市失敗不影響其他縣市
            logging.error("%s 抓取失敗：%s", city, exc)


if __name__ == "__main__":
    main()
