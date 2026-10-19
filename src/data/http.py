"""共用的 HTTP 連線設定。

為什麼需要：Python 3.13 起，SSL 預設啟用 `VERIFY_X509_STRICT`，會拒絕缺少 Subject Key
Identifier 等欄位的憑證。環境部（data.moenv.gov.tw）與中央氣象署（opendata.cwa.gov.tw）
的憑證會因此驗證失敗（2026-10-19 實測）。

這裡**仍然完整驗證憑證鏈與主機名稱**，只關閉 3.13 新增的這一項嚴格檢查，
不是關閉 SSL 驗證（絕對不要用 `verify=False`）。
"""

from __future__ import annotations

import ssl

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 120


class _RelaxedStrictAdapter(HTTPAdapter):
    """驗證憑證鏈與主機名稱，但不套用 X.509 嚴格模式的 HTTPAdapter。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def gov_session() -> requests.Session:
    """給台灣政府開放資料平台用的 session：自動重試暫時性錯誤，並處理憑證問題。"""
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
    session = requests.Session()
    session.mount("https://", _RelaxedStrictAdapter(max_retries=retry))
    return session
