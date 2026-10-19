"""給 Windows 工作排程器呼叫的收集腳本：每次執行就把各縣市的三種資料各抓一次。

- 微型感測器（民生公共物聯網）：API 只保留約 4～5 小時 → data/raw/colife/<縣市>/YYYY-MM-DD.csv.gz
- 國家測站小時值（環境部）：抓最近 1 天，重疊部分去除重複 → data/raw/moenv/<縣市>/YYYY-MM-DD.csv.gz
- 自動氣象站（氣象署）：API 只給最新一筆，所以排程要每小時跑 → data/raw/cwa/<縣市>/YYYY-MM-DD.csv.gz

排程設定見 scripts/register_task.ps1。紀錄寫到 data/raw/logs/scheduled.log。

手動執行（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.collect_scheduled
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # 排程器的工作目錄不一定是專案根目錄

from src.data import colife, cwa, moenv  # noqa: E402
from src.data.http import gov_session  # noqa: E402

CITIES = ["臺中市", "高雄市"]
RAW = ROOT / "data" / "raw"
LOG = RAW / "logs" / "scheduled.log"


def save_daily(df: pd.DataFrame, out_dir: Path, keys: list[str]) -> list[str]:
    """依日期（臺灣時間）存成 YYYY-MM-DD.csv.gz，和既有檔案合併後依 keys 去除重複（保留新抓的）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for day, part in df.groupby(df["time"].dt.strftime("%Y-%m-%d")):
        path = out_dir / f"{day}.csv.gz"
        if path.exists():
            old = pd.read_csv(path, dtype={k: str for k in keys if k != "time"})
            old["time"] = pd.to_datetime(old["time"]).dt.tz_convert(colife.TZ)
            part = pd.concat([old, part], ignore_index=True)
        part = part.drop_duplicates(keys, keep="last").sort_values(keys)
        part.to_csv(path, index=False, compression="gzip")
        written.append(path.name)
    return written


def run(name: str, func) -> None:
    """執行一項收集；失敗只記錄，不影響其他項目。"""
    try:
        logging.info("%s：%s", name, func())
    except Exception as exc:
        logging.error("%s 失敗：%s", name, exc)


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG, encoding="utf-8", level=logging.INFO,
                        format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    colife_session, gov = colife.make_session(), gov_session()
    try:
        site_table = moenv.sites(gov)  # 測站座標；失敗時照樣收集，只是座標欄位留空
    except Exception as exc:
        logging.error("環境部測站清單失敗：%s", exc)
        site_table = None
    weather = None

    for city in CITIES:
        def micro(city=city):
            df = colife.fetch_city(city, session=colife_session)
            files = colife.save_daily(df, RAW / "colife" / city)
            return f"微型感測器 {df['station_id'].nunique()} 個、{len(df)} 列 → {', '.join(p.name for p in files)}"

        def station(city=city):
            since = (pd.Timestamp.now(tz=moenv.TZ) - pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
            df = moenv.parse_hourly(moenv._get_all(moenv.CITY_HOURLY[city], gov, since=since), site_table)
            return f"國家測站 {df['siteid'].nunique()} 站、{len(df)} 列 → {', '.join(save_daily(df, RAW / 'moenv' / city, ['siteid', 'time']))}"

        def weather_obs(city=city):
            nonlocal weather
            if weather is None:
                weather = cwa.latest(session=gov)
            df = weather[weather["county"] == city]
            return f"氣象站 {len(df)} 站 → {', '.join(save_daily(df, RAW / 'cwa' / city, ['station_id', 'time']))}"

        run(f"{city} 微型感測器", micro)
        run(f"{city} 國家測站", station)
        run(f"{city} 氣象站", weather_obs)


if __name__ == "__main__":
    main()
