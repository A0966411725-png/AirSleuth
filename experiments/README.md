# 期末實驗（E1～E4）

對應 OpenSpec 變更 `openspec/changes/add-evaluation-suite`。每個實驗一個指令，結果寫到 `experiments/results/`；資料期間與亂數種子固定，所以重跑會得到相同的表格（E4 例外：LLM 回應快取在 `results/e4_cache/`）。

| 實驗 | 指令 | 輸出 | 約需時間 |
|---|---|---|---|
| E1 預測 | `python -m experiments.e1_forecast` | `e1_forecast.csv`、`e1_best_params.json`、`e1_forecast_mae.png` | 10～20 分鐘（Optuna 每個模型 30 次） |
| E2 校正 | `python -m experiments.e2_calibration` | `e2_calibration.csv`、`e2_coefficients.csv`、`e2_humidity_bias.csv`、`e2_calibration_scatter.png` | 3 分鐘 |
| E3 來源判斷 | `python -m experiments.e3_attribution` | `e3_summary.csv`、`e3_cases.csv`、`e3_confusion.csv`、`e3_real_events.csv`、`e3_attribution.png` | 5 分鐘 |
| E4 Agent | `python -m experiments.e4_agent` | `e4_scores.csv`、`e4_summary.csv`、`e4_agent.png`、`e4_cache/` | 30 分鐘（免費額度限速） |

**需求：**
- 本機的 `data/raw/`（由排程收集，不進版控）
- E4 另外需要 `.env` 的 `GEMINI_API_KEY`
- 套件版本見 `requirements.txt`：scikit-learn 1.9.1、optuna 5.0.0、scipy 1.16.3

## 資料期間

| 資料 | 期間 | 用在 |
|---|---|---|
| 國家測站 | 2026-08-20 ～ 11-24 13:00 | E1（訓練 8/20～10/13、調參 10/14～10/26、測試 10/27～11/24） |
| 微型感測器 | 2026-10-19 11:00 ～ 11-18 15:35（528 小時有資料） | E2、E3、E4 |
| 氣象站 | 2026-10-19 ～ 11-24 | E2（濕度）、E4 |

詳見 `docs/analysis/T-25_期末實驗資料集.md`。

## 模型與設定

- **E1**：所有測站合併訓練；樹模型以 Optuna TPE（seed 42）在驗證期調參，選定後用「訓練＋驗證」重訓，測試期只評估一次。
- **E3 注入情境**，每個背景 11 種：
  - 局部型：2 km 內 +10／15／25
  - 次區域型：6 km 內 +8／12／20
  - 區域型：15 km 內 +8／12／20，加上雜訊
  - 單一感測器 +40
  - 不注入
- **E3 比較方法**：消融（拿掉 8 km 層）、只看 AQI、只看最近感測器。
- **E4**：
  - LLM 一律用 `gemini-3.5-flash-lite`，回應中記錄 modelVersion。
  - 第一優先行動由同一模型擔任評審判斷，評審準確度用 AirSleuth 回答的已知排序驗證（輸出時會印出）。
  - 標準答案是確定性流程依環境部指引的排序。

## 結果

彙整與討論見 `docs/analysis/期末實驗結果.md`；論文版見 `paper/`。
