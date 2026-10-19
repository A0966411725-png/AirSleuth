# 04 Proposed Scheme 系統設計

> 負責：Claude（T-10）｜版本：2026-10-19 初稿
> 模組編號 ①～⑧ 與 `DESIGN.md` 第 4 節一致；圖檔原始碼在 `diagrams/`。
> 文中的 `S-xxx` 對應 `research/sources.md`；「實測」指本專題 T-07 對民生公共物聯網資料的實際分析。

## 4.0 設計原則：從研究發現推導出的五條規則

AirSleuth 的每個設計決定，都來自前面的文獻與實測，而不是憑空設計：

| # | 設計原則 | 依據 | 落在哪個模組 |
|---|---|---|---|
| P1 | **所有數字都必須來自工具查詢，不能由 LLM 自己生成** | LLM 會幻覺，工具呼叫可以降低幻覺（S-035、S-036） | ③④ |
| P2 | **先確認資料可不可信，再做判斷** | 微型感測器高估約 40%、濕度是最大誤差來源（S-008、S-009）；實測發現約 41% 的臺中感測器有時回報濕度為 0 | ④⑤ |
| P3 | **用當下的空間型態判斷來源，不引用單一的「境外佔 X%」** | 境外 vs 本地沒有單一正確數字，隨季節、地點、天氣而變（T-18 爭議 1）；先扣掉區域背景，剩下的才是局部（S-045、S-047） | ⑤ |
| P4 | **建議要結合使用者的族群、時間、地點與活動，而且要具體可行動** | 濃度不等於暴露量（S-034）；敏感族群風險較高（S-024、S-031）；只給數字時遵從率中位數只有 31%（S-028） | ⑥⑦ |
| P5 | **每個結論都附上證據與信心程度** | 不同資料來源的數字不同，民眾無法判斷（S-022）；專家共識是感測器讀數要附不確定性（S-011） | ⑦⑧ |

## 4.1 System Architecture

```mermaid
flowchart TB
    U["① User / Application Scenario"] --> Q["② Query / Input"]
    Q --> AG["③ Planner & Reasoning Agent（LLM）"]
    AG -->|呼叫工具| DA["④ Data Acquisition / Retrieval"]
    DA --> AN["⑤ Analytics Engine"]
    AN --> DE["⑦ Decision / Recommendation"]
    KN["⑥ Domain Knowledge Integration"] --> AN
    KN --> DE
    KN -.檢索依據.-> AG
    DE --> OU["⑧ Output & Interaction"]
    AG -.證據不足：追加查詢.-> DA
    DE -.信心太低：追問使用者.-> Q
    OU -.使用者回饋.-> AG
```

完整版（含每個模組的子元件）見 `diagrams/architecture.mmd`。

**架構的三個關鍵特徵：**
1. **LLM 只負責「規劃、推理與表達」**，計算、判斷門檻與數字全部交給確定性的程式（④⑤⑦），所以結果可以重現、可以驗證。
2. **領域知識（⑥）同時餵給分析與決策**，而不只是給 LLM 當背景資料。例如「濕度高時降低感測器信任度」是寫在分析流程裡的規則。
3. **三個回饋迴圈**：證據不足時追加查詢、信心太低時追問使用者、使用者回饋後重新規劃。

## 4.2 模組說明

### ① User / Application Scenario

| 使用者 | 典型問題 | 需要的能力 |
|---|---|---|
| 家長 | 「明天下午能帶小孩去公園嗎？」 | 預測、敏感族群門檻、時段建議 |
| 氣喘患者 | 「我家附近今天為什麼特別差？」 | 來源判斷、局部 vs 區域 |
| 運動者 | 「晚上 7 點去河堤跑步 1 小時 OK 嗎？」 | 暴露估算、運動取捨（S-033） |
| 長者照顧者 | 「要不要開窗、開空氣清淨機？」 | 室內外差異（S-034） |
| 一般通勤者 | 「我騎車上班會經過工業區，要注意什麼？」 | 路線上的局部熱點 |

### ② Query / Input
- **輸入：**自然語言提問，加上可選的使用者設定檔（常用地點、族群、是否有心肺疾病）。
- **處理：**把地址或地標轉成經緯度；把「明天下午」轉成時間窗；辨識活動類型與強度（散步、跑步、騎車）。
- **例外：**地點或時間不明確時，不用猜的，**直接追問使用者**（流程圖中的人機互動）。

### ③ Planner & Reasoning Agent
- **方法：**以 ReAct 方式運作（S-035）：LLM 交錯產生「推理」與「工具呼叫」，看到結果後再決定下一步。
- **可用的工具：**`get_microsensors`、`get_station`、`get_weather`、`assess_quality`、`analyze_spatial`、`forecast`、`retrieve_knowledge`、`recommend`。
- **證據充分性檢查：**可用感測器少於門檻（初步設定 5 個）時，自動擴大搜尋半徑或時間窗，最多兩次；仍不足就改用國家測站並降低信心。
- **防護規則：**回答中的每個數字都必須對應到某次工具呼叫的結果（P1），否則不輸出。

### ④ Data Acquisition / Retrieval

| 資料 | 來源 | 頻率 | 狀態 |
|---|---|---|---|
| 微型感測器 PM2.5、溫度、濕度 | 民生公共物聯網 SensorThings API（S-001） | 約每分鐘 | ✅ 已串接（`src/data/colife.py`） |
| 歷史資料 | 本地資料庫：Windows 排程每 2 小時收集臺中市、高雄市 | 5 分鐘平均 | ✅ 收集中 |
| 國家空品測站 | 環境部環境資料開放平臺（縣市小時值） | 每小時，可回溯數個月 | ✅ 已串接（T-08） |
| 風向、風速、溫濕度 | 中央氣象署自動氣象站 | 每小時（排程累積） | ✅ 已串接（T-08） |

- **為什麼需要本地資料庫：**實測發現 API 只保留最近約 4～5 小時，做趨勢與事件比對需要自己累積。
- **資料品質檢查**（`src/data/quality.py`，已實作）：標記缺值、負值、> 500 μg/m³、連續 1 小時數值不變、濕度無效。

### ⑤ Analytics Engine
1. **可信度評估：**每個感測器依濕度是否有效、資料完整度、與鄰近感測器的一致性給一個可信度分數。相對濕度高時（初步設定 > 70%），降低對絕對數值的信任（S-009、S-010）。
2. **測站錨定校正：**有國家測站時，用測站資料做濕度修正（S-008、S-011、S-041 的方法）；沒有測站時只看相對變化。濕度一律用國家測站或最近氣象站的濕度，不用微型感測器自己回報的濕度（T-22 實測：臺中共置點的感測器濕度平均 99.8%，同時測站只有 45～87%）。
3. **空間型態分析**（核心，借鏡 S-045 的「區域背景 + 局部事件」分解，以及 S-047 的背景正規化）：
   - **區域背景 B**：半徑 15 km 內可信感測器的 PM2.5 中位數
   - **局部濃度 L**：使用者所在位置半徑 2 km 內的中位數
   - **局部超量 E = L − B**
   - **空間一致性 C**：區域內「比自己前 6 小時基準升高超過 50%」的感測器比例（借鏡 S-046 用一致變化偵測區域事件）
4. **來源判斷：**依 E、C、鄰近感測器是否一起升高、風向，分成四類（見 Algorithm 2）。
5. **短期趨勢預測：**未來 1～6 小時。**基準模型用多元線性迴歸**（輸入：過去數小時 PM2.5、濕度、溫度、風速、時段），對照持續性預測（persistence）。T-11 已用國家測站 60 天資料做可行性驗證（見 4.5 節）。

> 門檻（15 km、2 km、50%、0.6、0.3 等）是依文獻與常識設定的初始值，**T-20 會用真實資料校準**；T-21 在國家測站的實測建議「升高」同時要求至少高 5 μg/m³，避免低濃度時的小波動被當成升高。

### ⑥ Domain Knowledge Integration

| 知識類型 | 內容 | 形式 | 來源 |
|---|---|---|---|
| 健康指引 | 2025 新版 AQI 的 PM2.5 門檻；各等級對一般民眾與敏感族群的建議 | 結構化規則（YAML） | S-029、S-032 |
| 專家觀念 | 8 個核心觀念（濃度 ≠ 暴露、沒有安全閾值、短期高峰、敏感族群、運動取捨、感測器看相對、天氣決定擴散、建議要具體） | 規則 + 說明文字 | T-06 |
| 爭議與不確定性 | 境外 vs 本地、感測器可信度、標準嚴格度的共識與未解問題 | 說明文字 | T-18 |
| 文獻 | 已查核的 51 筆來源摘要 | 文獻知識庫（RAG） | `research/` |

**為什麼不全部交給 LLM 自己判斷：**門檻與規則寫成結構化資料，結果才一致、可以驗證；LLM 只用來把規則套到使用者情境，並用口語解釋。

### ⑦ Decision / Recommendation
1. **暴露評估：**預測濃度 × 停留時間 × 活動強度（呼吸量），區分室內與室外。
2. **個人風險分級：**依新版 AQI 門檻，敏感族群提前一級警示（S-024、S-031、S-032）。
3. **候選行動與排序：**照常進行、改時段、改地點、降低強度、改到室內、開空氣清淨機、戴口罩。排序時考慮**運動的好處**：一般濃度下不建議直接取消運動（S-033）。
4. **信心程度：**高／中／低，由資料可信度、可用感測器數量、來源判斷的明確程度決定。信心低時，明確說明並給出較保守的建議。

### ⑧ Output & Interaction

固定的四段式回答，對應 P4、P5：

> **結論：**明天下午 3～5 點，公園附近 PM2.5 預估約 28 μg/m³（普通），可以去，但建議改到 4 點後、避免劇烈奔跑。
> **為什麼：**今天的升高屬於**區域型**：半徑 15 km 內 82% 的感測器同時上升，局部超量只有 2 μg/m³，同時吹東北風，比較像區域傳輸，而不是附近的污染源。
> **建議：**① 4 點後擴散條件較好；② 小孩有氣喘的話，隨身攜帶吸入劑；③ 回家後關窗、開清淨機。
> **信心：中。**可用感測器 37 個；目前濕度 78%，感測器可能高估，已用最近的國家測站校正。資料來源：民生公共物聯網、環境部測站、中央氣象署（查詢時間 14:05）。

（以上數字為說明用的範例，不是實際結果。）

## 4.3 Flowchart

```mermaid
flowchart TD
    S([開始：使用者提問]) --> I1["② 解析提問"]
    I1 --> C1{地點與時間明確？}
    C1 -- 否 --> H1["追問使用者"] --> I1
    C1 -- 是 --> P1["③ 規劃查詢"]
    P1 --> D1["④ 取得資料"]
    D1 --> C2{API 成功？}
    C2 -- 否 --> E1["例外：改用本地資料庫並標記可能過時"] --> C3
    C2 -- 是 --> Q1["資料品質檢查"] --> C3{可用感測器足夠？}
    C3 -- 否 --> X1["擴大半徑或時間窗"] --> D1
    C3 -- "否，已擴大 2 次" --> E2["例外：改用國家測站，信心降為低"]
    C3 -- 是 --> A1["⑤ 可信度評估與校正"]
    A1 --> A2["⑤ 空間型態分析與趨勢預測"]
    E2 --> A2
    A2 --> A4{"⑤ 來源判斷"}
    A4 --> K1["⑥ 檢索領域知識"]
    K1 --> R1["⑦ 暴露與風險評估"]
    R1 --> C4{敏感族群？}
    C4 -- 是 --> R2["使用較嚴格門檻"] --> R3
    C4 -- 否 --> R3["⑦ 產生並排序行動"]
    R3 --> C5{信心足夠？}
    C5 -- 否 --> R4["說明不確定性，給保守建議"] --> O1
    C5 -- 是 --> O1["⑧ 輸出四段式回答"]
    O1 --> C6{使用者追問？}
    C6 -- 是 --> I1
    C6 -- 否 --> Z([結束])
```

完整版（含來源判斷的四種分支與單一感測器異常的處理）見 `diagrams/flowchart.mmd`。

| 流程元素 | 對應位置 |
|---|---|
| Decision（判斷） | 地點時間是否明確、API 是否成功、感測器是否足夠、來源類型、是否敏感族群、信心是否足夠 |
| Loop（迴圈） | 擴大搜尋範圍（最多 2 次）；使用者追問後重新解析 |
| Exception（例外） | API 失敗改用本地資料庫；感測器不足改用國家測站 |
| Human Interaction（人機互動） | 地點不明確時追問；輸出後接受追問與回饋 |

## 4.4 Pseudocode

### Algorithm 1：AirSleuth 主流程

```
Algorithm 1: AirSleuth Domain AI Agent
Input : User query Q, optional user profile U (location, group, health conditions)
Output: Answer A = (conclusion, reasons & evidence, actions, confidence, sources)

01: intent ← ParseQuery(Q, U)                       ▷ location, time window, group, activity
02: if intent.location = ∅ or intent.time = ∅ then
03:     return AskUser("請問地點和時間？")             ▷ human interaction
04: radius ← 2 km; window ← 6 h; attempt ← 0
05: repeat                                          ▷ evidence sufficiency loop
06:     D ← GetMicrosensors(intent.location, 15 km, window)
07:     if D = FAILED then D ← LoadLocalCache(intent.location, window); stale ← true
08:     D ← AssessQuality(D)                        ▷ flag missing, stuck, invalid RH
09:     n ← CountReliable(D, intent.location, radius)
10:     if n < N_MIN then radius ← 2 × radius; attempt ← attempt + 1
11: until n ≥ N_MIN or attempt = 2
12: S ← GetStation(intent.location); W ← GetWeather(intent.location)
13: if n < N_MIN then D ← S; confidence_cap ← LOW   ▷ fallback to national station
14: D ← Calibrate(D, S)                             ▷ humidity correction anchored to station
15: src ← SourceAttribution(D, intent.location, W)  ▷ Algorithm 2
16: c_hat ← Forecast(D, W, intent.time)             ▷ MLR baseline, 1–6 h ahead
17: K ← RetrieveKnowledge(intent.group, intent.activity, src.type)
18: actions, conf ← Recommend(c_hat, src, intent, K)   ▷ Algorithm 3
19: conf ← min(conf, confidence_cap, Reliability(D, stale))
20: A ← ComposeAnswer(c_hat, src, actions, conf, sources = [D, S, W, K])
21: assert every number in A is traceable to a tool output   ▷ principle P1
22: return A
```

### Algorithm 2：來源判斷（局部 vs 區域）

```
Algorithm 2: SourceAttribution
Input : Reliable sensor readings D, target location p, weather W
Output: src = (type, local_excess, coherence, evidence)

01: R ← sensors in D within 15 km of p                ▷ regional set
02: L ← sensors in D within 2 km of p                 ▷ local set
03: B ← median PM2.5 of R at current time              ▷ regional background
04: E ← median PM2.5 of L − B                          ▷ local excess
05: for each sensor s in R do
06:     base_s ← median PM2.5 of s over previous 6 h
07:     rise_s ← (PM2.5_s − base_s) / base_s
08: C ← fraction of sensors in R with rise_s > 0.5    ▷ spatial coherence
09: if C ≥ 0.6 and E < max(5, 0.3·B) then type ← REGIONAL
10: else if E ≥ max(10, 0.5·B) and C < 0.3 then
11:     if at least 2 sensors in L exceed B + E/2 then type ← LOCAL
12:     else type ← SUSPECTED_SENSOR_FAULT            ▷ single-sensor spike
13: else if C ≥ 0.6 and E ≥ max(10, 0.5·B) then type ← MIXED
14: else type ← NO_CLEAR_EVENT
15: if type = REGIONAL and W.wind_dir ∈ NE and season ∈ {autumn, winter} then
16:     evidence ← evidence ∪ {"東北季風，可能有長程傳輸"}
17: return (type, E, C, evidence)
```

### Algorithm 3：個人化建議

```
Algorithm 3: Recommend
Input : Forecast c_hat over time window, source src, intent, knowledge K
Output: Ranked actions, confidence level

01: level ← AQIBand(c_hat, K.thresholds_2025)            ▷ 0–12.4 / 12.5–30.4 / 30.5–50.4 ...
02: if intent.group ∈ SENSITIVE then level ← level + 1   ▷ stricter for children, asthma, elderly
03: exposure ← c_hat × duration × BreathingRate(intent.activity)
04: candidates ← {AsPlanned, ShiftTime, ShiftPlace, LowerIntensity, MoveIndoor, Mask}
05: for each a in candidates do
06:     risk_a ← EstimateExposure(a, c_hat, src)          ▷ e.g., ShiftPlace helps only if src = LOCAL
07:     benefit_a ← ActivityBenefit(a, intent.activity)    ▷ exercise benefit (S-033)
08:     score_a ← benefit_a − λ(level) · risk_a
09: actions ← top-3 candidates by score
10: conf ← f(#reliable sensors, RH, src.type, forecast error)
11: if conf = LOW then actions ← actions ∪ {conservative advice}
12: return actions, conf
```

**設計重點：**Algorithm 3 第 6 行，**「換地點」只有在來源是局部型時才有用**；區域型事件時整個城市都差，換地點沒有意義，應該改時段或改到室內。這就是「判斷來源」對建議品質的直接影響，也是 AirSleuth 和只看 AQI 的工具最大的差別。

## 4.5 Technical Feasibility

### 已經完成的可行性證據（截至 2026-10-19）

| 項目 | 狀態 | 證據 |
|---|---|---|
| 即時資料取得 | ✅ | `src/data/colife.py` 可抓任一縣市；臺中市 1,130 個、高雄市 1,367 個感測器有即時資料 |
| 歷史資料累積 | ✅ | Windows 排程每小時收集微型感測器、國家測站、氣象站三種資料，已穩定執行 |
| 資料品質檢查 | ✅ | `src/data/quality.py` 與 3 個離線測試；臺中市實測：PM2.5 無負值與極端值，濕度無效 19.1%、疑似卡住 0.3% |
| 空間型態分析 | ✅ 初步 | `src/analytics/spatial.py` 實作 Algorithm 2，4 個合成資料測試通過；在真實資料上找到臺中西側沿海的群聚升高事件（局部 L 由約 18 升到 40 μg/m³，區域背景 B 只升到約 26），Algorithm 2 連續約 50 分鐘判斷為局部型，**附近的環境部沙鹿測站同時由 19 升到 32 μg/m³**，證實不是感測器雜訊；也正確分出單點飆高（1 個感測器達 111 μg/m³、鄰近 27 個正常）與持續性偏高的感測器（T-20） |
| 國家測站、氣象 | ✅ | 已取得 API key 並串接（`src/data/moenv.py`、`src/data/cwa.py`）；測站小時值可回溯數個月，已補抓 60 天；氣象站每小時收集 |
| 短期預測 | ✅ 初步 | `src/analytics/forecast.py`；國家測站 60 天、後 15 天測試：多元線性迴歸在 1、3、6 小時都優於持續性預測，6 小時 MAE 改善臺中 9%、高雄 17%（T-11）|
| 區域型事件 | ✅ 初步 | `src/analytics/regional.py`；國家測站 60 天中找到「多站同時升高、站間差異小」的候選日：臺中 7 天（例如 10/13，6 站日平均 22.9～30.9 μg/m³）、高雄 4 天（9/09～9/12）（T-21）|
| 感測器校正 | 🟡 單日 | `src/analytics/calibration.py`；10/19 一個下午的共置比對，留一站交叉驗證下「線性＋測站濕度」的 MAE 比不校正降低臺中 13%、高雄 54%；係數要等多天資料重估（T-22）|
| LLM 工具呼叫 | 成熟技術 | 主流 LLM 都支援 function calling；文獻已有空品領域的實作（S-036、S-037） |

### 預計的實驗設計（Experiments）

| 項目 | 設計 |
|---|---|
| Dataset | 本專題收集的臺中市、高雄市微型感測器資料（5 分鐘平均）；國家測站與氣象資料 |
| Case Study | 至少一個區域型事件、一個局部型事件（T-20），展示 Agent 的完整推理過程 |
| Baseline | ① 只看 AQI 等級的現有做法；② 沒有工具的純 LLM 聊天機器人；③ 有工具但沒有領域知識與品質檢查的 LLM |
| Evaluation Metrics | 來源判斷與人工標記事件的一致率；預測的 MAE（對照持續性預測）；回答中數字可追溯到工具輸出的比例（幻覺率）；建議的具體程度與正確性（依評分規準） |

### 預期成果（Expected Outcomes，非實驗結果）
- 相較於只看 AQI，AirSleuth 能額外回答「為什麼」與「我該怎麼做」。
- 相較於沒有工具的 LLM，回答中的數字都能追溯到資料來源，幻覺率預期大幅降低。
- 來源判斷在明顯的區域型與局部型事件上，預期能與人工標記一致；在混合型事件上可能較不穩定，這會在 Limitations 誠實說明。

### 已知風險與因應

| 風險 | 因應 |
|---|---|
| API 只保留約 4～5 小時 | 已用排程自行累積 |
| 濕度資料常無效 | 品質檢查標記；無效時改用氣象站濕度 |
| 單一感測器故障誤判成局部污染 | Algorithm 2 要求至少 2 個鄰近感測器一起升高；T-20 實測證實能分出單點飆高 |
| 長期偏高的感測器被誤判成事件 | T-20 加入「比自己前 6 小時基準升高」的條件，並把持續性偏高獨立分類 |
| 感測器自己回報的濕度不可靠 | T-20 發現臺中 84% 的正常資料濕度回報 90–100%；改用氣象署測站濕度做校正 |
| 事件大小不一，固定半徑不夠 | T-20 的沿海群聚約 8 km；期末加入次區域尺度或多尺度掃描 |
| 門檻是初始值 | T-20 用真實資料校準，並在報告中說明敏感度；T-21 已在國家測站找到區域型候選日，期末收集到新的區域型事件時同時比對測站與微型感測器的一致性 C |
| 校正係數只來自少量資料 | T-22 只有一個下午；期末累積 1 週以上後依日期切分重新驗證，並依城市分開估計 |
| LLM 幻覺 | 數字全部由工具產生；輸出前檢查可追溯性（Algorithm 1 第 21 行） |
