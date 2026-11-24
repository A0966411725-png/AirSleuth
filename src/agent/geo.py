"""把使用者說的地點換成縣市與經緯度（Agent 的 resolve_place 工具）。

座標表 `districts.csv` 由 `scripts/build_districts.py` 產生：有氣象站的區取氣象站座標平均，其餘 8 區查 OpenStreetMap。
目前只支援有收集資料的臺中市、高雄市；其他縣市會明確回報「不支援」，不會猜測。
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.spatial import haversine_km

DISTRICTS = pd.read_csv(Path(__file__).with_name("districts.csv"))
SUPPORTED = ["臺中市", "高雄市"]
CITY_NAMES = {"臺中": "臺中市", "高雄": "高雄市"}
OTHER_CITIES = ["臺北", "新北", "基隆", "桃園", "新竹", "苗栗", "彰化", "南投", "雲林", "嘉義", "臺南", "屏東",
                "宜蘭", "花蓮", "臺東", "澎湖", "金門", "連江", "馬祖"]
COORD = re.compile(r"(\d{2}\.\d+)\s*[,，、 ]\s*(\d{3}\.\d+)")
MAX_KM_FROM_CITY = 25.0   # 座標離最近的行政區代表點超過這個距離，就當成不在支援範圍


def _normalize(text: str) -> str:
    return text.replace("台", "臺")


def _match_district(text: str, city: str | None) -> pd.Series | None:
    rows = DISTRICTS if city is None else DISTRICTS[DISTRICTS["city"] == city]
    best = None
    for _, row in rows.iterrows():
        name = row["district"]
        base = name[:-1]  # 去掉「區」
        # 一個字的區名（中、東、南、西、北）一定要帶「區」才算，避免把「臺中」誤判成中區
        if name in text or (len(base) >= 2 and base in text):
            if best is None or len(name) > len(best["district"]):
                best = row
    return best


def resolve_place(text: str) -> dict:
    """回傳 ok／city／district／lat／lon；找不到時說明缺什麼。"""
    t = _normalize(text)
    m = COORD.search(t)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        d = haversine_km(lat, lon, DISTRICTS["lat"].to_numpy(), DISTRICTS["lon"].to_numpy())
        i = int(np.argmin(d))
        if d[i] > MAX_KM_FROM_CITY:
            return {"ok": False, "reason": "unsupported", "message": f"這個座標不在支援範圍（{'、'.join(SUPPORTED)}）"}
        row = DISTRICTS.iloc[i]
        return {"ok": True, "city": row["city"], "district": row["district"], "lat": lat, "lon": lon,
                "source": "使用者提供的座標"}
    city = next((full for short, full in CITY_NAMES.items() if short in t), None)
    other = next((c for c in OTHER_CITIES if c in t), None)
    if other and city is None:
        return {"ok": False, "reason": "unsupported", "message": f"目前只支援{'、'.join(SUPPORTED)}，沒有{other}的資料"}
    row = _match_district(t, city)
    if row is not None:
        return {"ok": True, "city": row["city"], "district": row["district"], "lat": float(row["lat"]),
                "lon": float(row["lon"]), "source": f"行政區代表點（{row['source']}）"}
    if city:
        return {"ok": False, "reason": "need_district", "city": city,
                "message": f"請告訴我在{city}的哪一區，才能找附近的感測器"}
    return {"ok": False, "reason": "not_found", "message": f"找不到這個地點；目前支援{'、'.join(SUPPORTED)}的各行政區"}
