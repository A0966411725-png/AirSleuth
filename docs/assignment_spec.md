# 作業規範摘要：期末專題提案 Final Project Proposal

> 依據 iLearning 作業頁面整理（2026-10-19）。以原始頁面為準，這裡是方便 AI 協作者查閱的摘要。

## 繳交

- **截止：2026-11-04**，組繳交
- Proposal 佔總成績 **10%**

## 一、核心要求

**AI Agent + Domain Knowledge + Data Analytics + Real-World Application**

不能只訓練一個 AI Model 或做一個單純的 Chatbot，要設計一個 Domain AI Agent：能理解使用者需求、取得與分析資料、結合領域知識推理，最後提供有依據的結果、預測、診斷或建議。

## 二、Proposal 四部分

### 1. Abstract（A–F 六段）
- A. Attention Getter：用具體證據說明問題重要，**優先找 2025–2026** 的論文、政府或產業報告、統計、公開資料集、新聞或真實案例，不能只寫「近年 AI 快速發展」
- B. But：現有技術或研究的問題、限制與 Research Gap
- C. Cure：「為了解決上述問題，本專題提出一個新的 ______ AI Agent / System」
- D. Development：如何整合 AI、資料來源、分析方法與 Domain Knowledge
- E. Experiments：預計使用的 Dataset、Case Study、Baseline、Evaluation Metrics 或使用者測試
- F. Findings：**只能寫 Expected Findings / Expected Outcomes，不得虛構實驗結果**

### 2. Introduction（回答 Why is this project worth doing?）
A. Attention Getter、B. Background、C. Problem、D. Existing Limitations、E. Innovation、F. Contributions。重要論述都要有客觀證據與來源。

### 3. Related Work
- 約 **1/2 AI Technology + 1/2 Domain Know-how**
- 必須有 **Article Summary Table**：Ref、Year、Problem、AI Method、Domain Knowledge、Dataset、Findings、Limitation
- 最後歸納：**Existing Research → Limitations → Research Gap → Our Project**
- 可以用 AI 工具協助研究，但必須確認原始來源與內容正確

## 三、Deep Research：三大核心問題
- **Q1. 五個核心思維模式**：領域專家普遍認同的 5 個核心思維，每項說明意義、證據，以及如何影響系統設計
- **Q2. 三個最重要的專業爭論**：觀點 A ↔ 觀點 B → Evidence → Consensus → Unresolved Problems
- **Q3. 十個深度理解問題**：用來判斷一個人是真正懂這個領域還是只會死記，要涵蓋 Why、What-if、Trade-off、Failure Case、Evidence、Comparison、Design Decision、Real-world Scenario

## 四、Proposed Scheme（最重要的技術內容）
參考架構：① User/Application Scenario → ② Query/Input → ③ Planner & Reasoning Agent → ④ Data Acquisition/Retrieval → ⑤ Analytics Engine → ⑥ Domain Knowledge Integration → ⑦ Decision/Recommendation → ⑧ Output & Interaction

必須提供三種技術表示：
1. **System Architecture**：完整架構圖，模組用 ①②③ 編號並逐一說明
2. **Flowchart**：Input → Processing → AI/Analytics → Decision → Output，必要時加入 Decision、Loop、Exception、Human Interaction
3. **Pseudocode**：有行號

## 五、AI 使用規範
可以使用 AI。但 **AI 可以幫你完成工作，你必須能解釋它做了什麼、為什麼這樣設計，以及如何驗證結果**。老師可能針對 Architecture、DESIGN.md、論文、資料、程式碼與實驗結果口頭提問。

## 六、繳交內容

### Proposal 階段
1. Proposal Document：Abstract、Introduction、Related Work、Deep Research、Proposed Scheme、References
2. Proposal PPT：研究動機、文獻、Research Gap、Agent Design、Architecture、Flowchart、Pseudocode
3. GitHub Repository
4. DESIGN.md

### 期末（參考）
GitHub（完整程式碼、資料、執行與測試方式）、README.md、DESIGN.md、Final PPT **超過 20 頁**、YouTube 影片 **超過 10 分鐘**、Experiments、Conclusion

## 七、Proposal 評分

| 項目 | 比例 |
|---|---|
| Introduction：重要性、動機、Evidence、Innovation | 20% |
| Related Work：AI + Domain + Article Summary | 20% |
| Deep Research：5 Mindsets + 3 Controversies + 10 Questions | 20% |
| Proposed AI Agent + System Architecture | 20% |
| Flowchart + Pseudocode + Technical Feasibility | 15% |
| GitHub + DESIGN.md + 完整度 | 5% |
