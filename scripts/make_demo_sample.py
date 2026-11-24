"""從本機收集的原始資料，截取 demo 網站用的小樣本（OpenSpec 變更 add-demo-site）。

公開部署時沒有 data/raw/（幾百 MB、不進版控），所以把幾個真實事件需要的資料切出來放到 data/sample/demo/，
檔案結構和 data/raw/ 相同，Agent 的工具只要把資料根目錄指到這裡就能重播事件。

每個事件時間截取：
- 微型感測器：兩個縣市的全部感測器，事件前 7 小時（來源判斷要 6 小時基準＋查詢當下）
- 國家測站：兩個縣市，最晚事件前 60 天（短期預測的訓練資料）
- 氣象站：兩個縣市，事件當天

用法（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.make_demo_sample
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src.agent.tools import TZ, _read

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "sample" / "demo"
CITIES = ["臺中市", "高雄市"]
EVENTS = [
    {"id": "kaohsiung_regional", "title": "高雄 10/23 區域型事件", "city": "高雄市", "place": "高雄市前金區",
     "lat": 22.6276, "lon": 120.2880, "time": "2026-10-23 11:30",
     "story": "整個高雄的感測器在上午一起升高，國家測站的小時值還沒發布。換地點沒有用，應該降低強度或改到室內。"},
    {"id": "taichung_subregional", "title": "臺中沿海 10/19 次區域型事件", "city": "臺中市", "place": "臺中市龍井區",
     "lat": 24.2369, "lon": 120.5385, "time": "2026-10-19 14:40",
     "story": "升高集中在沿海約 8 km 內，外圍大多沒有升高。換到 8 km 外是有效的建議。"},
    {"id": "taichung_clear", "title": "臺中 10/21 平常日", "city": "臺中市", "place": "臺中市西屯區",
     "lat": 24.1438, "lon": 120.6844, "time": "2026-10-21 10:00",
     "story": "沒有明顯的污染事件，照原計畫活動即可。"},
    {"id": "kaohsiung_local", "title": "高雄彌陀 11/17 局部型事件", "city": "高雄市", "place": "高雄市彌陀區",
     "lat": 22.78265, "lon": 120.23222, "time": "2026-11-17 12:00",
     "story": "附近 9 個感測器比區域背景高約 14 μg/m³，區域內其他地方沒有升高。換到 8 km 外就能避開。"},
]
KEYS = {"colife": "station_id", "moenv": "siteid", "cwa": "station_id"}


def save(df: pd.DataFrame, source: str, city: str) -> None:
    if df.empty:
        return
    out = OUT / source / city
    out.mkdir(parents=True, exist_ok=True)
    df = df.drop_duplicates([KEYS[source], "time"]).sort_values([KEYS[source], "time"])
    for day, part in df.groupby(df["time"].dt.strftime("%Y-%m-%d")):
        path = out / f"{day}.csv.gz"
        if path.exists():
            old = pd.read_csv(path, dtype={KEYS[source]: str})
            old["time"] = pd.to_datetime(old["time"], utc=True).dt.tz_convert(TZ)
            part = pd.concat([old, part]).drop_duplicates([KEYS[source], "time"]).sort_values([KEYS[source], "time"])
        part.to_csv(path, index=False, compression="gzip")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    times = [pd.Timestamp(e["time"], tz=TZ) for e in EVENTS]
    for city in CITIES:
        for t in times:
            save(_read("colife", city, t - pd.Timedelta(hours=7), t, RAW, "station_id"), "colife", city)
            day = t.normalize()
            save(_read("cwa", city, day, day + pd.Timedelta(hours=23, minutes=59), RAW, "station_id"), "cwa", city)
        latest = max(times)
        save(_read("moenv", city, min(times) - pd.Timedelta(days=61), latest, RAW, "siteid"), "moenv", city)
    (OUT / "events.json").write_text(json.dumps(EVENTS, ensure_ascii=False, indent=2), encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"已輸出 {OUT.relative_to(ROOT)}：{sum(1 for f in OUT.rglob('*.csv.gz'))} 個檔案，共 {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
