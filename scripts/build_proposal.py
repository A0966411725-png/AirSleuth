"""把 proposal/00～05 合併成 proposal/AirSleuth_Proposal.md（繳交用的完整文件）。

用法（從專案根目錄）：python scripts/build_proposal.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = [("00_abstract.md", "摘要（Abstract）"), ("01_introduction.md", "1. 緒論（Introduction）"),
         ("02_related_work.md", "2. 相關研究（Related Work）"), ("03_deep_research.md", "3. 深度研究（Deep Research）"),
         ("04_proposed_scheme.md", "4. 系統設計（Proposed Scheme）"), ("05_references.md", "5. 參考文獻（References）")]
HEADER = [
    "# AirSleuth 空品偵探：結合 IoT 微型感測器與領域知識的空氣品質 Domain AI Agent", "",
    "**物聯網數據分析與應用｜期末專題提案（Final Project Proposal）**", "",
    "組員：陳宏郁、陳彥愷、王鼎昌、李家豐、周聖儒｜繳交日期：2026 年 11 月 4 日", "",
    "GitHub：https://github.com/A0966411725-png/AirSleuth", "",
    "> 本文件由 `proposal/00～05` 各章合併產生（`python scripts/build_proposal.py`）。文中 [S-xxx] 對應第 5 章參考文獻，"
    "所有引用都已開啟原文或摘要核對。", "",
    "## 目錄", "",
] + [f"- {title}" for _, title in PARTS] + [""]


def chapter(name: str, title: str) -> list[str]:
    lines = (ROOT / "proposal" / name).read_text(encoding="utf-8").splitlines()[1:]  # 去掉原本的 H1
    while lines and (lines[0].startswith(">") or lines[0].strip() in ("", "---")):  # 去掉開頭的說明區塊與分隔線
        lines.pop(0)
    lines = [re.sub(r"^(#{2,5}) ", lambda m: "#" + m.group(1) + " ", l) for l in lines]  # 標題降一級
    return ["---", "", f"## {title}", ""] + lines + [""]


def main() -> None:
    out = list(HEADER)
    for name, title in PARTS:
        out += chapter(name, title)
    (ROOT / "proposal" / "AirSleuth_Proposal.md").write_text("\n".join(out), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
