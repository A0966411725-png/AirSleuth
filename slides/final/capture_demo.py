"""自動擷取 demo 網站的截圖，給期末簡報與影片用（Playwright 驅動本機已安裝的 Edge，不另外下載瀏覽器）。

先啟動網站：streamlit run app/streamlit_app.py --server.port 8501
再執行（Playwright 不在 requirements.txt，需要另外安裝）：
    python -m slides.final.capture_demo
輸出：slides/final/shots/*.png
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8501/"
OUT = Path(__file__).resolve().parent / "shots"


def wait_idle(page: Page, extra_ms: int = 1500) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180_000)
    page.wait_for_timeout(extra_ms)


def go(page: Page, label: str) -> None:
    page.get_by_text(label, exact=True).click()
    wait_idle(page)


def pick(page: Page, label: str, option: str) -> None:
    """Streamlit selectbox：點開後選文字符合的選項。"""
    page.get_by_label(label).click()
    page.get_by_role("option", name=option).click()
    wait_idle(page, 3000)


def ask(page: Page, question: str) -> None:
    box = page.get_by_placeholder("例如：我在臺中西屯區，想帶爸媽去散步，可以嗎？")
    box.fill(question)
    box.press("Enter")
    page.get_by_text("類型：", exact=False).last.wait_for(timeout=180_000)
    wait_idle(page)


def main() -> None:
    import sys
    parts = sys.argv[1:] or ["chat", "replay", "about"]
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
        page.goto(URL)
        wait_idle(page, 3000)

        if "chat" in parts:
            # 1. 對話：高雄區域型事件（LLM 規劃＋工具紀錄）
            ask(page, "我在高雄前金區，現在可以帶小孩去公園跑步嗎？")
            page.screenshot(path=OUT / "01_chat_kaohsiung.png", full_page=True)
            page.get_by_text("工具呼叫紀錄", exact=False).last.click()
            wait_idle(page)
            page.screenshot(path=OUT / "02_chat_trace.png", full_page=True)
            # 2. 對話：沒有說地點 → 追問
            page.reload()
            wait_idle(page, 3000)
            ask(page, "現在適合出去跑步嗎？")
            page.screenshot(path=OUT / "03_chat_clarify.png", full_page=True)

        if "replay" in parts:
            # 3. 事件重播：高雄區域型、臺中沿海次區域型、高雄彌陀局部型
            go(page, "🗺️ 真實事件重播")
            page.wait_for_timeout(6000)
            page.screenshot(path=OUT / "04_replay_kaohsiung.png", full_page=True)
            for name, label in (("05_replay_taichung.png", "臺中沿海 10/19 次區域型事件（2026-10-19 14:40）"),
                                ("07_replay_local.png", "高雄彌陀 11/17 局部型事件（2026-11-17 12:00）")):
                pick(page, "選擇事件", label)
                page.wait_for_timeout(6000)
                page.screenshot(path=OUT / name, full_page=True)

        if "about" in parts:
            go(page, "📊 資料與方法")
            page.screenshot(path=OUT / "06_about.png", full_page=True)
        browser.close()
    print("截圖已存到", OUT)


if __name__ == "__main__":
    main()
