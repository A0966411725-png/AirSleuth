"""把 proposal/AirSleuth_Proposal.md 轉成繳交用的 Word 檔 proposal/AirSleuth_Proposal.docx。

用法（從專案根目錄，先執行 build_proposal.py）：
    python scripts/build_proposal.py
    python scripts/export_docx.py

- 支援本專案 Markdown 用到的語法：標題、段落、粗體／斜體／行內程式碼、清單、表格、引言、程式碼區塊
- Mermaid 圖改放 `diagrams/` 的圖片：架構圖用總覽版（architecture_overview.png，即 4.1 節的 Mermaid 區塊），
  流程圖用完整版（flowchart.mmd 轉出後太長，切成 flowchart_part1/2.png）。
  圖片由 mermaid-cli 轉出：`mmdc -i diagrams/flowchart.mmd -o diagrams/flowchart.png -s 3 -b white`
- 目錄是 Word 的目錄欄位，開檔後在目錄上按右鍵「更新功能變數」即可更新頁碼
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "proposal" / "AirSleuth_Proposal.md"
OUT = ROOT / "proposal" / "AirSleuth_Proposal.docx"

LATIN, CJK, MONO = "Times New Roman", "標楷體", "Consolas"
NAVY = RGBColor(0x14, 0x21, 0x3D)
GRAY = RGBColor(0x55, 0x5D, 0x6B)
TEXT_WIDTH_CM = 16.0

# Markdown 的 Mermaid 區塊依序換成這些圖（完整版）與圖說
FIGURES = [
    [("architecture_overview.png", 13.0)],
    [("flowchart_part1.png", 15.0), ("flowchart_part2.png", 15.0)],
]
CAPTIONS = ["圖 1　System Architecture（模組 ①～⑧）",
            "圖 2　Flowchart（含判斷、迴圈、例外處理與人機互動；原始碼 diagrams/flowchart.mmd）"]

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|(?<![*\w])\*(?!\s)[^*]+?(?<!\s)\*(?![*\w]))")


def set_font(run, size=None, bold=None, italic=None, color=None, mono=False):
    run.font.name = MONO if mono else LATIN
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:eastAsia"), "微軟正黑體" if mono else CJK)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def add_inline(par, text, size=None, color=None, bold=False):
    """把行內的 **粗體**、*斜體*、`程式碼` 轉成不同格式的 run。"""
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            set_font(par.add_run(part[2:-2]), size, bold=True, color=color)
        elif part.startswith("`") and part.endswith("`"):
            set_font(par.add_run(part[1:-1]), (size or 12) - 1.5, color=color, mono=True, bold=bold)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            set_font(par.add_run(part[1:-1]), size, italic=True, color=color, bold=bold)
        else:
            set_font(par.add_run(part), size, color=color, bold=bold)


def shade(element, fill):
    pr = element.get_or_add_tcPr() if element.tag == qn("w:tc") else element.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def left_border(par, color="9AA6BD"):
    ppr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    for k, v in {"val": "single", "sz": "18", "space": "8", "color": color}.items():
        left.set(qn(f"w:{k}"), v)
    bdr.append(left)
    ppr.append(bdr)


def add_field(par, instr):
    for kind, text in (("begin", None), (None, instr), ("separate", None), ("end", None)):
        run = par.add_run()
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def setup(doc):
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(2.5)
    sec.left_margin = sec.right_margin = Cm(2.5)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = LATIN, Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)
    normal.paragraph_format.line_spacing = 1.3
    normal.paragraph_format.space_after = Pt(6)
    for level, size in ((1, 18), (2, 15), (3, 13), (4, 12)):
        st = doc.styles[f"Heading {level}"]
        st.font.name, st.font.size, st.font.bold = LATIN, Pt(size), True
        st.font.italic = False
        st.font.color.rgb = NAVY
        st.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)
        st.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.keep_with_next = True
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(footer, "PAGE")


def add_table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    header, body = cells[0], [r for r in cells[2:]]
    ncol = len(header)
    size = 9 if ncol >= 7 else 10
    table = doc.add_table(rows=1 + len(body), cols=ncol)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    # 欄寬：每欄至少放得下最長的英文單字與表頭，其餘依平均字數分配；總寬等於版心寬度
    plain = lambda t: re.sub(r"[*`]", "", t)
    col = lambda j: [plain(r[j]) for r in body if j < len(r)]
    char_cm = size * 0.0353  # 中文字寬約等於字級；英文約一半
    def need(t):  # 不能斷開的最小寬度（英文單字、數字）
        return max((len(w) for w in re.findall(r"[A-Za-z0-9.\-/_%()]+", t)), default=1) * char_cm * 0.55
    mins = [max(1.0, need(plain(header[j])), *(need(t) for t in col(j)),
                min(len(plain(header[j])), 6) * char_cm) + 0.3 for j in range(ncol)]
    avg = [max(1.0, sum(len(t) for t in col(j)) / max(len(body), 1)) for j in range(ncol)]
    extra = TEXT_WIDTH_CM - sum(mins)
    if extra > 0:
        widths = [m + extra * a / sum(avg) for m, a in zip(mins, avg)]
    else:
        widths = [m * TEXT_WIDTH_CM / sum(mins) for m in mins]
    for j, col in enumerate(table.columns):
        col.width = Cm(widths[j])
    for i, row in enumerate([header] + body):
        for j in range(ncol):
            text = row[j] if j < len(row) else ""
            cell = table.cell(i, j)
            cell.width = Cm(widths[j])
            par = cell.paragraphs[0]
            par.paragraph_format.line_spacing = 1.1
            par.paragraph_format.space_after = Pt(0)
            add_inline(par, text, size=size, bold=(i == 0))
            if i == 0:
                shade(cell._tc, "DDE3EC")
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_code(doc, lines):
    for k, line in enumerate(lines):
        par = doc.add_paragraph()
        fmt = par.paragraph_format
        fmt.line_spacing, fmt.space_after, fmt.space_before = 1.0, Pt(0), Pt(6 if k == 0 else 0)
        fmt.keep_with_next = k < len(lines) - 1  # 同一段虛擬碼不跨頁
        shade(par._p, "F2F4F7")
        set_font(par.add_run(line if line else " "), 7.5 if max(map(len, lines)) > 95 else 8.5, mono=True)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_figure(doc, n):
    for name, width in FIGURES[n]:
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(ROOT / "diagrams" / name), width=Cm(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_inline(cap, CAPTIONS[n], size=10, color=GRAY)


def add_image(doc, caption: str, path: str) -> None:
    """Markdown 圖片 ![圖說](相對路徑)：路徑相對於 proposal/。寬圖用滿版心，直式圖縮小。"""
    file = (SRC.parent / path).resolve()
    w, h = Image.open(file).size
    width = TEXT_WIDTH_CM if w / h >= 1.6 else (14.0 if w / h >= 1.0 else 11.0)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = True
    par.add_run().add_picture(str(file), width=Cm(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_inline(cap, caption, size=10, color=GRAY)


def convert(md: str, doc) -> None:
    lines = md.splitlines()
    i, figure, new_page = 0, 0, False
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            lang = s[3:].strip()
            j = i + 1
            while not lines[j].strip().startswith("```"):
                j += 1
            if lang == "mermaid":
                add_figure(doc, figure)
                figure += 1
            else:
                add_code(doc, lines[i + 1:j])
            i = j + 1
            continue
        if s.startswith("|"):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            add_table(doc, lines[i:j])
            i = j
            continue
        if s == "---":  # 各章之間換頁：設在下一個標題的「段落前分頁」，避免多出空白頁
            new_page = True
        elif s.startswith("# "):
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title.paragraph_format.space_before = Pt(120)
            title.paragraph_format.space_after = Pt(24)
            add_inline(title, s[2:], size=22, color=NAVY, bold=True)
        elif s == "## 目錄":
            # 封面與目錄分頁；目錄用 Word 欄位
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            add_inline(doc.add_paragraph(), "目錄", size=18, color=NAVY, bold=True)  # 不用標題樣式，免得列進目錄
            add_field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u')
            while i + 1 < len(lines) and (lines[i + 1].startswith("- ") or not lines[i + 1].strip()):
                i += 1
        elif m := re.match(r"^(#{2,5}) (.*)", s):
            par = doc.add_paragraph(style=f"Heading {len(m.group(1)) - 1}")
            par.paragraph_format.page_break_before, new_page = new_page, False
            add_inline(par, m.group(2))
        elif m := re.match(r"^!\[(.*)\]\((.+)\)$", s):
            add_image(doc, m.group(1), m.group(2))
        elif re.match(r"^完整版.*diagrams/flowchart", s):
            pass  # Word 版的流程圖直接放完整版，不需要這句
        elif s.startswith(">"):
            text = s.lstrip("> ").strip()
            if text.startswith("本文件由"):  # 合併腳本的說明，Word 版只保留引用說明
                text = "文中 [S-xxx] 對應第 5 章參考文獻，所有引用都已開啟原文或摘要核對。"
            if text:
                par = doc.add_paragraph()
                par.paragraph_format.left_indent = Cm(0.5)
                left_border(par)
                add_inline(par, text, size=11, color=GRAY)
        elif m := re.match(r"^(\s*)[-*] (.*)", line):
            style = "List Bullet 2" if len(m.group(1)) >= 2 else "List Bullet"
            add_inline(doc.add_paragraph(style=style), m.group(2))
        elif m := re.match(r"^(\s*)(\d+)\. (.*)", line):
            par = doc.add_paragraph()
            indent = 0.75 + (0.75 if len(m.group(1)) >= 2 else 0)
            par.paragraph_format.left_indent = Cm(indent)
            par.paragraph_format.first_line_indent = Cm(-0.75)
            add_inline(par, f"{m.group(2)}.\t{m.group(3)}")
        elif s:
            par = doc.add_paragraph()
            if i < 10:  # 封面資訊置中
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(par, s)
        i += 1


def main() -> None:
    doc = Document()
    setup(doc)
    convert(SRC.read_text(encoding="utf-8"), doc)
    doc.save(OUT)
    print(f"已輸出 {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
