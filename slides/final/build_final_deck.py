"""產生期末簡報 slides/final/AirSleuth_期末簡報.pptx（超過 20 頁，每頁附講稿）。

版面依老師課堂建議：黑底、白字、橘色標題、黃色重點。實驗數字直接讀 experiments/results/ 的輸出，
所以簡報、論文與實驗結果一致。講稿（備忘稿）同時是影片的 AI 語音旁白（slides/final/make_video.py）。

用法（從專案根目錄）：
    .venv\\Scripts\\python -m slides.final.build_final_deck
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RES = ROOT / "experiments" / "results"
OUT = HERE / "AirSleuth_期末簡報.pptx"
SHOTS = HERE / "shots"
BG, ORANGE, YELLOW, WHITE, GREY, PANEL = "0B0F19", "F28C28", "FFD23F", "F5F5F5", "9AA6BD", "161D2E"
FONT = "Microsoft JhengHei"
GITHUB = "github.com/A0966411725-png/AirSleuth"


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ---- 讀實驗結果 ----------------------------------------------------------------------------------------------
def test_count() -> int:
    """實際收集到的離線測試數（簡報上的數字跟著程式走，不寫死）。"""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout
    return int(re.search(r"(\d+) tests? collected", out).group(1))


def results() -> dict:
    r = {"tests": test_count()}
    e1 = pd.read_csv(RES / "e1_forecast.csv")
    e1 = e1[e1["scope"] == "全部"].set_index(["model", "horizon_h"])
    for m, key in (("持續性", "p"), ("MLR", "mlr"), ("梯度提升樹", "gb"), ("隨機森林", "rf")):
        for h in (1, 3, 6):
            r[f"e1_{key}{h}"] = e1.loc[(m, h), "MAE"]
            r[f"e1_{key}{h}_hit"] = e1.loc[(m, h), "AQI_hit"]
    r["e1_gb6_skill"] = e1.loc[("梯度提升樹", 6), "skill"]
    e2 = pd.read_csv(RES / "e2_calibration.csv").set_index(["city", "model"])
    for city, key in (("臺中市", "tc"), ("高雄市", "kh")):
        r[f"e2_{key}_raw"] = e2.loc[(city, "不校正"), "MAE"]
        r[f"e2_{key}_bias"] = e2.loc[(city, "不校正"), "bias"]
        best = e2.loc[city]["MAE"].idxmin()
        r[f"e2_{key}_best"], r[f"e2_{key}_gain"] = e2.loc[(city, best), "MAE"], e2.loc[(city, best), "MAE 改善"]
    e3 = pd.read_csv(RES / "e3_summary.csv").set_index("method")
    for m, key in (("AirSleuth", "as"), ("消融：無 8 km 層", "ab"), ("基準 A：只看 AQI", "aqi"), ("基準 B：最近感測器", "nn")):
        for col in ("accuracy", "macro_F1", "recall_local", "recall_subregional", "recall_regional", "false_local_under_fault"):
            r[f"e3_{key}_{col}"] = e3.loc[m, col]
    e4 = pd.read_csv(RES / "e4_summary.csv").set_index("做法")
    for m, key in (("只看 AQI", "aqi"), ("純 LLM", "llm"), ("LLM＋原始資料工具", "raw"), ("AirSleuth", "as")):
        for col, k in (("數字可追溯率", "trace"), ("含無法追溯數字的回答", "anybad"), ("建議一致率", "agree"),
                       ("區域型卻建議換地點", "spatial"), ("追問正確率", "clarify"), ("拒答正確率", "refuse"),
                       ("領域知識正確率", "know"), ("平均秒數", "sec"), ("宣稱沒有根據的即時數值", "invented")):
            r[f"e4_{key}_{k}"] = e4.loc[m, col]
    return r


def pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{x:.0%}"


# ---- 版面工具 --------------------------------------------------------------------------------------------------
def text_box(slide, x, y, w, h, text, size=20, color=WHITE, bold=False, align=PP_ALIGN.LEFT, spacing=1.15):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        rich(p, line, size, color, bold)
    return tb


def rich(p, line: str, size: float, color: str, bold: bool) -> None:
    """**文字** 顯示為黃色粗體重點。"""
    for token in re.split(r"(\*\*[^*]+\*\*)", line):
        if not token:
            continue
        run = p.add_run()
        hl = token.startswith("**")
        run.text = token[2:-2] if hl else token
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold or hl
        run.font.color.rgb = rgb(YELLOW if hl else color)


def bullets(slide, items: list[str], x=0.8, y=1.9, w=11.7, h=4.8, size=22, gap=10):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.15
        sub = item.startswith("  ")
        rich(p, ("　– " if sub else "● ") + item.strip(), size - (3 if sub else 0), GREY if sub else WHITE, False)
    return tb


def panel(slide, x, y, w, h, color=PANEL, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = 0.06
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)
    if line:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def image(slide, path: Path, x, y, w=None, h=None, frame=True):
    if frame:
        pad = 0.08
        pic = slide.shapes.add_picture(str(path), Inches(x + pad), Inches(y + pad),
                                       Inches(w - 2 * pad) if w else None, Inches(h - 2 * pad) if h else None)
        bg = panel(slide, x, y, Emu(pic.width).inches + 2 * pad, Emu(pic.height).inches + 2 * pad, "FFFFFF")
        slide.shapes._spTree.remove(bg._element)
        slide.shapes._spTree.insert(2, bg._element)
        return pic
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)


def cards(slide, items: list[tuple[str, str]], y=1.95, h=1.55, x0=0.8, w_total=11.7):
    n = len(items)
    gap = 0.25
    w = (w_total - gap * (n - 1)) / n
    for i, (big, label) in enumerate(items):
        x = x0 + i * (w + gap)
        panel(slide, x, y, w, h, line=ORANGE)
        size = 30 if len(big) <= 7 else 22 if len(big) <= 11 else 17
        text_box(slide, x + 0.1, y + 0.12, w - 0.2, 0.75, big, size, YELLOW, True, PP_ALIGN.CENTER)
        text_box(slide, x + 0.1, y + 0.86, w - 0.2, 0.6, label, 14, WHITE, False, PP_ALIGN.CENTER)


def table(slide, rows: list[list[str]], x=0.8, y=1.9, w=11.7, col_w=None, size=16, row_h=0.48):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = shape.table
    widths = col_w or [w / len(rows[0])] * len(rows[0])
    for j, cw in enumerate(widths):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb("2A3350" if i == 0 else (PANEL if i % 2 else "1C2438"))
            tf = cell.text_frame
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
            rich(tf.paragraphs[0], value, size, ORANGE if i == 0 else WHITE, i == 0)
    return tbl


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.n = 0

    def slide(self, kicker: str, title: str, notes: str):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(BG)
        self.n += 1
        if kicker:
            text_box(s, 0.8, 0.45, 11.7, 0.45, kicker, 16, GREY)
        if title:
            text_box(s, 0.8, 0.82, 11.9, 0.95, title, 34, ORANGE, True)
        text_box(s, 11.8, 6.95, 1.2, 0.4, str(self.n), 12, GREY, align=PP_ALIGN.RIGHT)
        s.notes_slide.notes_text_frame.text = notes.strip()
        return s


# ---- 內容 ------------------------------------------------------------------------------------------------------
def build(r: dict) -> Deck:
    d = Deck()

    s = d.slide("", "", f"""
大家好，我們是 Air Sleuth 團隊，今天報告的期末專題是 Air Sleuth 空品偵探。
這是一個結合物聯網微型感測器與領域知識的空氣品質 AI Agent。
它不只告訴你空氣好不好，還會判斷污染從哪裡來，並且依照你的族群和活動，給出可以照做、而且每個數字都查得到出處的建議。
接下來大約十五分鐘，我們會說明動機、系統設計、實作、實驗結果，最後展示網站。""")
    text_box(s, 0.8, 1.6, 11.7, 1.2, "AirSleuth 空品偵探", 60, ORANGE, True)
    text_box(s, 0.8, 2.85, 11.7, 1.0, "結合 IoT 微型感測器與領域知識的空氣品質 Domain AI Agent", 28, WHITE, True)
    text_box(s, 0.8, 3.75, 11.7, 0.6, "**判斷污染從哪裡來**　＋　**依你的情況給建議**　＋　**每個數字都能追溯**", 22)
    text_box(s, 0.8, 5.3, 11.7, 1.2, "物聯網數據分析與應用｜期末報告\n組員：陳宏郁、陳彥愷、王鼎昌、李家豐、周聖儒\n" + GITHUB, 18, GREY)

    s = d.slide("報告大綱", "今天要回答的四個問題", """
今天的報告分成四個部分。
第一，為什麼要做這個題目：民眾真正想知道的，不是空氣品質指標的顏色，而是原因和行動。
第二，我們怎麼設計：讓大型語言模型負責理解和表達，所有數字和判斷交給可以驗證的程式。
第三，實作了什麼：資料收集、分析工具、語言模型規劃器、規格驅動開發，還有可以實際操作的網站。
第四，效果怎麼證明：我們做了四個實驗，從預測、校正、污染來源判斷，到四十題的 Agent 比較。""")
    cards(s, [("Why", "民眾要的是原因與行動"), ("How", "LLM 規劃＋程式計算"), ("What", "資料、工具、網站、規格"),
              ("Proof", "E1～E4 四個實驗")], y=2.4, h=2.2)

    s = d.slide("動機｜Attention Getter", "空污是全球首要的環境健康風險", """
先看問題有多重要。根據二零二五年的全球空氣狀態報告，二零二三年空氣污染造成約七百九十萬人死亡，是全球首要的環境死亡風險。
世界衛生組織建議的細懸浮微粒年平均只有每立方公尺五微克。
台灣也在二零二四年加嚴標準，年平均改成十二、日平均三十，並在二零二五年啟用新版空氣品質指標。
標準越嚴，民眾越常看到黃燈和橘燈，就越需要知道：現在到底該怎麼做。""")
    cards(s, [("790 萬", "2023 年空污死亡人數（S-060）"), ("5 μg/m³", "WHO 年平均建議值（S-020）"),
              ("12／30", "台灣新標準：年／日平均（S-016）")], y=2.0)
    bullets(s, ["2025 年起台灣啟用**新版 AQI**：黃燈、橘燈的天數會變多",
                "標準越嚴，民眾越需要知道「**現在該怎麼做**」"], y=4.0, h=2.5)

    s = d.slide("問題｜But", "民眾拿到的是顏色，不是答案", f"""
但是現在的空品服務，給的主要是一個顏色，加上依族群分類的一般建議。
研究發現，空品不佳的時候，真正照著建議調整戶外活動的人，中位數只有百分之三十一，看不懂指標是主要的阻礙之一。
民眾真正想問的其實是三件事：為什麼我這裡特別高？我現在該怎麼做？這個數字可以相信嗎？
這三個問題，現有服務都沒有直接回答。""")
    bullets(s, ["空品不佳時，真正調整活動的人中位數只有 **31%**；看不懂指標是主要阻礙（S-028）",
                "民眾真正想問的三件事：",
                "  **為什麼**我這裡特別高？是附近有污染源，還是整個區域都高？",
                "  **我該怎麼做**？要不要改時間、換地點、降低強度？",
                "  **這個數字可信嗎**？微型感測器和國家測站常常不一樣"], y=1.95)

    s = d.slide("機會｜IoT", "一萬多個微型感測器：看得到空間型態", """
物聯網給了我們新的機會。環境部規劃在全國布建一萬多個空品微型感測器，資料都透過民生公共物聯網的開放介面公開。
感測器夠密，就能看出國家測站看不到的事情：這次升高是只發生在附近幾公里，還是整個區域一起升高。
這個差別直接改變建議：附近有污染源，換到幾公里外就有效；整個區域都高，換地點就沒有用，應該改時間或降低強度。""")
    image(s, ROOT / "paper" / "figures" / "fig2_cases.png", 1.37, 1.9, w=10.6)
    text_box(s, 0.8, 6.4, 11.7, 0.5, "同一個城市，三種完全不同的空間型態 → 三種不同的正確建議", 18, YELLOW, True, PP_ALIGN.CENTER)

    s = d.slide("挑戰", "要用這些資料，有三個難題", """
但要真正用好這些資料，有三個難題。
第一，微型感測器有系統性偏差，而且受濕度影響，校正公式在不同城市也不一樣。
第二，要分辨局部污染和區域背景本來就很難，研究比較過好幾種方法，沒有一種在所有情況都最好。
第三，大型語言模型雖然能用自然語言對話，但會自己編數字，在健康相關的建議上非常危險。""")
    cards(s, [("偏差＋濕度", "低成本感測器高估約 40%；校正要在地化（S-008、S-058）"),
              ("來源難分", "局部／背景分離沒有單一最佳方法（S-057）"),
              ("LLM 幻覺", "語言模型會編出看似合理的數字")], y=2.2, h=2.3)

    s = d.slide("相關研究", "既有的空品 AI Agent 做了什麼、缺了什麼", """
我們整理了二零二五到二零二六年的相關研究。
像 Neuro-Air 用多個代理人分析空品資料，在可驗證的任務上正確率達到百分之八十八點四；也有系統用在洛杉磯野火，或用 MCP 讓語言模型查詢監測資料。
但這些系統的使用者是分析人員，用的是國家測站這類參考資料。
它們都沒有處理微型感測器的資料品質，也沒有做局部和區域的空間判斷，更沒有給一般民眾個人化的行動建議。這就是我們要補的缺口。""")
    table(s, [["系統", "使用者", "資料", "感測器品質", "空間來源判斷", "個人化行動"],
              ["Neuro-Air（S-053）", "管理者", "參考測站", "—", "—", "—"],
              ["Instructor-Worker（S-054）", "決策者", "雲端資料", "—", "—", "部分"],
              ["MCP 監測介面（S-036）", "一般人", "即時感測器", "—", "—", "—"],
              ["VayuChat（S-037）", "分析者", "測站", "—", "—", "—"],
              ["**AirSleuth（本專題）**", "**民眾**", "**微型感測網**", "**✔**", "**✔**", "**✔**"]],
          col_w=[3.3, 1.5, 1.9, 1.7, 1.7, 1.6], size=15)

    s = d.slide("解法｜Cure", "LLM 負責想，程式負責算", """
我們的解法是 Air Sleuth。核心原則只有一句話：語言模型負責想，程式負責算。
語言模型只做三件事：理解問題、決定要呼叫哪些工具、把結果講成大家聽得懂的話。
所有數字和判斷，包括品質檢查、校正、來源判斷、預測、建議排序，都由確定性的程式完成，每一次呼叫都留下紀錄。
回答送出前，系統會檢查文中每個帶單位的數字，都必須能在工具結果裡找到，找不到就退回重寫。""")
    cards(s, [("理解＋規劃＋表達", "LLM（Gemini）"), ("品質、校正、來源、預測、排序", "確定性工具（可測試）"),
              ("數字可追溯檢查", "找不到出處就重寫或改用規則")], y=2.0, h=1.8)
    bullets(s, ["四項貢獻：**可驗證的 Agent 架構**、**多尺度空間來源判斷**、**真實資料的四個實驗**、**開源＋demo＋規格**"],
            y=4.3, h=1.5)

    s = d.slide("系統架構｜Proposed Scheme", "八個模組 ①～⑧", """
這是系統架構，總共八個模組。使用者提出問題後，第二個模組解析地點、時間、族群和活動，資訊不夠就追問。
第三個模組是語言模型規劃器，它透過 function calling 呼叫工具。
第四到第七個模組都是確定性程式：取得資料和品質檢查、分析引擎、領域知識、決策與建議。
最後第八個模組輸出四段式回答：結論、原因、建議、信心程度，以及完整的工具呼叫紀錄。""")
    image(s, HERE / "architecture_zh.png", 1.47, 1.8, w=10.4)

    s = d.slide("實作｜LLM 規劃器", "Gemini function calling＋三道防線", """
實作上，規劃器用的是 Gemini 三點五 Flash Lite，透過 function calling 使用三個工具：地點解析、空品分析、領域知識。
空品分析這個工具裡面，會依序跑八個資料工具，每一步都記錄。
我們設了三道防線：第一，地點不明確就追問，不支援的城市就直接說明；第二，數字可追溯檢查；第三，沒有 API key 或模型忙碌時，自動改用確定性流程，網站一樣能用。
模型忙碌或額度用完時，也會自動換到下一個模型。""")
    bullets(s, ["工具：**resolve_place**（67 個行政區）→ **analyze_air_quality**（8 個資料工具）→ **retrieve_knowledge**",
                "防線 1：地點不明確**先追問**；臺中、高雄以外**直接說明不支援**",
                "防線 2：帶單位的數字都要在工具結果中找到，否則**重寫一次**，再不行就用規則回答",
                "防線 3：沒有 key、模型 503／429／逾時 → **自動換模型或改用確定性流程**",
                "每一次工具呼叫的參數與結果都記錄，網站可以展開查看"], y=1.95)

    s = d.slide("核心演算法｜Algorithm 2", "用空間型態判斷污染從哪裡來", """
這是我們的核心演算法：空間來源判斷。
以查詢點為中心，十五公里內感測器的中位數叫做區域背景 B；兩公里內的中位數是局部濃度 L；兩者相減就是局部超量 E。
每個感測器跟自己前六小時比，升高超過百分之五十、而且至少高五微克，才算升高；升高的比例叫做空間一致性 C。
我們另外看八公里內和八到十五公里外環的升高比例，所以能分出局部型、次區域型、區域型，還有疑似單一感測器異常。
因為用的是中位數，單一壞掉的感測器沒辦法影響判斷。""")
    table(s, [["型態", "判斷條件", "建議方向"],
              ["區域型", "C ≥ 0.6 且 E 小", "**換地點沒用** → 改時段、降低強度、室內"],
              ["次區域型", "8 km 內升高 ≥ 30%、外環 < 30%", "**換到 8 km 外**"],
              ["局部型", "E 大、C 低、附近 ≥ 2 個感測器一起高", "**換個地方**就能避開"],
              ["疑似感測器異常", "E 大但鄰近都沒有升高", "不採信，降低信心"]],
          col_w=[2.2, 5.0, 4.5], size=16, y=2.0)
    text_box(s, 0.8, 5.0, 11.7, 1.2, "B：15 km 中位數｜L：2 km 中位數（不足 5 個就擴大到 4、8 km）｜E = L − B｜"
             "升高：比自己前 6 小時高 **50% 且 ≥ 5 μg/m³**", 16, GREY)

    s = d.slide("分析與決策", "校正、預測、個人化建議", """
分析引擎還有兩個部分。第一是在地校正：臺中和高雄各有一組公式，用最近氣象站的濕度修正。
第二是短期預測：用國家測站過去的資料訓練多元線性迴歸，只用查詢時間以前的資料，避免偷看未來。
決策模組依照新版空氣品質指標，對孩童、長者、氣喘和心血管疾病患者提前一級提醒，再用活動效益減去暴露風險，排序每一個行動。
換地點只在局部或次區域事件時才會出現，而且至少要改善五微克才會建議。""")
    bullets(s, ["**在地校正**：臺中、高雄各一組 ref = a + b·sensor + c·RH（濕度用最近氣象站）",
                "**短期預測**：只用查詢時間之前的資料訓練 MLR（1／3／6 小時）；測站短暫尖峰時不套用",
                "**個人化**：敏感族群提前一級（S-032）；分數 = 活動效益 − λ(等級) × 暴露（濃度 × 換氣量 × 時間）",
                "**空間邏輯**：換地點只在局部／次區域型；改時段、換地點至少要改善 **5 μg/m³**",
                "**信心程度**：感測器少、濕度 ≥ 85%、來源不確定、資料超過 30 分鐘 → 逐級降低"], y=1.95)

    s = d.slide("規格驅動開發｜OpenSpec", "研究主張 → 需求 → 程式 → 驗證", f"""
依照老師課堂示範的規格驅動開發，我們用 OpenSpec 把系統寫成可以驗證的規格。
目前有七項已實作能力的規格，以及期末三項變更：語言模型規劃器、demo 網站、評估實驗。每一項需求都有具體的情境，例如沒有說地點時必須追問。
我們還做了追溯矩陣，把三個研究問題對應到需求、程式和測試或實驗。
目前共有 {r['tests']} 個離線測試全部通過，而且測試不會呼叫真實的 API。""")
    cards(s, [("7＋3", "已實作規格＋期末變更"), ("10/10", "openspec validate --strict 通過"),
              (str(r["tests"]), "離線測試全部通過"), ("RQ1～3", "追溯到需求、程式、實驗")], y=2.0)
    text_box(s, 0.8, 4.0, 11.7, 2.4, "Requirement：Natural-language understanding with clarification\n"
             "  WHEN 使用者問「現在適合出去跑步嗎？」沒有說地點\n  THEN 規劃器先問使用者在哪裡\n  AND 在知道地點之前不呼叫任何資料工具",
             17, GREY)

    s = d.slide("資料｜IoT 資料管線", "每小時收集三種資料，共 1,550 萬筆", """
資料方面，我們從十月十九日開始，每小時自動收集三種資料：微型感測器、國家測站、氣象站。
實驗使用十月十九日到十一月十八日，臺中和高雄共兩千五百六十個感測器、一千五百五十萬筆五分鐘資料。
我們也誠實記錄資料的問題：十一月初有八天連不上，二十一日之後民生公共物聯網的憑證過期。
我們堅持不關閉憑證驗證，所以 demo 網站改用已收集的真實事件重播。""")
    table(s, [["資料", "期間（2026）", "規模"],
              ["微型感測器（民生公共物聯網）", "10/19～11/18，528 小時", "2,560 個感測器、1,550 萬筆"],
              ["國家測站（環境部）", "8/20～11/24", "18 站，小時值"],
              ["氣象站（中央氣象署）", "10/19～11/24", "124 站"]], col_w=[4.6, 3.8, 3.3], size=16)
    bullets(s, ["收集中斷也照實記錄：11/1～11/9 API 連不上；**11/21 官方憑證過期**",
                "堅持**不關閉憑證驗證** → demo 改用已收集的真實事件重播"], y=4.3, h=2)

    demo_slides(d, r)

    s = d.slide("實驗 E1｜預測", "樹模型最準，但我們選擇可解釋的 MLR", f"""
第一個實驗比較預測模型。用十八個國家測站，八月到十月中訓練、十月底到十一月測試。
六小時後的預測誤差，持續性預測是 {r['e1_p6']:.2f}，多元線性迴歸是 {r['e1_mlr6']:.2f}，用 Optuna 調參的梯度提升樹最好，是 {r['e1_gb6']:.2f}，比持續性預測改善 {r['e1_gb6_skill']:.0%}。
樹模型只比線性迴歸好約零點二微克，但線性迴歸的每個係數都能解釋，所以 Agent 裡我們選擇可解釋的線性迴歸。這是準確度和可解釋性之間的取捨。""")
    image(s, RES / "e1_forecast_mae.png", 0.8, 1.9, w=7.4)
    table(s, [["MAE（μg/m³）", "1 h", "3 h", "6 h"],
              ["持續性", f"{r['e1_p1']:.2f}", f"{r['e1_p3']:.2f}", f"{r['e1_p6']:.2f}"],
              ["MLR", f"{r['e1_mlr1']:.2f}", f"{r['e1_mlr3']:.2f}", f"{r['e1_mlr6']:.2f}"],
              ["梯度提升樹", f"**{r['e1_gb1']:.2f}**", f"**{r['e1_gb3']:.2f}**", f"**{r['e1_gb6']:.2f}**"]],
          x=8.5, y=2.1, w=4.4, col_w=[1.7, 0.9, 0.9, 0.9], size=14)

    s = d.slide("實驗 E2｜校正", "在地校正：臺中改善 20%、高雄改善 14%", f"""
第二個實驗是微型感測器的校正，資料量是期中時的六倍，用留一站交叉驗證。
臺中的感測器平均高估 {r['e2_tc_bias']:.1f} 微克，校正後誤差從 {r['e2_tc_raw']:.2f} 降到 {r['e2_tc_best']:.2f}，改善 {r['e2_tc_gain']:.0%}；
高雄剛好相反，平均低估 {abs(r['e2_kh_bias']):.1f}，校正後改善 {r['e2_kh_gain']:.0%}。
兩個城市偏差方向相反，證明校正一定要在地化。臺中在濕度百分之九十以上時，感測器讀數是測站的兩倍，和文獻的吸濕高估一致。""")
    image(s, RES / "e2_calibration_scatter.png", 0.8, 1.9, w=7.6)
    cards(s, [(f"−{r['e2_tc_gain']:.0%}", f"臺中 MAE {r['e2_tc_raw']:.2f}→{r['e2_tc_best']:.2f}"),
              (f"−{r['e2_kh_gain']:.0%}", f"高雄 MAE {r['e2_kh_raw']:.2f}→{r['e2_kh_best']:.2f}")],
          y=2.1, h=1.55, x0=8.7, w_total=4.0)
    text_box(s, 8.7, 4.0, 4.0, 2.2, "臺中原始讀數**偏高**、高雄**偏低**\n→ 校正必須**在地化**\n濕度 ≥ 90%：臺中感測器約為測站 **2 倍**", 16)

    s = d.slide("實驗 E3｜來源判斷", "半合成注入：已知答案的 880 個案例", f"""
第三個實驗是最核心的來源判斷。真實資料沒有標準答案，所以我們在真實的乾淨背景上，人工加入已知型態的升高，答案就是我們加入的型態。
臺中和高雄各四十個真實背景，乘上十一種情境，總共八百八十個案例。
Air Sleuth 的正確率是 {r['e3_as_accuracy']:.0%}，只看空品指標的做法只有 {r['e3_aqi_accuracy']:.0%}，只看最近感測器的做法是 {r['e3_nn_accuracy']:.0%}。
最重要的是，碰到單一感測器故障時，只看最近感測器的方法百分之百誤判成局部污染，而 Air Sleuth 只有 {r['e3_as_false_local_under_fault']:.0%}。
拿掉八公里這一層之後，次區域型完全辨識不出來，證明這一層是必要的。""")
    image(s, RES / "e3_attribution.png", 0.8, 1.9, w=7.6)
    table(s, [["方法", "正確率", "macro-F1", "故障誤判"],
              ["**AirSleuth**", f"**{pct(r['e3_as_accuracy'])}**", f"**{r['e3_as_macro_F1']:.2f}**", f"**{pct(r['e3_as_false_local_under_fault'])}**"],
              ["無 8 km 層", pct(r["e3_ab_accuracy"]), f"{r['e3_ab_macro_F1']:.2f}", pct(r["e3_ab_false_local_under_fault"])],
              ["只看 AQI", pct(r["e3_aqi_accuracy"]), f"{r['e3_aqi_macro_F1']:.2f}", pct(r["e3_aqi_false_local_under_fault"])],
              ["最近感測器", pct(r["e3_nn_accuracy"]), f"{r['e3_nn_macro_F1']:.2f}", pct(r["e3_nn_false_local_under_fault"])]],
          x=8.6, y=2.1, w=4.3, col_w=[1.5, 0.9, 1.0, 0.9], size=13)

    s = d.slide("實驗 E3｜真實事件", "四個真實事件，AirSleuth 全部判對", """
除了半合成案例，我們也檢查真實事件。
十月二十三日的高雄，十五公里內百分之九十的感測器一起升高，是區域型，所以建議孩童降低強度，而不是換地點。
十月十九日的臺中沿海，升高集中在八公里內，外環只有百分之四，換到八公里外濃度會從三十七降到二十三左右。
十一月十七日的高雄彌陀，九個感測器比背景高十四微克，區域內其他地方沒有升高，是典型的局部污染。
只看空品指標的方法，四個事件只判對一個。""")
    table(s, [["真實事件", "AirSleuth 判斷", "關鍵指標", "第一順位建議"],
              ["高雄 10/23 11:30", "**區域型**", "C = 0.90、E = 3.7", "降低強度（不換地點）"],
              ["臺中沿海 10/19 14:40", "**次區域型**", "8 km 內 38%、外環 4%", "換到 8 km 外（37→23）"],
              ["高雄彌陀 11/17 12:00", "**局部型**", "E = 14.3、C = 0", "換到 8 km 外"],
              ["臺中 10/21 10:00", "**沒有事件**", "C = 0", "照常活動"]],
          col_w=[3.1, 2.2, 3.2, 3.2], size=16)
    text_box(s, 0.8, 4.8, 11.7, 1.0, "高雄 10/23：國家測站最新小時值仍是 **5**，微型感測器已看到約 **21 μg/m³** → 微型感測網提早看見區域升高", 18)

    s = d.slide("實驗 E4｜Agent 比較", "40 題：四種做法同場比較", f"""
第四個實驗比較四種做法回答同樣的四十題問題：只看空品指標的規則、沒有工具的純語言模型、有原始資料工具但沒有領域知識的語言模型，以及完整的 Air Sleuth。三種語言模型做法都用同一個 Gemini 模型。
純語言模型沒有任何資料，卻有 {pct(r['e4_llm_invented'])} 的回答直接說出了即時數值，例如 AQI 大約八十到一百二十，這些都是編的。
有原始資料工具的版本，數字大多查得到，但建議只有 {pct(r['e4_raw_agree'])} 符合官方指引；例如高雄區域升高時，它只相信測站的五，就告訴家長可以帶小孩去跑步。
Air Sleuth 的數字全部可以追溯，建議有 {pct(r['e4_as_agree'])} 符合指引，追問、拒答和觀念題也全部答對。""")
    image(s, RES / "e4_agent.png", 0.8, 1.9, w=7.6)
    table(s, [["做法", "編造即時數值", "建議一致", "追問"],
              ["只看 AQI", pct(r["e4_aqi_invented"]), pct(r["e4_aqi_agree"]), "—"],
              ["純 LLM", f"**{pct(r['e4_llm_invented'])}**", pct(r["e4_llm_agree"]), pct(r["e4_llm_clarify"])],
              ["LLM＋原始工具", pct(r["e4_raw_invented"]), pct(r["e4_raw_agree"]), pct(r["e4_raw_clarify"])],
              ["**AirSleuth**", f"**{pct(r['e4_as_invented'])}**", f"**{pct(r['e4_as_agree'])}**", f"**{pct(r['e4_as_clarify'])}**"]],
          x=8.6, y=2.1, w=4.3, col_w=[1.5, 1.1, 0.9, 0.8], size=13)
    text_box(s, 8.6, 4.9, 4.3, 1.6, f"AirSleuth：數字 **{pct(r['e4_as_trace'])}** 可追溯；拒答 **{pct(r['e4_as_refuse'])}**、觀念題 **{pct(r['e4_as_know'])}**", 15)

    s = d.slide("用真實資料與評估找到的問題", "四個在合成測試裡看不到的錯誤", """
用真實資料重播和四十題評估時，我們找到四個合成測試抓不到的問題，都修好並加上測試。
第一，十月二十九日大里測站出現七十四的短暫尖峰，附近二十三個感測器只有十四左右，原本系統會把測站的預測直接套用，算出一小時後降到零，現在會偵測尖峰而不套用。
第二，空氣已經良好時，系統曾經為了一點點改善建議延後六小時，現在至少要改善五微克才會建議。
第三，一般民眾在普通等級運動，曾被建議改到室內，和環境部指引不一致，現在只對風險已達敏感等級的人打折扣。
第四，第一版遇到觀念題沒有查領域知識，還答出舊版的空品指標範圍，現在觀念題一定先查知識工具，而且所有回答都要通過數字檢查。""")
    table(s, [["問題", "原因", "修正"],
              ["大里測站尖峰 74、附近只有 14\n→ 預測「降到 0」", "把測站尖峰回落的預測套到附近", "偵測尖峰就不套用；變化量設上下限"],
              ["空氣良好（11.5）卻建議延後 6 小時", "延後沒有成本", "至少改善 5 μg/m³；延後、換地點有成本"],
              ["一般民眾在「普通」被建議進室內", "高濃度效益折扣對所有人套用", "只對已達敏感等級的人套用（符合 S-032）"],
              ["觀念題答出舊版 AQI 範圍（E4）", "沒查知識工具；只有分析才做數字檢查", "觀念題先查知識；所有回答都做數字檢查"]],
          col_w=[4.3, 3.6, 3.8], size=14, row_h=0.72)

    s = d.slide("討論｜Trade-offs", "三個取捨與限制", """
我們也要誠實說明取捨和限制。
第一，準確度和可解釋性：樹模型比較準，但線性迴歸可以解釋，我們選擇後者。
第二，靈敏度和誤報：升高門檻設得保守，在乾淨空氣裡不會誤報，但很弱的升高可能漏判。
第三，個人化和安全：建議的權重來自官方指引和文獻，但部分是假設，還需要使用者研究驗證。
另外，半合成實驗驗證的是演算法的邏輯，還不是化學成分分析的實際來源；資料也只有兩個城市、一個秋季。""")
    table(s, [["取捨", "我們的選擇", "代價"],
              ["準確度 vs 可解釋性", "Agent 用 MLR", "6 小時預測多 0.2 μg/m³ 誤差"],
              ["靈敏度 vs 誤報", "升高要 50% 且 ≥ 5", "+8～10 的弱事件會漏判"],
              ["個人化 vs 安全", "依官方指引排序", "部分權重是假設，待使用者研究"]],
          col_w=[3.4, 4.0, 4.3], size=16)
    bullets(s, ["限制：半合成標籤 ≠ 化學源解析；只有臺中、高雄一個秋季；**標準答案是依官方指引寫成的規則**"], y=4.4, h=1.5, size=18)

    s = d.slide("結論", "把一萬多個感測器，變成一句可以照做的建議", """
總結一下。Air Sleuth 證明了，用工具約束的語言模型 Agent，可以把有雜訊的公開物聯網資料，變成可以解釋、可以照做的個人化建議。
語言模型負責語言和規劃，品質檢查、校正、空間判斷、預測和決策規則負責數字。
在臺中和高雄的真實資料上，我們的來源判斷遠勝只看指標或只看最近感測器的方法，而且回答的數字都能追溯。
未來我們會加入冬季資料和更多城市，用化學成分分析做實地驗證，並進行使用者研究。""")
    cards(s, [(pct(r["e3_as_accuracy"]), "來源判斷正確率（只看 AQI 19%）"), (pct(r["e4_as_agree"]), "建議符合官方指引（純 LLM 25%）"),
              (pct(r["e4_as_trace"]), "回答數字可追溯"), (str(r["tests"]), "測試全部通過")], y=2.0)
    bullets(s, ["未來：**冬季與更多城市**、化學源解析實地驗證、**使用者研究**、LINE Bot 介面"], y=4.0, h=1.5)

    s = d.slide("", "", """
以上就是我們的期末報告。程式碼、規格、實驗和 demo 網站都公開在 GitHub。
論文初稿依照 ICEIB 2027 研討會的格式撰寫。謝謝大家，歡迎提問。""")
    text_box(s, 0.8, 1.8, 11.7, 1.2, "謝謝聆聽　Q & A", 54, ORANGE, True, PP_ALIGN.CENTER)
    text_box(s, 0.8, 3.4, 11.7, 1.8, f"GitHub：{GITHUB}\nDemo：Streamlit 網站（見 README）\n論文初稿：ICEIB 2027（Engineering Proceedings 格式）",
             22, WHITE, False, PP_ALIGN.CENTER)
    return d


def cropped(path: Path) -> Path:
    """裁掉 Streamlit 側欄與頁首空白，只留主畫面，放進投影片時字比較大。"""
    from PIL import Image
    out = SHOTS / "cropped" / path.name
    out.parent.mkdir(exist_ok=True)
    im = Image.open(path)
    w, h = im.size
    im.crop((int(w * 0.235), int(h * 0.06), w, h)).save(out)
    return out


def demo_slides(d: Deck, r: dict) -> None:
    shots = [
        ("01_chat_kaohsiung.png", "Demo｜問 AirSleuth", "用一句中文提問，AirSleuth 自己決定查什麼",
         ["Gemini 依序呼叫：**地點解析 → 空品分析 → 領域知識**", "四段式回答：結論、原因、建議、信心",
          "高雄 10/23 區域型 → 孩童**降低強度**，不建議換地點"], """
接下來是網站展示。在問 Air Sleuth 頁面，我們輸入：我在高雄前金區，現在可以帶小孩去公園跑步嗎？
Gemini 自己決定先解析地點，再做空品分析，最後取得領域知識。
回答分成結論、原因、建議和信心四段。這是十月二十三日的區域型事件，所以建議孩童降低強度，而不是換地點。"""),
        ("02_chat_trace.png", "Demo｜工具呼叫紀錄", "每個數字都查得到出處",
         ["展開就能看到每一步的**工具、參數、回傳值**", "回答中帶單位的數字都要**在這裡找得到**",
          "找不到就重寫；再不行就改用確定性流程"], """
展開工具呼叫紀錄，可以看到每一步呼叫的工具、帶入的參數和回傳的結果。
回答裡的每個濃度、比例、距離，都能在這裡找到，這就是我們說的數字可追溯。"""),
        ("03_chat_clarify.png", "Demo｜追問", "資訊不夠，先問清楚再回答",
         ["沒說地點 → **先問在哪一區**，不猜", "臺中、高雄以外 → **直接說明不支援**", "觀念題 → 查領域知識再回答"], """
如果使用者只問：現在適合出去跑步嗎？沒有說在哪裡，Air Sleuth 不會亂猜，而是先問使用者在哪一區。
問台北的話，它也會直接說明目前只支援臺中和高雄，不會編造資料。"""),
        ("04_replay_kaohsiung.png", "Demo｜真實事件重播", "高雄 10/23：整個區域一起升高",
         ["15 km 內幾乎都是黃色，**C = 0.90**", "**區域型** → 換地點沒用", "一般民眾照常；孩童、長者、患者**降低強度**"], """
在真實事件重播頁面，可以看到查詢點周圍兩公里、八公里、十五公里內每個感測器的濃度。
高雄十月二十三日，幾乎整個區域都是黃色，空間一致性零點九，是典型的區域型事件。
右邊的表格比較不同族群拿到的建議：一般民眾照常運動，孩童、長者和患者則降低強度。"""),
        ("05_replay_taichung.png", "Demo｜真實事件重播", "臺中沿海 10/19：升高集中在 8 km 內",
         ["橘色集中在查詢點附近，外環只有 **4%** 升高", "**次區域型** → 換到 8 km 外", "濃度約 **37 → 23** μg/m³"], """
換成臺中沿海十月十九日，可以看到橘色的感測器集中在查詢點附近，外圍大多沒有升高。
這是次區域型事件，所以第一順位建議變成換到八公里以外，那裡的區域背景大約只有二十三微克。
同一套規則，空間型態不同，建議就不同，這就是 Air Sleuth 和只看指標的工具最大的差別。"""),
        ("07_replay_local.png", "Demo｜真實事件重播", "高雄彌陀 11/17：附近有污染源",
         ["2 km 內 9 個感測器比背景高 **14 μg/m³**", "區域內其他地方**沒有升高**（C = 0）", "**局部型** → 換個地方就能避開"], """
最後是十一月十七日中午的高雄彌陀。查詢點附近九個感測器比十五公里的背景高了十四微克，但區域內其他地方都沒有升高。
這是局部型事件，代表附近有污染源，所以建議換到八公里以外，區域背景大約二十微克。
四種型態，四種不同的建議，都來自同一套規則。"""),
    ]
    for name, kicker, title, points, notes in shots:
        s = d.slide(kicker, title, notes)
        path = SHOTS / name
        if path.exists():
            image(s, cropped(path), 0.6, 1.8, h=5.2)
            bullets(s, points, x=8.55, y=2.0, w=4.4, h=4.8, size=17)
        else:
            text_box(s, 0.8, 3.0, 11.7, 1, f"（截圖 {name} 尚未產生：python -m slides.final.capture_demo）", 18, GREY)


def main() -> None:
    d = build(results())
    d.prs.save(OUT)
    print(f"已輸出 {OUT.relative_to(ROOT)}：{d.n} 張")


if __name__ == "__main__":
    main()
