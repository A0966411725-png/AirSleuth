# 簡報

## 期末簡報（`final/`）

- **簡報檔：**`final/AirSleuth_期末簡報.pptx`，由 `python -m slides.final.build_final_deck` 產生。
  - 超過 20 頁，每頁的備忘稿就是講稿。
  - 實驗數字直接讀 `experiments/results/`。
- **版面：**依老師課堂建議，黑底、白字、橘色標題、黃色重點。
- **demo 截圖：**`final/shots/`，由 `python -m slides.final.capture_demo` 擷取。
  - 需要先啟動網站，並另外安裝 Playwright；它會驅動本機的 Edge。
- **影片：**`python -m slides.final.make_video`
  - 講稿用 Gemini 語音合成，每段再轉回文字核對內容。
  - 用 PowerPoint 匯出 1080p MP4。
  - 影片檔很大，不進版控，由使用者上傳 YouTube。

## Proposal 簡報（`deck/`）

- **線上簡報（可播放、下載成 .pptx 或 PDF）：**https://claude.ai/artifact/CPZf8ZFZzmUzniVvqjYkGx
  - 目前是 private，只有 repo 擁有者能開。要給組員看，請在簡報頁面右上角的 Share 選單分享。
- **原始檔：**`deck/project/`（`deck.json` 是索引，`slides/*.html` 一張投影片一個檔）
- **講稿：**每張投影片的 `<aside>` 是演講者備註

| # | 內容 | 對應 Proposal 章節 |
|---|---|---|
| 1–4 | 封面、三個數字、三個問題、核心主張 | 01 Introduction |
| 5–7 | AI 技術相關研究、領域相關研究、Research Gap | 02 Related Work |
| 8–9 | 五個核心思維、三大爭論 | 03 Deep Research |
| 10–13 | 設計原則、系統架構、流程圖、Algorithm 2 | 04 Proposed Scheme |
| 14–17 | 真實資料：臺中、高雄事件、資料品質、初步結果 | 04 Technical Feasibility |
| 18 | Agent 原型 | 04 Technical Feasibility |
| 19–20 | 實驗設計、總結與 Q&A | 00 Abstract E、F 段 |
