"""產生 src/agent/districts.csv：臺中市、高雄市各行政區的代表座標，讓 Agent 把「前金區」這類地名換成經緯度。

座標來源：
1. 該區中央氣象署自動氣象站座標的平均（data/raw/cwa 已收集的站點清單）
2. 沒有氣象站的區，查 OpenStreetMap Nominatim 一次（遵守其使用政策：帶 User-Agent、每秒最多一次）

用法（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.build_districts
"""

from __future__ import annotations

import glob
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "agent" / "districts.csv"
DISTRICTS = {
    "臺中市": "中區 東區 南區 西區 北區 西屯區 南屯區 北屯區 豐原區 東勢區 大甲區 清水區 沙鹿區 梧棲區 后里區 神岡區 潭子區 "
              "大雅區 新社區 石岡區 外埔區 大安區 烏日區 大肚區 龍井區 霧峰區 太平區 大里區 和平區".split(),
    "高雄市": "新興區 前金區 苓雅區 鹽埕區 鼓山區 旗津區 前鎮區 三民區 楠梓區 小港區 左營區 仁武區 大社區 岡山區 路竹區 阿蓮區 "
              "田寮區 燕巢區 橋頭區 梓官區 彌陀區 永安區 湖內區 鳳山區 大寮區 林園區 鳥松區 大樹區 旗山區 美濃區 六龜區 內門區 "
              "杉林區 甲仙區 桃源區 那瑪夏區 茂林區 茄萣區".split(),
}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AirSleuth-course-project/1.0 (https://github.com/A0966411725-png/AirSleuth)"


def weather_station_centroids(city: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(ROOT / "data" / "raw" / "cwa" / city / "*.csv.gz")))
    w = pd.concat([pd.read_csv(f, dtype={"station_id": str}) for f in files]).drop_duplicates("station_id")
    return w.groupby("town")[["lat", "lon"]].mean().reset_index().rename(columns={"town": "district"})


def nominatim(city: str, district: str) -> tuple[float, float]:
    r = requests.get(NOMINATIM, params={"q": f"{district}, {city}, 臺灣", "format": "jsonv2", "limit": 1},
                     headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    hit = r.json()[0]
    time.sleep(1.1)
    return float(hit["lat"]), float(hit["lon"])


def main() -> None:
    rows = []
    for city, names in DISTRICTS.items():
        known = weather_station_centroids(city).set_index("district")
        for name in names:
            if name in known.index:
                lat, lon, source = known.at[name, "lat"], known.at[name, "lon"], "中央氣象署氣象站座標平均"
            else:
                (lat, lon), source = nominatim(city, name), "OpenStreetMap Nominatim"
            rows.append({"city": city, "district": name, "lat": round(lat, 5), "lon": round(lon, 5), "source": source})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"已輸出 {OUT.relative_to(ROOT)}：{len(out)} 區，其中 Nominatim {int((out['source'] != '中央氣象署氣象站座標平均').sum())} 區")


if __name__ == "__main__":
    main()
