"""Gemini API 用戶端（架構模組 ③ 的 LLM），只負責送出對話與工具規格、取回回應。

- 直接呼叫 REST API（`requests`），不另外安裝 SDK。
- API key 只從環境變數 `GEMINI_API_KEY`（或專案根目錄的 `.env`）讀取，放在 HTTP 標頭，不會出現在網址或紀錄裡。
- 依序嘗試 `GEMINI_MODELS` 列出的模型；遇到 503（服務忙碌）或 429（免費額度用完）就換下一個（DECISIONS D-09）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# 2026-11-24 實測同一題：3.5-flash-lite 7.6 秒、3.8-flash 238 秒（服務忙碌），兩者工具呼叫與數字都正確。
# demo 要即時回應，所以 lite 排第一；額度用完（429）或忙碌（503）才換較大的模型。
DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
RETRY_STATUS = {429, 500, 503}


class LLMUnavailable(RuntimeError):
    """沒有 key，或所有模型都暫時無法使用。"""


class LLMError(RuntimeError):
    """請求本身有錯（例如 400），換模型也不會好。"""


def api_key() -> str | None:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key or None


def configured_models() -> list[str]:
    load_dotenv(ROOT / ".env")
    env = os.environ.get("GEMINI_MODELS", "").strip()
    return [m.strip() for m in env.split(",") if m.strip()] or list(DEFAULT_MODELS)


class GeminiClient:
    def __init__(self, key: str | None = None, models: list[str] | None = None, timeout: float = 45,
                 session: requests.Session | None = None, retry_wait: float = 2.0):
        self.key = key if key is not None else api_key()
        self.models = models or configured_models()
        self.timeout = timeout
        self.session = session or requests.Session()
        self.retry_wait = retry_wait

    @property
    def available(self) -> bool:
        return bool(self.key)

    def generate(self, contents: list[dict], system: str | None = None, tools: list[dict] | None = None) -> tuple[dict, str]:
        """送出一輪對話，回傳（模型這一輪的 content, 實際回答的模型版本）。"""
        if not self.key:
            raise LLMUnavailable("沒有設定 GEMINI_API_KEY")
        body: dict = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]
        errors = []
        for model in self.models:
            for attempt in range(2):  # 503 先等一下重試一次，再換模型
                try:
                    r = self.session.post(URL.format(model=model), headers={"x-goog-api-key": self.key},
                                          json=body, timeout=self.timeout)
                except (requests.Timeout, requests.ConnectionError) as exc:  # 模型忙碌時常常卡住不回應：換下一個
                    errors.append(f"{model}: {type(exc).__name__}")
                    break
                if r.ok:
                    data = r.json()
                    candidates = data.get("candidates") or []
                    if not candidates or "content" not in candidates[0]:
                        errors.append(f"{model}: 沒有回傳內容（{candidates[0].get('finishReason') if candidates else '無候選'}）")
                        break
                    return candidates[0]["content"], data.get("modelVersion", model)
                message = _error_message(r)
                if r.status_code in RETRY_STATUS:
                    errors.append(f"{model}: HTTP {r.status_code}")
                    if r.status_code == 503 and attempt == 0:
                        time.sleep(self.retry_wait)
                        continue
                    break
                raise LLMError(f"{model}: HTTP {r.status_code} {message}")
        raise LLMUnavailable("；".join(errors))


def _error_message(r: requests.Response) -> str:
    try:
        return r.json().get("error", {}).get("message", "")[:200]
    except ValueError:
        return r.text[:200]
