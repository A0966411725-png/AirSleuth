"""民生公共物聯網：環境部智慧城鄉空品微型感測器資料串接（架構模組 ④ Data Acquisition）。

資料來源是 OGC SensorThings API：
    https://sta.colife.org.tw/STA_AirQuality_EPAIoT/v1.0/

已知限制（2026-10-19 實測）：
- 每個感測器有 PM2.5、Relative humidity、Temperature 三個 Datastream，約每分鐘一筆。
- API 只保留最近約 4～5 小時的觀測值，更早的資料查不到，所以要用 `collect` 定時累積。
- 縣市名稱要用「臺」，例如「臺中市」；用「台中市」會查不到。
- 有些縣市的感測器沒有 township、areaType 欄位，空間分析請用經緯度。

輸入：縣市名稱。
輸出：長表 DataFrame，一列是「一個感測器在一個時間區間」，欄位見 `OBS_COLUMNS`。

指令列用法（從專案根目錄執行）：
    python -m src.data.colife cities
    python -m src.data.colife snapshot --city 臺中市 --out data/sample/taichung_snapshot.csv
    python -m src.data.colife collect --city 臺中市 --every-minutes 120
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://sta.colife.org.tw/STA_AirQuality_EPAIoT/v1.0"
TZ = "Asia/Taipei"
TIMEOUT = 120

# API 的 Datastream 名稱 → 我們的欄位名稱
VARIABLES = {"PM2.5": "pm25", "Relative humidity": "rh", "Temperature": "temp"}

STATION_COLUMNS = ["station_id", "device_name", "city", "township", "area_type", "lon", "lat"]
OBS_COLUMNS = STATION_COLUMNS + ["time", "pm25", "rh", "temp", "n_obs"]


def make_session() -> requests.Session:
    """建立一個遇到暫時性錯誤會自動重試的 HTTP session。"""
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _get_paged(session: requests.Session, url: str, params: dict | None) -> list[dict]:
    """依序跟著 @iot.nextLink 取回所有分頁。"""
    items: list[dict] = []
    while url:
        resp = session.get(url, params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            raise RuntimeError(f"SensorThings API 回傳 {resp.status_code}：{resp.text[:200]}")
        body = resp.json()
        items.extend(body.get("value", []))
        url = body.get("@iot.nextLink")
        params = None  # nextLink 已經帶好查詢參數
    return items


def list_cities(session: requests.Session | None = None) -> pd.Series:
    """列出每個縣市有幾個感測器（不論目前有沒有資料）。"""
    session = session or make_session()
    things = _get_paged(
        session, f"{BASE_URL}/Things", {"$select": "properties", "$top": 1000}
    )
    cities = pd.Series([t.get("properties", {}).get("city") for t in things], name="city")
    return cities.value_counts().rename("sensors")


def _station_record(thing: dict) -> dict:
    props = thing.get("properties", {})
    coords = (thing.get("Locations") or [{}])[0].get("location", {}).get("coordinates", [None, None])
    return {
        "station_id": props.get("stationID") or str(thing.get("@iot.id")),
        "device_name": props.get("deviceName"),
        "city": props.get("city"),
        "township": props.get("township"),
        "area_type": props.get("areaType"),
        "lon": coords[0],
        "lat": coords[1],
    }


def fetch_raw(city: str, session: requests.Session | None = None, page_size: int = 200) -> pd.DataFrame:
    """抓一個縣市所有感測器目前 API 上保留的逐筆觀測值（約最近 4～5 小時）。

    回傳長表：station 欄位 + variable、time（臺灣時間）、value。
    """
    session = session or make_session()
    name_filter = " or ".join(f"name eq '{n}'" for n in VARIABLES)
    params = {
        "$filter": f"({name_filter}) and Thing/properties/city eq '{city}'",
        "$select": "@iot.id,name",
        "$expand": (
            "Thing($select=@iot.id,properties;$expand=Locations($select=location)),"
            "Observations($select=phenomenonTime,result;$orderby=phenomenonTime desc;$top=1000)"
        ),
        "$top": page_size,
    }
    datastreams = _get_paged(session, f"{BASE_URL}/Datastreams", params)
    if not datastreams:
        raise ValueError(f"找不到「{city}」的感測器。縣市名稱請用「臺」，例如「臺中市」。")

    rows = []
    for ds in datastreams:
        station = _station_record(ds["Thing"])
        observations = ds.get("Observations", [])
        # 單一 Datastream 超過 1000 筆時，繼續跟著巢狀的 nextLink 取完
        next_link = ds.get("Observations@iot.nextLink")
        if next_link:
            observations += _get_paged(session, next_link, None)
        for obs in observations:
            rows.append({**station, "variable": VARIABLES[ds["name"]],
                         "time": obs["phenomenonTime"], "value": obs["result"]})

    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_convert(TZ)
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    return raw


def aggregate(raw: pd.DataFrame, freq: str = "5min") -> pd.DataFrame:
    """把逐分鐘的觀測值平均成固定時間區間，並把三個變數攤成欄位。

    n_obs 是該區間 PM2.5 的原始筆數，可用來判斷資料是否完整。
    """
    if raw.empty:
        return pd.DataFrame(columns=OBS_COLUMNS)
    raw = raw.assign(time=raw["time"].dt.floor(freq))
    keys = ["station_id", "time"]
    values = raw.pivot_table(index=keys, columns="variable", values="value", aggfunc="mean")
    counts = (raw[raw["variable"] == "pm25"].groupby(keys)["value"].count().rename("n_obs"))
    stations = raw.drop_duplicates("station_id").set_index("station_id")[STATION_COLUMNS[1:]]
    out = values.join(counts).reset_index().join(stations, on="station_id")
    for col in ("pm25", "rh", "temp", "n_obs"):
        if col not in out:
            out[col] = pd.NA
    out["n_obs"] = out["n_obs"].fillna(0).astype(int)
    return out[OBS_COLUMNS].sort_values(keys).reset_index(drop=True)


def fetch_city(city: str, freq: str = "5min", session: requests.Session | None = None) -> pd.DataFrame:
    """抓一個縣市目前可取得的資料，並平均成 `freq` 的時間區間。"""
    return aggregate(fetch_raw(city, session=session), freq=freq)


def save_daily(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    """依日期（臺灣時間）存成 `YYYY-MM-DD.csv.gz`，與既有檔案合併並去除重複。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for day, part in df.groupby(df["time"].dt.strftime("%Y-%m-%d")):
        path = out_dir / f"{day}.csv.gz"
        if path.exists():
            old = pd.read_csv(path, dtype={"station_id": str})
            old["time"] = pd.to_datetime(old["time"]).dt.tz_convert(TZ)
            part = pd.concat([old, part], ignore_index=True)
        # 同一時間區間保留筆數較多的那一筆（較晚抓取時，前一次可能只抓到區間的一部分）
        part = (part.sort_values("n_obs").drop_duplicates(["station_id", "time"], keep="last")
                .sort_values(["station_id", "time"]))
        part.to_csv(path, index=False, compression="gzip")
        written.append(path)
    return written


def collect(city: str, out_dir: Path, every_minutes: int | None, freq: str = "5min") -> None:
    """定時抓取並累積資料。every_minutes 為 None 時只抓一次。

    API 只保留約 4～5 小時，所以間隔要小於 4 小時（預設 120 分鐘）才不會漏資料。
    """
    session = make_session()
    while True:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            df = fetch_city(city, freq=freq, session=session)
            paths = save_daily(df, out_dir)
            print(f"[{started}] {city}：{df['station_id'].nunique()} 個感測器、{len(df)} 列 → "
                  + ", ".join(p.name for p in paths), flush=True)
        except Exception as exc:  # 收集器要能持續跑，單次失敗只記錄
            print(f"[{started}] {city} 抓取失敗：{exc}", file=sys.stderr, flush=True)
        if every_minutes is None:
            return
        time.sleep(every_minutes * 60)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="民生公共物聯網 空品微型感測器資料")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("cities", help="列出各縣市的感測器數量")

    snap = sub.add_parser("snapshot", help="抓一次目前可取得的資料（約最近 4～5 小時）")
    snap.add_argument("--city", required=True, help="縣市，例如 臺中市")
    snap.add_argument("--freq", default="5min", help="平均的時間區間，預設 5min")
    snap.add_argument("--out", required=True, type=Path, help="輸出 CSV 路徑")

    col = sub.add_parser("collect", help="定時抓取並依日期累積到 data/raw/")
    col.add_argument("--city", required=True)
    col.add_argument("--freq", default="5min")
    col.add_argument("--out-dir", type=Path, default=None, help="預設 data/raw/colife/<縣市>/")
    col.add_argument("--every-minutes", type=int, default=120, help="抓取間隔，必須小於 240")
    col.add_argument("--once", action="store_true", help="只抓一次就結束")

    args = parser.parse_args(argv)
    if args.command == "cities":
        print(list_cities().to_string())
    elif args.command == "snapshot":
        df = fetch_city(args.city, freq=args.freq)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"{args.city}：{df['station_id'].nunique()} 個感測器、{len(df)} 列，"
              f"時間 {df['time'].min()} ～ {df['time'].max()} → {args.out}")
    elif args.command == "collect":
        if args.every_minutes >= 240:
            parser.error("--every-minutes 必須小於 240，否則會漏掉 API 已刪除的資料")
        out_dir = args.out_dir or Path("data/raw/colife") / args.city
        collect(args.city, out_dir, None if args.once else args.every_minutes, freq=args.freq)


if __name__ == "__main__":
    main()
