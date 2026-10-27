"""領域知識：新版 AQI、敏感族群、活動與建議規則（架構模組 ⑥ Domain Knowledge Integration）。

每條規則都附上依據（`research/sources.md` 的 S 編號或本專題的任務回報），讓 Agent 的建議可以追溯。
標「假設值」的參數沒有直接的文獻數字，是為了讓 Algorithm 3 能運作的初始值，期末依文獻與使用者測試校準。

輸入：PM2.5 濃度（μg/m³）、族群、活動。
輸出：AQI 等級、等級名稱、建議文字、規則依據。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 2025 年起新版 AQI 的 PM2.5（24 小時平均）分段上限（S-029）
AQI_PM25_BOUNDS = [12.4, 30.4, 50.4, 125.4, 225.4]
AQI_NAMES = ["良好", "普通", "對敏感族群不健康", "對所有族群不健康", "非常不健康", "危害"]

# 敏感族群（S-032）：心臟、呼吸道及心血管疾病患者、孩童、老年人、氣喘患者
SENSITIVE_GROUPS = {"child", "elderly", "asthma", "heart"}
GROUP_NAMES = {"general": "一般民眾", "child": "孩童", "elderly": "長者", "asthma": "氣喘患者", "heart": "心血管疾病患者"}

ACTIVITY_NAMES = {"rest": "靜態活動", "walk": "散步或通勤", "exercise": "跑步等運動"}
# 相對換氣量（靜態 = 1）：假設值，期末依文獻的換氣量資料校準
BREATHING_RATE = {"rest": 1.0, "walk": 2.0, "exercise": 4.0}
# 活動的健康效益（相對值）：運動效益通常大於一般濃度下的空污風險（S-033）
ACTIVITY_BENEFIT = {"rest": 0.0, "walk": 0.6, "exercise": 1.0}
# PM2.5 ≥ 25 時運動的保護效果由約 30% 降為 12%～15%（S-061）→ 效益乘上約 0.45
HIGH_PM_BENEFIT_FACTOR = 0.45
HIGH_PM_THRESHOLD = 25.0
# 室內／室外濃度比：假設值（門窗關閉時通常低於室外），期末依文獻校準
INDOOR_RATIO = 0.6
# 改到室內時保留的活動效益比例：假設值（室內通常活動量較小）
INDOOR_BENEFIT = 0.5
# 各 AQI 等級的風險權重 λ（Algorithm 3 第 8 行）：假設值，調整成與環境部的活動建議一致（S-032）：
# 「普通」時一般人照常活動；到了「對敏感族群不健康」，敏感族群改成減少體力消耗
RISK_WEIGHT = [0.02, 0.05, 0.12, 0.3, 0.8, 2.0]


def aqi_level(pm25: float) -> int:
    """PM2.5 濃度 → 新版 AQI 等級（0 良好、1 普通、2 對敏感族群不健康…）。"""
    return int(np.searchsorted(AQI_PM25_BOUNDS, float(pm25), side="left"))


def personal_level(pm25: float, group: str) -> int:
    """敏感族群提前一級警示（DESIGN.md 第 7 節；S-024、S-031）。"""
    level = aqi_level(pm25)
    return min(level + 1, len(AQI_NAMES) - 1) if group in SENSITIVE_GROUPS else level


@dataclass
class Action:
    key: str
    text: str
    concentration: float     # 這個行動下預期接觸的濃度
    rate: float              # 相對換氣量
    benefit: float           # 活動效益
    note: str = ""


def candidate_actions(c_now: float, c_best: float, best_hour: int, src_type: str, c_away: float | None,
                      activity: str) -> list[Action]:
    """Algorithm 3 第 4～7 行：列出候選行動與各自的濃度、換氣量、效益。

    c_best／best_hour：未來 6 小時預測中最低的濃度與時距；c_away：8 km 外（區域背景）的濃度。
    「換地點」只有在局部型或次區域型事件時才會降低濃度（Algorithm 3 第 6 行）。
    """
    rate, benefit = BREATHING_RATE[activity], ACTIVITY_BENEFIT[activity]
    act = ACTIVITY_NAMES[activity]
    actions = [Action("as_planned", f"照原計畫進行{act}", c_now, rate, benefit)]
    if best_hour > 0 and c_best < c_now:
        actions.append(Action("shift_time", f"延後約 {best_hour} 小時再出門（預估降到 {c_best:.0f} μg/m³）",
                              c_best, rate, benefit))
    if c_away is not None and src_type in ("local", "subregional") and c_away < c_now:
        actions.append(Action("shift_place", f"換到 8 km 以外的地點（區域背景約 {c_away:.0f} μg/m³）",
                              c_away, rate, benefit, note="只有局部或次區域事件時有效"))
    if activity != "rest":
        actions.append(Action("lower_intensity", f"降低強度，改成散步或伸展", c_now,
                              BREATHING_RATE["walk"] if activity == "exercise" else BREATHING_RATE["rest"],
                              ACTIVITY_BENEFIT["walk"] if activity == "exercise" else 0.2))
    actions.append(Action("move_indoor", "改到室內並關閉門窗（可開空氣清淨機）", c_now * INDOOR_RATIO,
                          rate, benefit * INDOOR_BENEFIT))
    return actions


def score(a: Action, level: int, hours: float = 1.0) -> float:
    """Algorithm 3 第 8 行：效益 − λ(等級) × 暴露。暴露 = 濃度 × 換氣量 × 時間（S-034：濃度不等於暴露量）。"""
    benefit = a.benefit * (HIGH_PM_BENEFIT_FACTOR if a.concentration >= HIGH_PM_THRESHOLD else 1.0)
    exposure = a.concentration * a.rate * hours / 10.0
    return benefit - RISK_WEIGHT[level] * exposure


def rank_actions(actions: list[Action], level: int, hours: float = 1.0, top: int = 3) -> list[Action]:
    return sorted(actions, key=lambda a: score(a, level, hours), reverse=True)[:top]


RULES = {
    "aqi_2025": "新版 AQI：良好 0–12.4、普通 12.5–30.4、對敏感族群不健康 30.5–50.4 μg/m³（S-029）",
    "sensitive": "孩童、長者、氣喘與心血管疾病患者為敏感族群，提前一級提醒（S-032、S-024、S-031）",
    "no_threshold": "PM2.5 沒有安全閾值，綠燈時仍提醒心肺疾病患者（S-020、S-021）",
    "exercise": "一般濃度下運動效益大於空污風險；PM2.5 ≥ 25 時效益打折但仍存在（S-033、S-061）",
    "exposure": "暴露量取決於濃度 × 換氣量 × 停留時間（S-034）",
    "shift_place": "局部或次區域事件才建議換地點；區域事件時改時段或改到室內（Algorithm 3 第 6 行）",
}
