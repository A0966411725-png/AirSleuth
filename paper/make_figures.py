"""Draw the English figures for the ICEIB 2027 paper from the experiment outputs.

Run from the project root (needs data/raw for Figure 2):
    .venv\\Scripts\\python -m paper.make_figures
Outputs: paper/figures/fig1_architecture.png, fig2_cases.png, fig3_attribution.png, fig4_agent.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

from src.agent import tools  # noqa: E402
from src.knowledge import health  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
OUT = ROOT / "paper" / "figures"
NAVY, ORANGE, BLUE, GREY, GREEN = "#14213d", "#eb6834", "#2a78d6", "#9aa6bd", "#2e9c6a"
AQI_COLORS = ["#009966", "#e6c000", "#ff9933", "#cc0033", "#660099", "#7e0023"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6, "figure.facecolor": "white"})


def box(ax, x, y, w, h, title, body, fc="white", ec=NAVY, tc=NAVY):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center", fontsize=8.6, weight="bold", color=tc)
    ax.text(x + w / 2, y + h * 0.3, body, ha="center", va="center", fontsize=7, color=tc, linespacing=1.25)


def arrow(ax, a, b, color=GREY):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10, color=color, lw=1.1))


def fig1_architecture():
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    w, h = 2.15, 0.95
    box(ax, 0.1, 3.8, w, h, "(1) User scenario", "parents, asthma patients,\nrunners, commuters")
    box(ax, 2.6, 3.8, w, h, "(2) Query / input", "place, time, group,\nactivity; clarify if missing")
    box(ax, 5.1, 3.8, 4.8, h, "(3) Planner & reasoning (LLM)", "Gemini function calling (ReAct); never computes numbers;\nnumber-traceability check before answering",
        fc=NAVY, tc="white")
    box(ax, 7.6, 2.2, 2.3, h, "(4) Data acquisition", "micro sensors, stations,\nweather; quality flags")
    box(ax, 5.1, 2.2, 2.3, h, "(5) Analytics engine", "calibration, spatial\nattribution, forecast", ec=ORANGE)
    box(ax, 2.6, 2.2, 2.3, h, "(7) Decision", "personal risk level,\naction ranking, confidence")
    box(ax, 0.1, 2.2, 2.3, h, "(8) Output", "conclusion, evidence,\nactions, confidence, trace")
    box(ax, 2.6, 0.55, 4.8, 0.95, "(6) Domain knowledge", "2025 AQI bands, sensitive groups one level earlier,\nexposure = concentration x ventilation x time (cited rules)",
        fc="#fcefe8", ec=ORANGE)
    for a, b in [((2.25, 4.27), (2.6, 4.27)), ((4.75, 4.27), (5.1, 4.27)), ((8.75, 3.8), (8.75, 3.15)),
                 ((7.6, 2.67), (7.4, 2.67)), ((5.1, 2.67), (4.9, 2.67)), ((2.6, 2.67), (2.4, 2.67))]:
        arrow(ax, a, b)
    arrow(ax, (3.75, 1.5), (3.75, 2.2), ORANGE)
    arrow(ax, (6.25, 1.5), (6.25, 2.2), ORANGE)
    ax.text(9.0, 3.45, "tool calls", fontsize=7, color=GREY)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_architecture.png", dpi=300)


def fig2_cases():
    cases = [("(a) Kaohsiung, 23 Oct 11:30\nregional rise", "高雄市", 22.6276, 120.2880, "2026-10-23 11:30"),
             ("(b) Taichung coast, 19 Oct 14:40\nsubregional cluster", "臺中市", 24.2369, 120.5385, "2026-10-19 14:40"),
             ("(c) Kaohsiung Mituo, 17 Nov 12:00\nlocal source", "高雄市", 22.78265, 120.23222, "2026-11-17 12:00")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.75))
    for ax, (title, city, lat, lon, t) in zip(axes, cases):
        df = tools.get_microsensors(city, t, lat, lon, 15)["data"]
        last = df.sort_values("time").groupby("station_id").tail(1)
        last = last[last["time"] >= last["time"].max() - pd.Timedelta(minutes=10)].dropna(subset=["pm25"])
        colors = [AQI_COLORS[health.aqi_level(v)] for v in last["pm25"]]
        kx = 111.32 * np.cos(np.radians(lat))
        ax.scatter((last["lon"] - lon) * kx, (last["lat"] - lat) * 110.57, c=colors, s=5, lw=0)
        for r in (2, 8, 15):
            ax.add_patch(Circle((0, 0), r, fill=False, ec=NAVY, lw=0.6, ls="--" if r != 2 else "-"))
        ax.plot(0, 0, marker="*", color=NAVY, ms=8)
        ax.set_xlim(-16, 16)
        ax.set_ylim(-16, 16)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("km east", fontsize=7)
        ax.tick_params(labelsize=6)
    axes[0].set_ylabel("km north", fontsize=7)
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, ms=4) for c in AQI_COLORS[:4]]
    fig.legend(handles, ["Good (<=12.4)", "Moderate (<=30.4)", "Unhealthy for sensitive (<=50.4)", "Unhealthy"],
               loc="lower center", ncols=4, fontsize=6.5, frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(OUT / "fig2_cases.png", dpi=300)


def fig3_attribution():
    s = pd.read_csv(RES / "e3_summary.csv")
    names = {"AirSleuth": "AirSleuth", "消融：無 8 km 層": "Ablation: no 8 km tier",
             "基準 A：只看 AQI": "Baseline A: AQI only", "基準 B：最近感測器": "Baseline B: nearest sensor"}
    cols = ["recall_local", "recall_subregional", "recall_regional", "recall_control", "recall_fault"]
    labels = ["Local", "Subregional", "Regional", "No event", "Single faulty\nsensor"]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    width = 0.2
    for i, (key, color) in enumerate(zip(names, [ORANGE, BLUE, GREY, NAVY])):
        vals = s.set_index("method").loc[key, cols].to_numpy(dtype=float)
        ax.bar(np.arange(len(cols)) + (i - 1.5) * width, vals, width, color=color, label=names[key])
    ax.set_xticks(range(len(cols)), labels)
    ax.set_ylabel("Correct rate")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, ncols=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    fig.tight_layout()
    fig.savefig(OUT / "fig3_attribution.png", dpi=300)


def fig4_agent():
    path = RES / "e4_summary.csv"
    if not path.exists():
        return
    s = pd.read_csv(path).set_index("做法")
    names = {"只看 AQI": "AQI only", "純 LLM": "LLM only", "LLM＋原始資料工具": "LLM + raw-data tools", "AirSleuth": "AirSleuth"}
    cols = ["數字可追溯率", "建議一致率", "追問正確率", "拒答正確率"]
    labels = ["Traceable numbers", "Action agreement", "Correct clarification", "Correct refusal"]
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    width = 0.2
    for i, (key, color) in enumerate(zip(names, [GREY, NAVY, BLUE, ORANGE])):
        vals = s.loc[key, cols].to_numpy(dtype=float)
        bars = ax.bar(np.arange(len(cols)) + (i - 1.5) * width, np.nan_to_num(vals), width, color=color, label=names[key])
        ax.bar_label(bars, labels=["n/a" if np.isnan(v) else f"{v:.0%}" for v in vals], fontsize=6, padding=1)
    ax.set_xticks(range(len(cols)), labels)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Rate")
    ax.legend(frameon=False, ncols=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    fig.tight_layout()
    fig.savefig(OUT / "fig4_agent.png", dpi=300)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig1_architecture()
    fig2_cases()
    fig3_attribution()
    fig4_agent()
    print("figures written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
