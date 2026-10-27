"""由 research/sources.md 產生 proposal/05_references.md：只列出 00～04 章實際引用的來源。

用法（從專案根目錄）：python scripts/build_references.py
正文引用了沒登記、或狀態是 unverified 的來源時會報錯，避免把未查核的引用放進 Proposal。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ["00_abstract.md", "01_introduction.md", "02_related_work.md", "03_deep_research.md", "04_proposed_scheme.md"]
HEADER = """# 05 References

> 由 `research/sources.md` 自動產生（`python scripts/build_references.py`），只列出 Proposal 正文（00～04 章）實際引用的來源。
"""
NOTE = "> 標 🟡 的來源已確認文獻存在與書目正確，但未能讀取原文，引用的數字需再核對。\n"


def cited_ids() -> set[str]:
    text = "".join((ROOT / "proposal" / name).read_text(encoding="utf-8") for name in CHAPTERS)
    ids = set()
    for group in re.findall(r"S-\d{3}(?:\s*[🟡]?\s*[、,，]\s*S-\d{3})*", text):
        ids |= set(re.findall(r"S-\d{3}", group))
    return ids


def sources() -> dict[str, dict]:
    rows = {}
    for line in (ROOT / "research" / "sources.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*S-\d{3}\s*\|", line):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            rows[c[0]] = {"year": c[2], "author": c[3], "title": c[4], "url": c[5], "status": c[8]}
    return rows


def main() -> None:
    cited, table = cited_ids(), sources()
    missing = sorted(cited - table.keys())
    unverified = sorted(s for s in cited & table.keys() if table[s]["status"] not in ("verified", "metadata-verified"))
    if missing or unverified:
        sys.exit(f"引用未登記：{missing}；未查核：{unverified}")
    lines = [HEADER + (NOTE if any(table[s]["status"] == "metadata-verified" for s in cited) else "")]
    for sid in sorted(cited):
        s = table[sid]
        mark = "🟡 " if s["status"] == "metadata-verified" else ""
        lines.append(f"- **[{sid}]** {mark}{s['author']} ({s['year']}). *{s['title']}*. {s['url']}")
    lines += ["", f"共 {len(cited)} 筆。"]
    (ROOT / "proposal" / "05_references.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"已輸出 proposal/05_references.md（{len(cited)} 筆）")


if __name__ == "__main__":
    main()
