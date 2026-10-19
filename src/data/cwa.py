"""中央氣象署自動氣象站觀測（架構模組 ④ Data Acquisition）。

資料來源：交通部中央氣象署開放資料平臺 https://opendata.cwa.gov.tw/ （需要授權碼，見 .env 的 CWA_API_KEY）
- `O-A0001-001` 自動氣象站資料：全國約 876 站「最新一筆」觀測，含風向、風速、溫度、濕度
  （只有當下這一筆，所以要靠排程每小時收集才能累積成時間序列）

用途：⑤ 來源判斷需要風向（區域傳輸）；濕度校正改用氣象站濕度，
因為微型感測器回報的濕度不可靠（T-20 實測）。

指令列用法（從專案根目錄）：
    python -m src.data.cwa latest --city 臺中市
"""

from __future__ import annotations

import argparse
import os

import pandas as pd
from dotenv import load_dotenv

from src.data.http import TIMEOUT, gov_session

URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
TZ = "Asia/Taipei"
COLUMNS = ["station_id", "station_name", "county", "town", "lon", "lat", "time",
           "wind_dir", "wind_speed", "temp", "rh", "pressure"]


def api_key() -> str:
    load_dotenv()
    key = os.environ.get("CWA_API_KEY")
    if not key:
        raise RuntimeError("找不到 CWA_API_KEY，請在專案根目錄的 .env 設定（見 .env.example）")
    return key


def _num(value):
    """氣象署以 -99、-999 等表示缺值；轉成 NaN。"""
    v = pd.to_numeric(value, errors="coerce")
    return float("nan") if pd.isna(v) or v <= -90 else float(v)


def parse_stations(body: dict) -> pd.DataFrame:
    """把 O-A0001-001 的 JSON 轉成一列一站的 DataFrame。"""
    rows = []
    for st in body.get("records", {}).get("Station", []):
        geo, we = st.get("GeoInfo", {}), st.get("WeatherElement", {})
        coord = next((c for c in geo.get("Coordinates", []) if c.get("CoordinateName") == "WGS84"),
                     (geo.get("Coordinates") or [{}])[0])
        rows.append({
            "station_id": st.get("StationId"), "station_name": st.get("StationName"),
            "county": geo.get("CountyName"), "town": geo.get("TownName"),
            "lon": _num(coord.get("StationLongitude")), "lat": _num(coord.get("StationLatitude")),
            "time": st.get("ObsTime", {}).get("DateTime"),
            "wind_dir": _num(we.get("WindDirection")), "wind_speed": _num(we.get("WindSpeed")),
            "temp": _num(we.get("AirTemperature")), "rh": _num(we.get("RelativeHumidity")),
            "pressure": _num(we.get("AirPressure")),
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    return df


def latest(city: str | None = None, session=None) -> pd.DataFrame:
    """抓全國（或指定縣市）自動氣象站的最新觀測。"""
    session = session or gov_session()
    resp = session.get(URL, params={"Authorization": api_key(), "format": "JSON"}, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"氣象署 API 回傳 {resp.status_code}：{resp.text[:200]}")
    df = parse_stations(resp.json())
    return df[df["county"] == city].reset_index(drop=True) if city else df


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="中央氣象署自動氣象站觀測")
    sub = parser.add_subparsers(dest="command", required=True)
    lt = sub.add_parser("latest", help="最新一筆觀測")
    lt.add_argument("--city", default=None)
    args = parser.parse_args(argv)
    df = latest(args.city)
    print(df.to_string(index=False, max_rows=40))


if __name__ == "__main__":
    main()
