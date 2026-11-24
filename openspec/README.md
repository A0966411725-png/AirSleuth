# OpenSpec 規格（Spec-Driven Development）

依老師 11/11 課程示範，期末用 OpenSpec 把「研究主張 → 系統需求 → 實作 → 驗證」串成可追蹤的證據鏈。格式依 OpenSpec 1.17（`schema: spec-driven`）。規格本文用英文，方便直接對應英文論文。

## 目錄

| 位置 | 內容 |
|---|---|
| `config.yaml` | 專案背景與撰寫規則（給人和 AI 共同遵守） |
| `specs/` | **目前已實作**的能力（9 項），每項都有需求與情境 |
| `changes/` | **期末要新增**的變更，每項都有 proposal、design、tasks 與新增的需求 |
| `traceability.md` | 追溯矩陣：研究問題與主張 → 需求 → 程式 → 測試或實驗 |

## 已實作的能力（specs）

| 能力 | 對應模組 | 說明 |
|---|---|---|
| `data-acquisition` | ④ | 每小時收集、憑證驗證與金鑰遮罩、國家測站回補、依查詢時間讀取 |
| `data-quality` | ④ | 品質旗標與可用比例 |
| `source-attribution` | ⑤ | Algorithm 2：B、L、E、C 與七種來源類型 |
| `sensor-calibration` | ⑤ | 分縣市線性＋濕度校正、留一站交叉驗證 |
| `pm25-forecasting` | ⑤ | 不偷看未來的 1／3／6 小時預測與基準比較 |
| `health-recommendation` | ⑥⑦ | Algorithm 3：敏感族群提前一級、依空間型態給行動、效益減風險排序 |
| `agent-answer` | ③⑧ | 四段式回答、數字可追溯、信心程度、資料不足時降級 |
| `llm-planner` | ②③ | Gemini 規劃：理解問題、追問、function calling、數字可追溯檢查、模型與確定性備援（2026-11-24 由變更歸檔） |
| `evaluation` | — | E1～E4 可重跑的實驗與比較基準（2026-11-24 由變更歸檔） |

## 期末變更（changes）

| 變更 | 狀態 |
|---|---|
| `add-llm-planner` | ✅ 已完成並歸檔（`changes/archive/2026-11-24-add-llm-planner/`），需求併入 `specs/llm-planner` |
| `add-evaluation-suite` | ✅ 已完成並歸檔（`changes/archive/2026-11-24-add-evaluation-suite/`），需求併入 `specs/evaluation` |
| `add-demo-site` | 網站已完成；等 repo 擁有者部署到 Streamlit Community Cloud、取得公開網址後歸檔 |

## 怎麼使用

```bash
npx @fission-ai/openspec@1.17.0 list            # 列出規格與變更
npx @fission-ai/openspec@1.17.0 validate --all  # 檢查格式
```

變更完成並通過測試後，用 `openspec archive <變更名稱>` 把新增的需求併入 `specs/`。
