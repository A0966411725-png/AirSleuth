# AirSleuth 空品偵探

> 結合 IoT 微型感測器與領域知識的空氣品質 Domain AI Agent
> 物聯網數據分析與應用｜期末專題（組繳交）

使用者用中文問「我在高雄前金區，現在可以帶小孩去公園跑步嗎？」，AirSleuth 會做四件事：
1. 用 Gemini 理解問題並決定要查哪些資料。
2. 用確定性的程式完成品質檢查、在地校正、**判斷污染是局部、次區域還是整個區域的升高**、短期預測。
3. 依族群與活動排出具體建議。
4. 給出結論、原因、建議、信心四段式回答。

回答中的每個數字都能在工具紀錄裡找到出處。

**狀態：** 期末版（2026-11-24）

## 期末繳交物

| 繳交項目 | 位置 |
|---|---|
| GitHub（完整程式、資料來源、執行與測試方式） | 本 repo |
| Demo site | https://airsleuth.streamlit.app （程式在 `app/streamlit_app.py`，部署步驟見下方「Demo 網站」） |
| 研討會格式論文初稿（ICEIB 2027，Engineering Proceedings 範本） | [paper/AirSleuth_ICEIB2027_draft.docx](paper/AirSleuth_ICEIB2027_draft.docx)、[PDF](paper/AirSleuth_ICEIB2027_draft.pdf)；原稿 [paper/airsleuth_iceib2027.md](paper/airsleuth_iceib2027.md) |
| 期末簡報（> 20 頁，附講稿） | [slides/final/](slides/final/) |
| 影片（> 10 分鐘，AI 語音旁白） | `slides/final/AirSleuth_期末報告影片.mp4`（檔案大，不進版控；上傳 YouTube） |
| DESIGN.md | [DESIGN.md](DESIGN.md) |
| 實驗（Dataset、Metrics、Results、Comparison） | [experiments/](experiments/README.md)、[docs/analysis/期末實驗結果.md](docs/analysis/期末實驗結果.md) |
| 規格驅動開發（OpenSpec） | [openspec/](openspec/README.md) |
| Proposal 階段（10%） | [proposal/](proposal/)、[slides/README.md](slides/README.md) |

## 主要結果

| 實驗 | 結果 |
|---|---|
| E1 預測（18 站，測試 10/27～11/24） | 6 小時 MAE：持續性 5.69 → MLR 4.97 → 梯度提升樹 4.74 μg/m³（−17%） |
| E2 在地校正（留一站交叉驗證） | 臺中 MAE −20%、高雄 −14%；兩市偏差方向相反，必須在地化 |
| E3 來源判斷（880 個半合成案例＋真實事件） | AirSleuth 正確率 84%（只看 AQI 19%、最近感測器 51%）；單一感測器異常誤判成局部 1% |
| E4 Agent（40 題 × 4 種做法） | 回答中的數字 100% 可追溯；建議與官方指引一致 **96%**（純 LLM 25%、LLM＋原始資料工具 33%、只看 AQI 46%）；純 LLM 有 46% 的回答編造即時數值 |

## 快速試跑

```bash
pip install -r requirements.txt
python -m pytest -q tests                      # 離線測試（不打真實 API）
streamlit run app/streamlit_app.py             # demo 網站（用 data/sample/demo 的真實事件樣本）
python -m src.agent.ask "我在高雄前金區，現在可以帶小孩去公園跑步嗎？" --time "2026-10-23 11:30" --trace
python -m src.agent.demo --case kaohsiung      # 確定性流程（不用 LLM）
python -m scripts.collection_status            # 資料收集狀況
```

- 有 `GEMINI_API_KEY`（填在 `.env`，到 https://aistudio.google.com/apikey 免費申請）時，由 Gemini 理解問題並決定呼叫哪些工具。
- 沒有 key 時自動改用確定性流程，網站與指令一樣能用。

## Demo 網站

公開網址：**https://airsleuth.streamlit.app**

網站有三頁：
- **問 AirSleuth**：用中文提問，回答附上工具呼叫紀錄。
- **真實事件重播**：顯示感測器地圖、空間指標，並比較不同族群拿到的建議。
- **資料與方法**：說明資料來源與方法。

網站使用 `data/sample/demo/` 的四個真實事件樣本：高雄 10/23 區域型、臺中沿海 10/19 次區域型、臺中 10/21 平常日、高雄彌陀 11/17 局部型。部署時不需要原始資料。

**部署到 Streamlit Community Cloud**（由 repo 擁有者操作一次）：
1. 用 GitHub 帳號登入 https://share.streamlit.io ，按 **Create app**。
2. Repository 選 `A0966411725-png/AirSleuth`，Branch 選 `main`，Main file path 填 `app/streamlit_app.py`。
3. **Advanced settings** 的 Python version 選 3.13；Secrets 填入一行 `GEMINI_API_KEY = "你的 key"`（不填也能用，只是不啟用 LLM）。
4. 按 Deploy，幾分鐘後會得到公開網址。免費方案閒置一段時間後，第一次開啟要等幾十秒。

重建 demo 樣本（需要本機的 `data/raw/`）：`python -m scripts.make_demo_sample`。

## 儲存庫結構

```
DESIGN.md            系統設計文件（期末版）
app/                 Streamlit demo 網站
src/                 程式：data（資料串接）、analytics（分析引擎）、knowledge（領域知識與建議）、agent（LLM 規劃器與工具）
tests/               離線測試
experiments/         期末實驗 E1～E4 與結果
openspec/            規格驅動開發：需求、情境、變更、追溯矩陣
paper/               ICEIB 2027 論文初稿（範本、原稿、圖、轉換程式）
slides/              簡報（Proposal 線上版；final/ 為期末簡報與影片工具）
scripts/             資料收集排程、樣本與文件產生腳本
notebooks/           Proposal 階段的分析 notebook
docs/                作業規範摘要、分析紀錄（analysis/）、原型輸出、問答預演
research/            文獻、數據、來源登記表（sources.md）
proposal/            Proposal 各章節與 Word／PDF
diagrams/            架構圖、流程圖
data/sample/         demo 與測試用的小型資料（原始資料放 data/raw/，不進版控）
```

## 開發環境

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

然後在 `.env` 填入 API key：
- 環境部環境資料開放平臺：`MOENV_API_KEY`
- 中央氣象署開放資料平臺：`CWA_API_KEY`
- 選用：Google AI Studio 的 `GEMINI_API_KEY`

金鑰只放在 `.env`（不進版控）；程式的錯誤紀錄會遮掉網址中的金鑰。

## 資料來源

| 來源 | 用途 |
|---|---|
| [民生公共物聯網 空品微型感測器 API](https://sta.colife.org.tw/STA_AirQuality_EPAIoT/v1.0/) | 約 1.1 萬個感測器的 PM2.5、溫度、濕度（2026-11-21 起官方憑證過期，暫停收集） |
| [環境部環境資料開放平臺](https://data.moenv.gov.tw/) | 國家空品測站 |
| [中央氣象署開放資料平臺](https://opendata.cwa.gov.tw/) | 風向、風速、濕度 |

## 資料收集排程

Windows 工作排程器**每小時**收集臺中市、高雄市的三種資料，存到 `data/raw/`（不進版控）：
- 微型感測器：API 只保留約 4～5 小時。
- 國家測站小時值。
- 自動氣象站：API 只給最新一筆。

國家測站的歷史資料可用 `python -m scripts.backfill_moenv --days 60` 補抓。

```bash
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

紀錄在 `data/raw/logs/scheduled.log`。下面的指令會列出每種資料收到幾筆、哪些小時有缺口，並畫出每小時覆蓋圖：

```bash
.venv\Scripts\python -m scripts.collection_status --png docs/collection_status.png
```

移除排程：`Unregister-ScheduledTask -TaskName "AirSleuth-colife-collect" -Confirm:$false`。
