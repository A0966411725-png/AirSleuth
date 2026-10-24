"""環境部國家空品測站資料（架構模組 ④ Data Acquisition）。

資料來源：環境部環境資料開放平臺 https://data.moenv.gov.tw/ （需要 API key，見 .env 的 MOENV_API_KEY）
- `aqx_p_432` 空氣品質指標（AQI）：全國測站「當下這一小時」，含經緯度，用來取得測站座標
- `aqx_p_<縣市代碼>` 縣市小時值：每個測站、每個測項、每小時一筆的長表，由新到舊排序，
  **可回溯好幾個月**（2026-10-19 實測，臺中市可查到 2026 年 5 月以前）

輸出：寬表 DataFrame，一列 = 一個測站的一個小時，欄位見 `STATION_COLUMNS`。

指令列用法（從專案根目錄）：
    python -m src.data.moenv sites
    python -m src.data.moenv hourly --city 臺中市 --days 7 --out data/raw/moenv/taichung_7d.csv
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src.data.http import TIMEOUT, gov_session

BASE_URL = "https://data.moenv.gov.tw/api/v2"
TZ = "Asia/Taipei"

# 縣市小時值資料集代碼（從環境部 OpenAPI 規格查得，2026-10-19）
CITY_HOURLY = {
    "基隆市": "aqx_p_135", "臺北市": "aqx_p_136", "新北市": "aqx_p_137", "桃園市": "aqx_p_138",
    "新竹市": "aqx_p_139", "新竹縣": "aqx_p_140", "苗栗縣": "aqx_p_141", "臺中市": "aqx_p_142",
    "彰化縣": "aqx_p_143", "南投縣": "aqx_p_144", "雲林縣": "aqx_p_145", "嘉義市": "aqx_p_146",
    "嘉義縣": "aqx_p_147", "澎湖縣": "aqx_p_148", "臺南市": "aqx_p_149", "高雄市": "aqx_p_150",
    "屏東縣": "aqx_p_151", "臺東縣": "aqx_p_152", "花蓮縣": "aqx_p_153", "宜蘭縣": "aqx_p_154",
    "金門縣": "aqx_p_155", "連江縣": "aqx_p_156",
}

# 測項英文代碼 → 欄位名稱（只保留 AirSleuth 用得到的）
ITEMS = {
    "PM2.5": "pm25", "PM10": "pm10", "RH": "rh", "AMB_TEMP": "temp",
    "WIND_SPEED": "wind_speed", "WIND_DIREC": "wind_dir", "RAINFALL": "rain",
}
STATION_COLUMNS = ["siteid", "sitename", "county", "lon", "lat", "time"] + list(ITEMS.values())


def api_key() -> str:
    load_dotenv()
    key = os.environ.get("MOENV_API_KEY")
    if not key:
        raise RuntimeError("找不到 MOENV_API_KEY，請在專案根目錄的 .env 設定（見 .env.example）")
    return key


def _get_all(dataset: str, session=None, page: int = 1000, since: str | None = None) -> list[dict]:
    """依 offset 分頁取回資料集（環境部 API 每頁最多 1000 筆）。

    縣市小時值資料集由新到舊排序，可回溯好幾個月（2026-10-19 實測到 5 月以前），
    所以給 `since`（'YYYY-MM-DD HH:MM'）時，翻到比它舊的資料就停止。
    """
    session = session or gov_session()
    rows, offset = [], 0
    while True:
        resp = session.get(f"{BASE_URL}/{dataset}", timeout=TIMEOUT,
                           params={"api_key": api_key(), "format": "json", "limit": page, "offset": offset})
        if resp.status_code != 200:
            raise RuntimeError(f"環境部 API {dataset} 回傳 {resp.status_code}：{resp.text[:200]}")
        body = resp.json()
        records = body if isinstance(body, list) else body.get("records", [])
        if since:
            kept = [r for r in records if r.get("monitordate", "") >= since]
            rows += kept
            if len(kept) < len(records):
                return rows
        else:
            rows += records
        if len(records) < page:
            return rows
        offset += page


def sites(session=None) -> pd.DataFrame:
    """全國測站清單與座標（取自 AQI 即時資料集）。"""
    df = pd.DataFrame(_get_all("aqx_p_432", session))
    df = df.rename(columns={"longitude": "lon", "latitude": "lat"})
    df[["lon", "lat"]] = df[["lon", "lat"]].apply(pd.to_numeric, errors="coerce")
    return df[["siteid", "sitename", "county", "lon", "lat"]].drop_duplicates("siteid").reset_index(drop=True)


def parse_hourly(records: list[dict], site_table: pd.DataFrame | None = None) -> pd.DataFrame:
    """把縣市小時值的長表（一列一個測項）轉成寬表（一列一個測站小時）。

    無效值（空字串、'x'、'#' 等標記）轉成 NaN。
    """
    if not records:
        return pd.DataFrame(columns=STATION_COLUMNS)
    df = pd.DataFrame(records)
    df = df[df["itemengname"].isin(ITEMS)]
    df["value"] = pd.to_numeric(df["concentration"], errors="coerce")
    df["time"] = pd.to_datetime(df["monitordate"]).dt.tz_localize(TZ)
    wide = (df.pivot_table(index=["siteid", "sitename", "county", "time"], columns="itemengname",
                           values="value", aggfunc="mean")
            .rename(columns=ITEMS).reset_index())
    for col in ITEMS.values():
        if col not in wide:
            wide[col] = pd.NA
    if site_table is not None:
        wide = wide.merge(site_table[["siteid", "lon", "lat"]], on="siteid", how="left")
    else:
        wide["lon"] = wide["lat"] = pd.NA
    wide.columns.name = None
    return wide[STATION_COLUMNS].sort_values(["siteid", "time"]).reset_index(drop=True)


def hourly(city: str, days: float = 7, session=None) -> pd.DataFrame:
    """抓一個縣市所有測站最近 `days` 天的小時值，回傳寬表。"""
    if city not in CITY_HOURLY:
        raise ValueError(f"不支援的縣市「{city}」。縣市名稱要用「臺」，可用：{', '.join(CITY_HOURLY)}")
    session = session or gov_session()
    since = (pd.Timestamp.now(tz=TZ) - pd.Timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    return parse_hourly(_get_all(CITY_HOURLY[city], session, since=since), sites(session))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="環境部國家空品測站資料")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sites", help="列出全國測站與座標")
    h = sub.add_parser("hourly", help="抓一個縣市所有測站最近幾天的小時值")
    h.add_argument("--city", required=True)
    h.add_argument("--days", type=float, default=7, help="往前抓幾天，預設 7")
    h.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "sites":
        print(sites().to_string(index=False))
    else:
        df = hourly(args.city, days=args.days)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"{args.city}：{df['siteid'].nunique()} 個測站、{len(df)} 列，"
              f"{df['time'].min()} ～ {df['time'].max()} → {args.out}")


if __name__ == "__main__":
    main()
