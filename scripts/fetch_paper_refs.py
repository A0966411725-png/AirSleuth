"""取得論文參考文獻的正式書目（Crossref／arXiv 官方 API），輸出 paper/references.json。

只收 research/sources.md 裡狀態為 verified 的來源；書目以官方 API 回傳的資料為準，網站類來源保留登記表上的標題與網址。

用法（從專案根目錄）：
    .venv\\Scripts\\python -m scripts.fetch_paper_refs
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "references.json"
# 論文引用順序（MDPI 規定依正文出現順序編號，正文用 [n] 引用）
ORDER = ["S-060", "S-020", "S-016", "S-032", "S-013", "S-012", "S-001", "S-008", "S-009", "S-010", "S-058", "S-041",
         "S-005", "S-004", "S-057", "S-047", "S-059", "S-035", "S-056", "S-055", "S-053", "S-054", "S-036", "S-037",
         "S-048", "S-061", "S-033", "S-034", "S-028"]
UA = {"User-Agent": "AirSleuth-course-project/1.0 (https://github.com/A0966411725-png/AirSleuth)"}


def registry() -> dict[str, dict]:
    rows = {}
    for line in (ROOT / "research" / "sources.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*S-\d{3}\s*\|", line):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            rows[c[0]] = {"type": c[1], "year": c[2], "author": c[3], "title": c[4], "url": c[5], "status": c[8]}
    return rows


def crossref(doi: str) -> dict:
    m = requests.get(f"https://api.crossref.org/works/{doi}", headers=UA, timeout=30).json()["message"]
    authors = [{"family": a.get("family", a.get("name", "")), "given": a.get("given", "")} for a in m.get("author", [])]
    year = (m.get("published-print") or m.get("published-online") or m.get("issued"))["date-parts"][0][0]
    return {"kind": "journal", "authors": authors, "title": m["title"][0], "journal": (m.get("container-title") or [""])[0],
            "journal_abbrev": (m.get("short-container-title") or [""])[0], "year": year, "volume": m.get("volume", ""),
            "issue": m.get("issue", ""), "pages": m.get("page", "") or m.get("article-number", ""),
            "doi": m["DOI"], "publisher": m.get("publisher", "")}


def arxiv(arxiv_id: str) -> dict:
    xml = requests.get("http://export.arxiv.org/api/query", params={"id_list": arxiv_id}, headers=UA, timeout=30).text
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    names = [a.find("a:name", ns).text for a in entry.findall("a:author", ns)]
    authors = [{"family": n.split()[-1], "given": " ".join(n.split()[:-1])} for n in names]
    return {"kind": "arxiv", "authors": authors, "title": " ".join(entry.find("a:title", ns).text.split()),
            "year": int(entry.find("a:published", ns).text[:4]), "arxiv": arxiv_id}


def main() -> None:
    reg = registry()
    out = []
    for sid in ORDER:
        s = reg[sid]
        assert s["status"] == "verified", f"{sid} 尚未查核，不能引用"
        url = s["url"]
        if "doi.org/" in url:
            meta = crossref(url.split("doi.org/")[1])
        elif "arxiv.org/abs/" in url:
            meta = arxiv(url.split("arxiv.org/abs/")[1])
            time.sleep(3)  # arXiv API 要求間隔 3 秒
        else:
            meta = {"kind": "web", "author": s["author"], "title": s["title"], "year": s["year"], "url": url}
        out.append({"sid": sid, **meta})
        print(sid, meta["kind"], meta.get("title", "")[:70])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已輸出 {OUT.relative_to(ROOT)}：{len(out)} 筆")


if __name__ == "__main__":
    main()
