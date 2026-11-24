"""在終端機直接問 AirSleuth（LLM 規劃版；沒有 GEMINI_API_KEY 時自動改用確定性流程）。

用法（從專案根目錄）：
    python -m src.agent.ask "我在高雄前金區，現在可以帶小孩去公園跑步嗎？" --time "2026-10-23 11:30"
    python -m src.agent.ask "台中西屯適合散步嗎" --time "2026-10-19 14:40" --trace
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from src.agent.planner import Planner


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="問 AirSleuth 空品偵探")
    parser.add_argument("question")
    parser.add_argument("--time", default=None, help="查詢時間（台灣時間），預設為現在；重播事件時請指定")
    parser.add_argument("--trace", action="store_true", help="一併印出工具呼叫紀錄")
    args = parser.parse_args(argv)
    time = args.time or f"{pd.Timestamp.now(tz='Asia/Taipei'):%Y-%m-%d %H:%M}"
    result = Planner().ask(args.question, time=time)
    print(result.text)
    print(f"\n[{result.kind}｜模型：{result.model or '未使用'}｜查詢時間：{time}]")
    for note in result.notes:
        print(f"[註] {note}")
    if args.trace:
        for step in result.trace:
            print(json.dumps({k: step[k] for k in ("tool", "args") if k in step}, ensure_ascii=False))


if __name__ == "__main__":
    main()
