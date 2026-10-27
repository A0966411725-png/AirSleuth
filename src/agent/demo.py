"""用真實收集的資料重跑 AirSleuth 的完整流程，輸出四段式回答與工具呼叫紀錄。

用法（從專案根目錄）：
    python -m src.agent.demo --case kaohsiung        # 高雄 10/23 區域型事件
    python -m src.agent.demo --case taichung         # 臺中 10/19 沿海事件
    python -m src.agent.demo --city 高雄市 --lat 22.6276 --lon 120.2880 --time "2026-10-23 11:30" --group child
    加上 --save 會把結果寫到 docs/agent_demo/<case>.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.agent.pipeline import Query, run

ROOT = Path(__file__).resolve().parents[2]

CASES = {
    "kaohsiung": Query("高雄市", 22.6276, 120.2880, "2026-10-23 11:30", group="child", activity="exercise",
                       hours=1.0, place="高雄市前金區（前金測站附近）"),
    "taichung": Query("臺中市", 24.2369, 120.5385, "2026-10-19 14:40", group="general", activity="exercise",
                      hours=1.0, place="臺中市西側沿海（T-20 事件中心）"),
    "taichung_clear": Query("臺中市", 24.1438, 120.6844, "2026-10-21 10:00", group="asthma", activity="walk",
                            hours=1.0, place="臺中市西屯區"),
}


def render(name: str, q: Query, answer) -> str:
    lines = [f"# AirSleuth 原型輸出：{name}", "",
             f"> 由 `python -m src.agent.demo --case {name}` 以本地收集的真實資料產生。數字全部來自工具計算。", "",
             "## 使用者情境", "",
             f"- 地點：{q.place}（{q.lat}, {q.lon}）", f"- 時間：{q.time}",
             f"- 族群：{q.group}；活動：{q.activity}；預計 {q.hours:g} 小時", "",
             "## 回答", "", answer.to_text(), "", "## 工具呼叫紀錄（可追溯性）", "",
             "| 步驟 | 工具 | 主要結果 |", "|---|---|---|"]
    for t in answer.trace:
        brief = {k: (f"{len(v)} 條規則" if k == "rules" else v) for k, v in t["result"].items()}
        lines.append(f"| {t['step']} | `{t['tool']}` | {json.dumps(brief, ensure_ascii=False, default=str)[:220]} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", choices=sorted(CASES))
    ap.add_argument("--city"), ap.add_argument("--lat", type=float), ap.add_argument("--lon", type=float)
    ap.add_argument("--time"), ap.add_argument("--group", default="general"), ap.add_argument("--activity", default="exercise")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args(argv)
    if a.case:
        name, q = a.case, CASES[a.case]
    else:
        name, q = "custom", Query(a.city, a.lat, a.lon, a.time, a.group, a.activity)
    answer = run(q)
    text = render(name, q, answer)
    print(text)
    if a.save:
        out = ROOT / "docs" / "agent_demo" / f"{name}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"已存到 {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
