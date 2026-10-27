# AirSleuth 原型輸出：taichung_clear

> 由 `python -m src.agent.demo --case taichung_clear` 以本地收集的真實資料產生。數字全部來自工具計算。

## 使用者情境

- 地點：臺中市西屯區（24.1438, 120.6844）
- 時間：2026-10-21 10:00
- 族群：asthma；活動：walk；預計 1 小時

## 回答

**結論：**臺中市西屯區目前 PM2.5 約 15 μg/m³（新版 AQI「普通」），屬於沒有明顯的污染事件。對氣喘患者的建議是：照原計畫進行散步或通勤。

**為什麼：**
- 2 km 內微型感測器中位數 16.2、15 km 區域背景 16.6 μg/m³，局部超量 E = -0.5；區域內 0% 的感測器比自己前 6 小時明顯升高（空間一致性 C）
- 8 km 內升高比例 0%、8～15 km 外環 0%
- 最近的國家測站「臺灣大道」（3.3 km）09:00 為 14 μg/m³，風速 1.6 m/s
- 氣象站「臺中」：風向 350°、風速 1.6 m/s、濕度 60%
- 未來趨勢（MLR）：1 小時後約 19、3 小時後約 19、6 小時後約 21 μg/m³
- 新版 AQI：良好 0–12.4、普通 12.5–30.4、對敏感族群不健康 30.5–50.4 μg/m³（S-029）
- 暴露量取決於濃度 × 換氣量 × 停留時間（S-034）

**建議：**
1. 照原計畫進行散步或通勤
2. 改到室內並關閉門窗（可開空氣清淨機）
3. 降低強度，改成散步或伸展

**信心：高。**2 km 內可信感測器 40 個；已用在地係數校正

**資料來源：**民生公共物聯網微型感測器；環境部國家空品測站；中央氣象署自動氣象站；查詢時間 2026-10-21 10:00

## 工具呼叫紀錄（可追溯性）

| 步驟 | 工具 | 主要結果 |
|---|---|---|
| 1 | `get_microsensors` | {"ok": true, "n_sensors": 757, "radius_km": 15, "latest_time": "2026-10-21 10:00:00+08:00", "stale_minutes": 0.0} |
| 2 | `assess_quality` | {"rows": 63894, "usable_ratio": 0.999, "rh_invalid_ratio": 0.289, "excluded_ratio": 0.001} |
| 3 | `source_attribution` | {"n_region": 751, "n_local": 40, "B": 16.65, "L": 16.18, "E": -0.47, "C": 0.0, "n_local_elevated": 0, "n_sub": 383, "C_sub": 0.0, "C_ring": 0.0, "time": "2026-10-21 10:00:00+08:00", "type": "no_clear_event"} |
| 4 | `get_station` | {"ok": true, "siteid": "88", "sitename": "臺灣大道", "distance_km": 3.3, "time": "2026-10-21 09:00:00+08:00", "pm25": 14.0, "rh": 60.0, "wind_speed": 1.6, "wind_dir": 345.0} |
| 5 | `get_weather` | {"ok": true, "station_id": "467490", "station_name": "臺中", "distance_km": 0.2, "time": "2026-10-21 10:00:00+08:00", "wind_dir": 350.0, "wind_speed": 1.6, "rh": 60.0, "temp": 30.0} |
| 6 | `calibrate` | {"calibrated": true, "pm25": 14.7, "note": "T-22 在地校正（臺中市，線性＋氣象站濕度 60%）"} |
| 7 | `forecast_trend` | {"ok": true, "siteid": "88", "base_time": "2026-10-21 09:00:00+08:00", "station_now": 14.0, "forecast": {"1": 17.9, "3": 18.7, "6": 20.1}} |
| 8 | `retrieve_knowledge` | {"rules": "4 條規則"} |
