# AirSleuth 空品偵探

> 結合 IoT 微型感測器與領域知識的空氣品質 Domain AI Agent
> 物聯網數據分析與應用｜期末專題（組繳交）

**目前階段：** Proposal，2026-11-04 繳交

## 繳交物一覽

| 繳交項目 | 位置 |
|---|---|
| Proposal Document | [proposal/AirSleuth_Proposal.docx](proposal/AirSleuth_Proposal.docx)（Word）、[PDF](proposal/AirSleuth_Proposal.pdf)、[Markdown](proposal/AirSleuth_Proposal.md)；各章原始檔在 `proposal/00～05` |
| Proposal PPT | [slides/README.md](slides/README.md)（線上簡報，可下載 .pptx／PDF，附講稿） |
| GitHub Repository | 本 repo |
| DESIGN.md | [DESIGN.md](DESIGN.md) |
| 口頭問答預演 | [docs/qa_rehearsal.md](docs/qa_rehearsal.md) |
| 文獻與來源查核 | [research/sources.md](research/sources.md)（63 筆） |

## 這個 Agent 要做什麼

使用者問：「為什麼今天我家附近 PM2.5 這麼高？明天能不能帶小孩去運動？」

AirSleuth 會：
1. 理解問題：地點、時間、使用者族群
2. 規劃要抓哪些資料：附近的微型感測器、國家測站、風向風速
3. 分析：判斷污染比較可能是**局部來源**（施工、交通、燃燒）還是**區域或境外傳輸**，並預測短期趨勢
4. 結合領域知識：AQI 健康指引、敏感族群建議
5. 給出**有證據、標明不確定性**的行動建議

詳細設計見 [DESIGN.md](DESIGN.md)。

## 快速試跑

```bash
pip install -r requirements.txt
python -m pytest -q tests                      # 33 個離線測試
python -m src.agent.demo --case kaohsiung      # Agent 原型：高雄 10/23 區域型事件（需要 data/raw 的收集資料）
python -m src.agent.schema                     # 給 LLM function calling 用的工具規格
python -m scripts.collection_status            # 資料收集狀況
```

原型輸出範例（含每一步的工具呼叫紀錄）見 [docs/agent_demo/](docs/agent_demo/)。

重建繳交文件：`python scripts/build_references.py` → `python scripts/build_proposal.py` → `python scripts/export_docx.py`。

## 儲存庫結構

```
DESIGN.md            系統設計文件
proposal/            Proposal 各章節與合併後的 Word／PDF
research/            文獻、數據、來源登記表（sources.md）
diagrams/            架構圖、流程圖（Mermaid 與 PNG）
src/                 程式碼：data（資料串接）、analytics（分析引擎）、knowledge（領域知識）、agent（Agent 原型）
tests/               離線測試
scripts/             資料收集排程、文件產生腳本
notebooks/           分析 notebook 與圖
docs/                作業規範摘要、分析紀錄（analysis/）、Agent 原型輸出、問答預演
data/sample/         小型資料樣本（原始資料放 data/raw/，不進版控）
slides/              簡報
```

## 開發環境

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

然後在 `.env` 填入 API key：環境部環境資料開放平臺（`MOENV_API_KEY`）與中央氣象署開放資料平臺（`CWA_API_KEY`）註冊會員後即可申請。

## 資料來源

| 來源 | 用途 |
|---|---|
| [民生公共物聯網 空品微型感測器 API](https://sta.colife.org.tw/STA_AirQuality_EPAIoT/v1.0/) | 約 1.1 萬個感測器的 PM2.5、溫度、濕度 |
| [環境部環境資料開放平臺](https://data.moenv.gov.tw/) | 國家空品測站 |
| [中央氣象署開放資料平臺](https://opendata.cwa.gov.tw/) | 風向、風速、降雨 |

## 資料收集排程

Windows 工作排程器**每小時**收集臺中市、高雄市的三種資料，存到 `data/raw/`（不進版控）：微型感測器（API 只保留約 4～5 小時）、國家測站小時值、自動氣象站（API 只給最新一筆）。國家測站的歷史資料可用 `python -m scripts.backfill_moenv --days 60` 補抓。

```bash
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

紀錄在 `data/raw/logs/scheduled.log`。

**想確認有沒有收到資料**：執行下面的指令，會列出每種資料收到幾筆、哪些小時有缺口，並畫出每小時覆蓋圖（`docs/collection_status.png`）。

```bash
.venv\Scripts\python -m scripts.collection_status --png docs/collection_status.png
```移除排程：`Unregister-ScheduledTask -TaskName "AirSleuth-colife-collect" -Confirm:$false`。
