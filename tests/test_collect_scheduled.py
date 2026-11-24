"""排程收集的紀錄不能留下 API key（錯誤訊息裡的網址會帶金鑰）。"""

from scripts.collect_scheduled import redact


def test_redact_hides_api_keys_in_error_urls():
    moenv = "Max retries exceeded with url: /api/v2/aqx_p_432?api_key=abc-123&format=json (Caused by X('y'))"
    cwa = "O-A0001-001?Authorization=CWA-XYZ-9&format=JSON'"
    assert redact(moenv) == "Max retries exceeded with url: /api/v2/aqx_p_432?api_key=***&format=json (Caused by X('y'))"
    assert redact(cwa) == "O-A0001-001?Authorization=***&format=JSON'"
    assert redact("臺中市 微型感測器 失敗：SSL 憑證過期") == "臺中市 微型感測器 失敗：SSL 憑證過期"
