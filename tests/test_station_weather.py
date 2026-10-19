"""src.data.moenv、src.data.cwa 的離線測試（不呼叫真實 API）。"""

import math

import pandas as pd

from src.data import cwa, moenv


def test_moenv_parse_hourly_pivots_and_cleans():
    rec = lambda item, value, hour="15:00": {  # noqa: E731
        "siteid": "33", "sitename": "沙鹿", "county": "臺中市", "itemid": "x",
        "itemengname": item, "monitordate": f"2026-10-19 {hour}", "concentration": value}
    records = [rec("PM2.5", "32"), rec("RH", "68"), rec("WIND_DIREC", "328"), rec("WIND_SPEED", "2.8"),
               rec("NO2", "10"),            # 不需要的測項要被丟掉
               rec("PM2.5", "x", "14:00"),  # 無效值標記要變成 NaN
               rec("RH", "70", "14:00")]
    sites = pd.DataFrame({"siteid": ["33"], "lon": [120.57], "lat": [24.23]})
    out = moenv.parse_hourly(records, sites)
    assert list(out.columns) == moenv.STATION_COLUMNS
    assert len(out) == 2
    row = out[out["time"].dt.hour == 15].iloc[0]
    assert row["pm25"] == 32 and row["rh"] == 68 and row["wind_dir"] == 328 and row["lon"] == 120.57
    assert math.isnan(out[out["time"].dt.hour == 14].iloc[0]["pm25"])


def test_cwa_parse_stations_handles_missing_codes():
    body = {"records": {"Station": [{
        "StationId": "C0FA30", "StationName": "梧棲",
        "ObsTime": {"DateTime": "2026-10-19T16:00:00+08:00"},
        "GeoInfo": {"CountyName": "臺中市", "TownName": "梧棲區", "Coordinates": [
            {"CoordinateName": "TWD67", "StationLatitude": 24.0, "StationLongitude": 120.0},
            {"CoordinateName": "WGS84", "StationLatitude": 24.256, "StationLongitude": 120.523}]},
        "WeatherElement": {"WindDirection": 339, "WindSpeed": 4.1, "AirTemperature": 27.8,
                           "RelativeHumidity": 81, "AirPressure": -99},
    }]}}
    out = cwa.parse_stations(body)
    row = out.iloc[0]
    assert row["lat"] == 24.256 and row["wind_dir"] == 339 and row["rh"] == 81
    assert math.isnan(row["pressure"])  # -99 是缺值
    assert str(row["time"].tz) == "Asia/Taipei"
