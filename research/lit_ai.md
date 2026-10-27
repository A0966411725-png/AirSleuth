# T-05 AI 技術端文獻

> 負責：Claude｜日期：2026-10-19｜用途：Related Work 的 AI 技術那一半、Research Gap
> 查核狀態：✅ 已讀摘要核對；🟡 只確認書目（摘要無法讀取），數字引用前需人工核對。編號對應 `research/sources.md`。
> 感測器校正的經典研究（S-008～S-011）已在 T-18 整理，這裡只補充機器學習方法。

## 主題 1：以大型語言模型為核心的 AI Agent

### S-035 ReAct：推理與行動交錯（✅）
- **作者、年份：**Yao, Zhao, Yu, Du, Shafran, Narasimhan, Cao｜arXiv 2210.03629（2022），發表於 ICLR 2023
- **連結：**https://arxiv.org/abs/2210.03629
- **Problem：**LLM 的推理（chain-of-thought）和行動（呼叫工具）過去是分開研究的，只推理容易幻覺，只行動缺乏規劃。
- **AI Method：**讓 LLM 交錯產生「推理軌跡」和「行動」（例如查詢 Wikipedia API），根據觀察結果更新計畫。
- **Domain Knowledge：**無（通用方法）。
- **Dataset：**HotpotQA、FEVER、ALFWorld、WebShop。
- **Findings：**在問答與事實查核上，透過呼叫外部 API 取得資訊，**減少了只靠推理時的幻覺與錯誤傳遞**，軌跡也更容易被人理解。
- **Limitation：**工具是通用的，沒有領域知識；推理品質仍依賴模型本身。（推論）
- **對 AirSleuth 的意義：**③ Planner & Reasoning Agent 的基本運作方式：先想要查什麼 → 呼叫資料工具 → 看結果 → 決定下一步。

### S-036 用 MCP 讓 LLM 操作空品監測系統（✅）
- **作者、年份：**Pan & Nipu｜arXiv 2511.03706（2025）
- **連結：**https://arxiv.org/abs/2511.03706
- **Problem：**傳統空品監測系統的視覺化對一般人太難懂；LLM 會幻覺，在安全攸關的領域不可靠。
- **AI Method：**透過 Model Context Protocol（MCP）把系統功能開放成可被發現的「工具」，讓 LLM 主動查詢**即時感測器資料**再回答，而不是靠預訓練知識。
- **Domain Knowledge：**有限，著重在介面與資料存取。
- **Dataset：**系統自己的即時感測器資料；由專家評分。
- **Findings：**專家評分事實正確性 4.78、完整性 4.82、幻覺程度 4.84（滿分 5，越高越少幻覺）。
- **Limitation：**著重「查詢與呈現資料」，**沒有判斷污染來源，也沒有處理感測器資料品質**；評估是專家主觀評分，規模小。（推論）

### S-037 VayuChat：用對話分析印度空品資料（✅）
- **作者、年份：**Acharya, Pisharodi, Mondal, Rafiuddin, Batra｜arXiv 2511.01046（2025）
- **連結：**https://arxiv.org/abs/2511.01046
- **Problem：**決策者難以把分散的空品資料轉成決策，現有工具需要專業能力。
- **AI Method：**LLM 把自然語言問題轉成**可執行的 Python 程式碼**與互動圖表。
- **Domain Knowledge：**整合印度國家測站（CPCB）、人口與國家清淨空氣計畫的經費資料。
- **Dataset：**CPCB 監測站資料。
- **Findings：**示範系統，已公開部署。
- **Limitation：**以政策分析為主，**對象是決策者與研究者，不是一般民眾的即時健康決策**；只用國家測站，沒有微型感測器；屬於展示論文，沒有量化評估。（推論）

### S-038 EnQyMo：LLM 讀法規與文獻，產生個人化室內空品警示（✅）
- **作者、年份：**Vieira et al.｜arXiv 2609.17954（2026）
- **連結：**https://arxiv.org/abs/2609.17954
- **Problem：**室內空品監測多半是被動的，不會主動通知受影響的人。
- **AI Method：**IoT 中介軟體 + **多個 LLM 組成的代理**，解讀法規標準與科學文獻，自動找出關鍵暴露門檻；用藍牙信標定位使用者，只通知在受污染空間裡的人。
- **Domain Knowledge：**室內空品法規、CO₂ 與污染物的健康風險。
- **Findings：**示範依位置產生個人化警示的架構。
- **Limitation：**針對**室內**辦公空間；沒有處理室外污染來源與區域傳輸。（推論）
- **對 AirSleuth 的意義：**證明「LLM 讀領域知識 + IoT 資料 + 依位置個人化」是可行方向；AirSleuth 把它延伸到室外與來源判斷。

### S-039 JARVIS：LLM 分兩階段回答感測器資料問題（✅）
- **作者、年份：**Lee et al.｜arXiv 2507.04748（2025）
- **連結：**https://arxiv.org/abs/2507.04748
- **Problem：**讓非專家也能用自然語言詢問空調系統（HVAC）的感測器資料，需要整合即時資料、領域知識與多步推理。
- **AI Method：**Expert-LLM 把問題轉成結構化執行指令 → Agent 執行 **SQL 資料擷取、統計處理**、產生回答；加入「依情境注入領域知識」與「由下而上的規劃」。
- **Domain Knowledge：**HVAC 領域知識與部署資訊。
- **Dataset：**商用 HVAC 系統的真實資料，與 HVAC 專家建立的標準問答集。
- **Findings：**以專家問答集驗證框架的有效性。
- **Limitation：**不是空品領域；但架構（規劃者 + 執行者 + 領域知識注入）可以直接借鏡。（推論）

### S-040 LLM 與都市運算綜述（✅）
- **作者、年份：**Li, Xia, Ren, Tang, Chen, Xu et al.｜arXiv 2504.02009（2025）
- **連結：**https://arxiv.org/abs/2504.02009
- **重點：**整理 LLM 在交通、公共安全、**環境監測**等都市領域的應用，指出現有方法在泛化、擴展性與情境理解上的限制，並討論 LLM 的功能角色與實作模式。
- **Limitation：**綜述性質，沒有針對空品來源判斷的具體方法。

## 主題 2：低成本感測器的機器學習校正

### S-041 台灣 39 個感測器的隨機森林校正（✅）
- **作者、年份：**Wang, Lung & Liu｜*Sensors*, 20(17), 5002（2020）
- **連結：**https://doi.org/10.3390/s20175002
- **Problem：**很多低成本感測器沒有經過嚴謹校正就上線；而且多數地點附近沒有國家測站可以比對。
- **AI Method：**比較多元線性迴歸（MLR）、支援向量迴歸（SVR）、隨機森林迴歸（RFR），用**台灣國家測站的 PM2.5** 校正。
- **Domain Knowledge：**感測器偏差在日夜之間有不同型態。
- **Dataset：**台灣 39 個感測器，2017 年 7 月到 2018 年 12 月。
- **Findings：**RFR 最好，速度也比 SVR 快 35 倍；加入「夜間型態」的 RFR，RMSE 從 18.4 ± 6.5 降到 **5.9 ± 2.0 μg/m³**。這是第一個在沒有測站的地點校正、並用實驗室校正資料驗證的研究。
- **Limitation：**只有 39 個感測器、單一型號；資料是 2017–2018 年。

### S-043 隨機森林、XGBoost 在不同環境條件下的表現（✅）
- **作者、年份：**Wathore, Wanjari, Chakraborty & Labhsetwar｜*Aerosol and Air Quality Research*（2026）
- **連結：**https://doi.org/10.1007/s44408-026-00094-6
- **AI Method：**RF、XGBoost，加入溫度、濕度、時段、月份；再組合成混合模型；以美國 EPA 的低成本感測器效能指標評估。
- **Dataset：**印度維沙卡帕特南的長期共置觀測。
- **Findings：**最好的 ML 模型 RMSE 比線性迴歸低 58%，混合模型低 63%，且在多數溫濕度與時間條件下誤差最小，符合美國 EPA 標準。
- **Limitation：**單一地點；感測器型號與氣候和台灣不同。

### S-042 統計、機器學習與深度學習校正的比較（✅）
- **作者、年份：**Gómez, Rodríguez & Ferro｜*Sensors*, 26(3), 796（2026）
- **連結：**https://doi.org/10.3390/s26030796
- **AI Method：**兩種統計方法、三種機器學習、一種深度學習；前處理用 FastDTW 對齊時間序列。
- **Dataset：**哥倫比亞波哥大，低成本感測器與 T640X 參考儀器共置，加上氣象站的溫濕度。
- **Findings：**比較多類校正方法，並把相對濕度、溫度、流量一併納入觀測。（摘要後段與量化結果未能完整讀取，**引用數字前需核對原文**）
- **Limitation：**單一地點。

### S-044 LSTM 捕捉時間依賴的校正（✅）
- **作者、年份：**Sengupta, Bush, Marner, Pérez & Le Clainche｜arXiv 2604.21527（2026）
- **連結：**https://arxiv.org/abs/2604.21527
- **AI Method：**LSTM 序列模型，加入時間延遲變數、週期編碼與交互項；對照隨機森林。
- **Dataset：**英國牛津 OxAria 網路的共置參考資料。
- **Findings：**R² 在訓練、驗證、測試集都高於 RF；PM2.5 校正後的擴展不確定度 9.1%，符合法規等效性要求。
- **Limitation：**預印本，尚未經同儕審查。

## 主題 3：資料驅動的污染來源判斷（局部 vs 區域）

### S-045 用小波分解把短期事件和區域背景分開（✅）
- **作者、年份：**Jain, Presto & Zimmerman｜*Environmental Science & Technology*（2021）
- **連結：**https://doi.org/10.1021/acs.est.1c02653
- **Problem：**低成本感測網的即時資料，能不能建立高時空解析度的污染地圖？
- **AI Method：**土地利用迴歸（LUR）vs **隨機森林版的土地利用模型（LURF）**；並用**小波分解（wavelet decomposition）**把短期局部事件從區域背景中分離出來。
- **Domain Knowledge：**污染 = 區域背景 + 局部來源；土地利用（道路、工業）決定局部差異。
- **Dataset：**美國匹茲堡 50 個低成本感測器站點，2016 年 8 月至 2017 年 12 月。
- **Findings：**LURF 比 LUR 的交叉驗證 R² 高 0.10–0.19；**分離時間尺度後，R² 再提升最多 0.14**，模型更依賴空間變數。
- **Limitation：**以日平均為主，不是即時判斷；需要土地利用資料。
- **對 AirSleuth 的意義：**「**先扣掉區域背景，剩下的才是局部**」正是 AirSleuth 判斷來源的核心概念。

### S-046 用相關網路偵測區域性污染事件（✅）
- **作者、年份：**Bashan, Li & Wang｜*npj Climate and Atmospheric Science*（2024）
- **連結：**https://doi.org/10.1038/s41612-024-00716-z
- **AI Method：**用每小時 PM2.5 的**時間延遲相關**建立動態網路。
- **Dataset：**美國本土 741 個監測站。
- **Findings：**空間相關網路能偵測 2020、2021 年野火季的顯著異常，**對區域性污染現象很敏感**；也能看出煙霧傳輸，以及污染在看不到煙之後仍持續。
- **Limitation：**使用標準測站，不是密集的低成本感測網；著重極端事件。

### S-047 扣除背景後，用高斯過程找出都市熱點（✅）
- **作者、年份：**Perry et al.｜*npj Clean Air*（2025）
- **連結：**https://doi.org/10.1038/s44407-025-00038-1
- **AI Method：**行動感測資料先**扣除背景濃度**（正規化），再以高斯過程迴歸計算具機率意義的「熱點分數」。
- **Dataset：**盧安達基加利（200 公尺解析度），並以北京的模擬資料驗證。
- **Findings：**熱點分數能捕捉真實的空間分布；方法開源、可以在各地重複使用。
- **Limitation：**行動感測、取樣不均；產出的是地圖，不是給個人的建議。

### S-014（T-18）研究級感測器找到社區熱點
- 中台灣社區 3.5 年監測，熱點靠近交通、廟宇、市場，並隨時間移動。

## 主題 4：PM2.5 短期預測

### S-048 台灣：沒有測站的地區也能預測的時空圖神經網路（✅）
- **作者、年份：**Su, Chung, Lee & Huang｜*Expert Systems with Applications*（2023）
- **連結：**https://doi.org/10.1016/j.eswa.2023.121074
- **重點（待核對）：**以測站為節點、測站距離為邊，結合 GNN 與 GRU，預測台灣未來 48 小時 PM2.5，包含沒有測站的地區。
- **Limitation：**摘要無法讀取，**引用前需核對**。

### S-049 多尺度動態圖神經網路（✅）
- **作者、年份：**Lu et al.｜*PLoS ONE*（2025）
- **連結：**https://doi.org/10.1371/journal.pone.0338392
- **AI Method：**同時建模小時、日、週三種時間尺度；用可學習的映射矩陣動態分群測站；多頭注意力 + 時空圖注意力 + Chebyshev 圖卷積。
- **Dataset：**中國長株潭地區 22 個測站。
- **Findings：**MAE 比最佳基準模型低 6.77%、RMSE 低 8.67%。
- **Limitation：**只用國家測站（22 站），沒有微型感測器；模型複雜，可解釋性低。（推論）

### S-050 多源資料的時空圖注意力網路（🟡）
- **作者、年份：**Wu, Xu, Fan, Xia & Wang｜*Air Quality, Atmosphere & Health*（2025）
- **連結：**https://doi.org/10.1007/s11869-025-01818-0
- **重點（待核對）：**結合圖卷積與多層注意力，輸入衛星與氣象資料，在京津冀測站評估。

### S-051 台灣大規模感測網的卷積遞迴網路預測（✅）
- **作者、年份：**Chen, Putra & Lin｜arXiv 2101.06213（2021）
- **連結：**https://arxiv.org/abs/2101.06213
- **AI Method：**卷積遞迴神經網路（CRNN），從大量感測節點擷取時空特徵，產生預測地圖。
- **Dataset：**台灣空品監測系統的大規模感測器資料。
- **Findings：**同時考慮空間與時間關係，能追蹤 PM2.5 的擴散。
- **Limitation：**預印本；摘要沒有提供量化指標。

---

## Article Summary Table

| Ref | Year | Problem | AI Method | Domain Knowledge | Dataset | Findings | Limitation |
|---|---|---|---|---|---|---|---|
| S-035 | 2022 | LLM 推理與行動分離 | ReAct：推理與工具呼叫交錯 | 無 | HotpotQA 等 | 減少幻覺、軌跡可解釋 | 通用工具、無領域知識 |
| S-036 | 2025 | 空品系統難懂、LLM 會幻覺 | LLM + MCP 工具呼叫 | 有限 | 即時感測器 | 專家評分正確性 4.78／5 | 不判斷來源、不處理資料品質 |
| S-037 | 2025 | 空品資料難轉成決策 | LLM 產生 Python 分析程式 | 測站、政策經費 | 印度 CPCB | 對話式分析已部署 | 對象是決策者、無微型感測器 |
| S-038 | 2026 | 室內空品監測被動 | 多 LLM 代理 + IoT + 定位 | 室內法規、健康門檻 | 室內感測器 | 依位置的個人化警示 | 只限室內 |
| S-039 | 2025 | 感測器資料問答 | 規劃 LLM + SQL 執行代理 | HVAC 知識注入 | 商用 HVAC | 專家問答集驗證 | 非空品領域 |
| S-041 | 2020 | 感測器缺乏校正 | RF、SVR、MLR | 日夜偏差型態 | 台灣 39 個感測器 | RMSE 18.4 → 5.9 | 少量、單一型號 |
| S-043 | 2026 | ML 校正的條件表現 | RF、XGBoost、混合模型 | 溫濕度、時段 | 印度長期共置 | RMSE 降 58%～63% | 單一地點 |
| S-044 | 2026 | 校正忽略時間依賴 | LSTM | 延遲的環境效應 | 英國 OxAria | R² 高於 RF；不確定度 9.1% | 預印本 |
| S-045 | 2021 | 感測網的時空地圖 | LURF + 小波分解 | 區域背景 + 局部來源 | 匹茲堡 50 站 | 分離時間尺度後 R² 最多 +0.14 | 日平均、非即時 |
| S-046 | 2024 | 偵測區域性污染事件 | 時間延遲相關網路 | 傳輸、氣象 | 美國 741 站 | 對區域事件敏感 | 標準測站、極端事件 |
| S-047 | 2025 | 都市熱點辨識 | 背景正規化 + 高斯過程 | 背景 vs 熱點 | 基加利行動感測 | 熱點分數符合真實分布 | 行動感測、非個人建議 |
| S-049 | 2025 | 多時間尺度預測 | 動態 GNN + 注意力 | 測站時空相依 | 長株潭 22 站 | MAE −6.77%、RMSE −8.67% | 只有測站、可解釋性低 |
| S-051 | 2021 | 感測網的擴散預測 | CRNN | 空間擴散 | 台灣感測網 | 產生預測地圖 | 預印本、無量化指標 |

---

## 我觀察到的 Research Gap（推論）

| # | 現有研究做到了什麼 | 還缺什麼 | AirSleuth 怎麼補 |
|---|---|---|---|
| 1 | LLM 已能透過工具呼叫查詢即時空品資料、產生分析程式（S-036、S-037），減少幻覺（S-035） | **只會「查」和「畫」，不會「判斷原因」**：沒有一個系統告訴使用者，這次升高比較像局部來源還是區域傳輸 | ⑤ Analytics Engine 加入空間型態分析：扣除區域背景後看局部超量（借鏡 S-045、S-047），並用空間一致性判斷區域事件（借鏡 S-046） |
| 2 | 校正與預測模型越來越準（S-041、S-043、S-044、S-049） | 這些都是**獨立的模型**，沒有被整合進「給個人的決策」；也很少把**資料品質與不確定性**傳達給使用者 | ④ 資料取得時先做品質檢查（T-07 已實作）；⑦ 決策時依濕度、資料完整度、感測器一致性給出**信心程度** |
| 3 | 來源判斷的方法（S-045、S-046、S-047）多為離線研究，產出的是地圖或論文結論 | **沒有即時轉成一般民眾看得懂的解釋** | ⑧ 輸出時用自然語言說明「為什麼」，並附上證據（例如「附近 85% 的感測器同時升高」） |
| 4 | LLM 代理能讀法規與文獻、依位置個人化（S-038，但只限室內） | **室外空品的個人化建議**沒有結合使用者的族群、行程與活動強度；而文獻指出只給數字時遵從率很低（S-028） | ⑥ 領域知識整合健康指引（S-029、S-032）與運動取捨（S-033）；⑦ 依使用者情境給出具體行動（改時段、改地點、降強度） |
| 5 | 台灣有約 1.1 萬個公開的微型感測器（S-001），已有校正與預測研究（S-011、S-041、S-048、S-051） | **台灣的感測網還沒有被做成 LLM Agent**，讓民眾直接用自然語言問「為什麼」與「我該怎麼做」 | AirSleuth 本身 |

**一句話總結：**現有研究分成兩群——「LLM 讓空品資料好查」與「ML 讓感測器更準、預測更準」——但**沒有人把兩者接起來，變成一個會判斷原因、知道資料可不可信、並給個人具體建議的 Agent**。這就是 AirSleuth 的定位。

---

## 來源清單（本檔新增）

| 編號 | 年份 | 作者 | 標題 | 發表處 | 連結 | 查核 |
|---|---|---|---|---|---|---|
| S-035 | 2022 | Yao et al. | ReAct: Synergizing Reasoning and Acting in Language Models | ICLR 2023 / arXiv | https://arxiv.org/abs/2210.03629 | ✅ |
| S-036 | 2025 | Pan & Nipu | LLM-enhanced Air Quality Monitoring Interface via Model Context Protocol | arXiv | https://arxiv.org/abs/2511.03706 | ✅ |
| S-037 | 2025 | Acharya et al. | VayuChat: An LLM-Powered Conversational Interface for Air Quality Data Analytics | arXiv | https://arxiv.org/abs/2511.01046 | ✅ |
| S-038 | 2026 | Vieira et al. | Large Language Model based air quality monitoring and localized alert generation | arXiv | https://arxiv.org/abs/2609.17954 | ✅ |
| S-039 | 2025 | Lee et al. | LLM-based Question-Answer Framework for Sensor-driven HVAC System Interaction | arXiv | https://arxiv.org/abs/2507.04748 | ✅ |
| S-040 | 2025 | Li et al. | Urban Computing in the Era of Large Language Models | arXiv | https://arxiv.org/abs/2504.02009 | ✅ |
| S-041 | 2020 | Wang, Lung & Liu | Application of Machine Learning for the in-Field Correction of a PM2.5 Low-Cost Sensor Network | Sensors | https://doi.org/10.3390/s20175002 | ✅ |
| S-042 | 2026 | Gómez, Rodríguez & Ferro | Calibration of Low-Cost Sensors for PM10 and PM2.5 Based on Artificial Intelligence for Smart Cities | Sensors | https://doi.org/10.3390/s26030796 | ✅ |
| S-043 | 2026 | Wathore et al. | Exploring Environmental and Temporal Performances of Machine Learning Models for Calibration of a Low-Cost PM2.5 Sensor | Aerosol and Air Quality Research | https://doi.org/10.1007/s44408-026-00094-6 | ✅ |
| S-044 | 2026 | Sengupta et al. | A temporal deep learning framework for calibration of low-cost air quality sensors | arXiv | https://arxiv.org/abs/2604.21527 | ✅ |
| S-045 | 2021 | Jain, Presto & Zimmerman | Spatial Modeling of Daily PM2.5, NO2, and CO Concentrations Measured by a Low-Cost Sensor Network | Environmental Science & Technology | https://doi.org/10.1021/acs.est.1c02653 | ✅ |
| S-046 | 2024 | Bashan, Li & Wang | Dynamics of PM2.5 and network activity during extreme pollution events | npj Climate and Atmospheric Science | https://doi.org/10.1038/s41612-024-00716-z | ✅ |
| S-047 | 2025 | Perry et al. | Detecting urban PM2.5 hotspots with mobile sensing and Gaussian process regression | npj Clean Air | https://doi.org/10.1038/s44407-025-00038-1 | ✅ |
| S-048 | 2023 | Su, Chung, Lee & Huang | Effective PM2.5 concentration forecasting based on multiple spatial–temporal GNN for areas without monitoring stations | Expert Systems with Applications | https://doi.org/10.1016/j.eswa.2023.121074 | ✅ |
| S-049 | 2025 | Lu et al. | Multi-scale dynamic graph neural network for PM2.5 concentration prediction in regional station cluster | PLoS ONE | https://doi.org/10.1371/journal.pone.0338392 | ✅ |
| S-050 | 2025 | Wu et al. | A Spatiotemporal graph attention network for PM2.5 forecasting using multi-source data | Air Quality, Atmosphere & Health | https://doi.org/10.1007/s11869-025-01818-0 | 🟡 |
| S-051 | 2021 | Chen, Putra & Lin | A Novel Prediction Approach for Exploring PM2.5 Spatiotemporal Propagation Based on Convolutional Recursive Neural Networks | arXiv | https://arxiv.org/abs/2101.06213 | ✅ |
