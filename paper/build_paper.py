"""Build the ICEIB 2027 conference draft (Engineering Proceedings template) from paper/airsleuth_iceib2027.md.

The Markdown source keeps the content; this script maps it onto the official MDPI styles of
paper/template/Engineering_proceedings_Template.docx. Citations are written as [S-xxx] (IDs of research/sources.md)
and renumbered [1], [2], ... in order of first appearance; the reference list comes from paper/references.json,
which only contains verified sources (scripts/fetch_paper_refs.py).

Run from the project root:
    .venv\\Scripts\\python -m paper.build_paper
Output: paper/AirSleuth_ICEIB2027_draft.docx
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper" / "airsleuth_iceib2027.md"
TEMPLATE = ROOT / "paper" / "template" / "Engineering_proceedings_Template.docx"
OUT = ROOT / "paper" / "AirSleuth_ICEIB2027_draft.docx"
REFS = json.loads((ROOT / "paper" / "references.json").read_text(encoding="utf-8"))
CITE = re.compile(r"\[(S-\d{3}(?:\s*,\s*S-\d{3})*)\]")
# Web sources: English author and title (Chinese originals are marked "in Chinese"); URLs come from research/sources.md
WEB_EN = {
    "S-060": ("Health Effects Institute", "State of Global Air 2025"),
    "S-020": ("World Health Organization", "WHO Global Air Quality Guidelines: Particulate Matter (PM2.5 and PM10), Ozone, "
              "Nitrogen Dioxide, Sulfur Dioxide and Carbon Monoxide; World Health Organization: Geneva, Switzerland, 2021"),
    "S-016": ("Ministry of Environment, Taiwan", "Revised Ambient Air Quality Standards and Air Quality Index "
              "(Press Release, 30 September 2024; in Chinese)"),
    "S-032": ("Ministry of Environment, Taiwan", "Air Quality Index and Activity Guidance (in Chinese)"),
    "S-001": ("Civil IoT Taiwan", "SensorThings API for the Smart-City Air Quality Micro Sensors"),
}


# ---- front matter and citations --------------------------------------------------------------------------------
def parse(md: str) -> tuple[dict, list[str]]:
    _, front, body = md.split("---\n", 2)
    meta, key = {}, None
    for line in front.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif line.startswith("  - ") and key:
            meta[key] = (meta[key] if isinstance(meta[key], list) else []) + [line[4:].strip()]
    return meta, body.splitlines()


def citation_order(text: str) -> list[str]:
    order = []
    for group in CITE.findall(text):
        for sid in re.findall(r"S-\d{3}", group):
            if sid not in order:
                order.append(sid)
    return order


def renumber(text: str, number: dict[str, int]) -> str:
    def repl(m):
        nums = sorted({number[s] for s in re.findall(r"S-\d{3}", m.group(1))})
        parts, start = [], nums[0]
        for a, b in zip(nums, nums[1:] + [None]):
            if b != a + 1:
                parts.append(f"{start}" if start == a else (f"{start},{a}" if a == start + 1 else f"{start}–{a}"))
                start = b
        return "[" + ",".join(parts) + "]"
    return CITE.sub(repl, text)


# ---- references (MDPI style) -----------------------------------------------------------------------------------
def initials(given: str) -> str:
    parts = re.split(r"[\s]+", given.strip())
    out = []
    for p in parts:
        if not p:
            continue
        out.append("-".join(q[0].upper() + "." for q in p.split("-") if q))
    return "".join(out)


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def format_ref(r: dict) -> str:
    if r["kind"] == "web":
        author, title = WEB_EN[r["sid"]]
        return f"{author}. {title}. Available online: {r['url']} (accessed on 24 November 2026)."
    def family(name: str) -> str:  # Crossref 有時回傳全大寫的姓
        return name.title() if name.isupper() else name
    names = [f"{family(a['family'])}, {initials(a['given'])}" if a.get("given") else family(a["family"]) for a in r["authors"]]
    if len(names) > 10:
        names = names[:10] + ["et al."]
    authors = "; ".join(names[:-1]) + (" " if names[-1] == "et al." else "; ") + names[-1] if len(names) > 1 else names[0]
    authors = authors.replace("; et al.", " et al.") if names[-1] == "et al." else authors
    title = clean(r["title"])
    if r["kind"] == "arxiv":
        return f"{authors} {title}. arXiv {r['year']}, arXiv:{r['arxiv']}."
    journal = clean(r.get("journal_abbrev") or r.get("journal") or "")
    vol = f", {r['volume']}" if r.get("volume") else ""
    pages = f", {r['pages']}" if r.get("pages") else ""
    return f"{authors} {title}. {journal} {r['year']}{vol}{pages}. https://doi.org/{r['doi']}."


# ---- docx helpers ----------------------------------------------------------------------------------------------
def add_runs(par, text: str, size: float | None = None) -> None:
    """**bold**, *italic*, ^superscript^ and _{subscript}."""
    for token in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|\^[^^]+\^|_\{[^}]+\})", text):
        if not token:
            continue
        if token.startswith("**"):
            run = par.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("*"):
            run = par.add_run(token[1:-1])
            run.italic = True
        elif token.startswith("^"):
            run = par.add_run(token[1:-1])
            run.font.superscript = True
        elif token.startswith("_{"):
            run = par.add_run(token[2:-1])
            run.font.subscript = True
        else:
            run = par.add_run(token)
        if size:
            run.font.size = Pt(size)


def set_text(par, text: str) -> None:
    for r in list(par.runs):
        r._element.getparent().remove(r._element)
    add_runs(par, text)


def border(cell, side: str, size: int) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), "auto")
    borders.append(el)


def add_table(doc, rows: list[list[str]], widths: list[float] | None = None):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    tblPr = table._tbl.tblPr
    for tag, attrs in (("w:tblW", {"w:w": "7857", "w:type": "dxa"}), ("w:tblInd", {"w:w": "2608", "w:type": "dxa"})):
        el = tblPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            tblPr.append(el)
        for k, v in attrs.items():
            el.set(qn(k), v)
    total = sum(widths) if widths else len(rows[0])
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.width = Cm(13.86 * (widths[j] if widths else 1) / total)
            par = cell.paragraphs[0]
            par.style = doc.styles["MDPI_4.2_table_body"]
            par.paragraph_format.keep_with_next = i < len(rows) - 1   # 表格不要被拆到兩頁
            add_runs(par, value, size=9)
            if i == 0:
                for r in par.runs:
                    r.bold = True
                border(cell, "top", 8)
                border(cell, "bottom", 4)
            if i == len(rows) - 1:
                border(cell, "bottom", 8)
    return table


def caption(doc, style: str, label: str, text: str) -> None:
    par = doc.add_paragraph(style=style)
    if style.startswith("MDPI_4.1"):   # 表格標題要和表格在同一頁
        par.paragraph_format.keep_with_next = True
    run = par.add_run(label + " ")
    run.bold = True
    add_runs(par, text)


# ---- main ------------------------------------------------------------------------------------------------------
def main() -> None:
    meta, lines = parse(SRC.read_text(encoding="utf-8"))
    body_text = "\n".join(lines)
    order = citation_order(meta["abstract"] + "\n" + body_text)
    known = {r["sid"]: r for r in REFS}
    missing = [s for s in order if s not in known]
    if missing:
        raise SystemExit(f"cited but not in paper/references.json (verified sources only): {missing}")
    number = {sid: i + 1 for i, sid in enumerate(order)}

    doc = Document(str(TEMPLATE))
    p = doc.paragraphs
    set_text(p[0], meta["article_type"])
    set_text(p[1], meta["title"] + " ^†^")
    set_text(p[2], meta["authors"])
    affs = meta["affiliations"]
    set_text(p[3], affs[0])
    set_text(p[4], affs[1] if len(affs) > 1 else "")
    set_text(p[5], "*\tCorrespondence: " + meta["correspondence"])
    set_text(p[6], "†\t" + meta["presented"])
    set_text(p[8], renumber(meta["abstract"], number))
    set_text(p[9], "**Keywords:** " + meta["keywords"])
    if len(affs) < 2:
        p[4]._element.getparent().remove(p[4]._element)

    # drop the template body from "0. How to Use This Template" to the end (keep the section properties)
    body = doc.element.body
    start = next(par._element for par in doc.paragraphs if par.text.strip().startswith("0. How to Use This Template"))
    notes = next(par for par in doc.paragraphs if par.text.startswith("Disclaimer/Publisher"))
    notes_el = copy.deepcopy(notes._element)
    remove, found = [], False
    for el in list(body):
        if el is start:
            found = True
        if found and el.tag != qn("w:sectPr"):
            remove.append(el)
    for el in remove:
        body.remove(el)

    sectPr = body.find(qn("w:sectPr"))
    fig_no = 0
    back = False
    i = 0
    while i < len(lines):
        line = renumber(lines[i].rstrip(), number)
        if not line.strip():
            i += 1
            continue
        if line.startswith("## Back Matter"):
            back = True
        elif line.startswith("## "):
            doc.add_paragraph(line[3:], style="MDPI_2.1_heading1").paragraph_format.keep_with_next = True
        elif line.startswith("### "):
            doc.add_paragraph(line[4:], style="MDPI_2.2_heading2").paragraph_format.keep_with_next = True
        elif line.startswith("!["):
            m = re.match(r"!\[(Figure \d+\.)\s*(.*)\]\((.+?)\)(?:\{width=([\d.]+)\})?", line)
            par = doc.add_paragraph(style="MDPI_5.2_figure")
            par.add_run().add_picture(str(ROOT / "paper" / m.group(3)), width=Cm(float(m.group(4) or 13.5)))
            caption(doc, "MDPI_5.1_figure_caption", m.group(1), m.group(2))
            fig_no += 1
        elif re.match(r"^Table \d+\.", line):
            label, text = line.split(" ", 2)[0] + " " + line.split(" ", 2)[1], line.split(" ", 2)[2]
            caption(doc, "MDPI_4.1_table_caption", label, text)
            rows, widths = [], None
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                cells = [renumber(c.strip(), number) for c in lines[i].strip().strip("|").split("|")]
                if all(re.match(r"^:?-{3,}:?$", c) for c in cells):
                    widths = [float(c.count("-")) for c in cells]
                else:
                    rows.append(cells)
                i += 1
            add_table(doc, rows, widths)
            if i < len(lines) and lines[i].startswith("> "):
                doc.add_paragraph(renumber(lines[i][2:], number), style="MDPI_4.3_table_footer")
                i += 1
            continue
        elif line.startswith("- "):
            add_runs(doc.add_paragraph(style="MDPI_3.8_bullet"), line[2:])
        elif re.match(r"^\d+\. ", line):
            add_runs(doc.add_paragraph(style="MDPI_3.7_itemize"), re.sub(r"^\d+\. ", "", line))
        elif line.startswith("    "):   # algorithm / pseudocode line
            par = doc.add_paragraph(style="MDPI_3.2_text_no_indent")
            par.paragraph_format.left_indent = Cm(4.6)
            run = par.add_run(line.strip())
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
        else:
            add_runs(doc.add_paragraph(style="MDPI_6.2_back_matter" if back else "MDPI_3.1_text"), line)
        i += 1

    doc.add_paragraph("References", style="MDPI_2.1_heading1")
    for sid in order:
        doc.add_paragraph(format_ref(known[sid]), style="MDPI_8.1_references")
    body.append(notes_el)
    body.remove(sectPr)
    body.append(sectPr)
    doc.save(OUT)
    print(f"written {OUT.relative_to(ROOT)}: {len(order)} references, {fig_no} figures")


if __name__ == "__main__":
    main()
