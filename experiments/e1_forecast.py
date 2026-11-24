"""E1 預測實驗：持續性、多元線性迴歸（MLR）與兩種樹模型（Optuna 調參），預測國家測站 1／3／6 小時後的 PM2.5。

設計（openspec/changes/add-evaluation-suite）：
- 資料：臺中 6 站＋高雄 12 站，2026-08-20 ～ 11-24 的小時值，所有測站合併訓練（特徵與測站無關）。
- 依時間切分，不能隨機切：訓練 8/20～10/13、驗證 10/14～10/26（只用來調參）、測試 10/27～11/24。
- 樹模型用 Optuna（TPE，固定種子）在驗證期調參；選定參數後用「訓練＋驗證」重新訓練，測試期只評估一次。
- 指標：MAE、RMSE、新版 AQI 等級命中率；skill = 1 − MAE / 持續性 MAE。

用法（從專案根目錄）：
    .venv\\Scripts\\python -m experiments.e1_forecast            # 完整（每個模型 30 次試驗）
    .venv\\Scripts\\python -m experiments.e1_forecast --trials 5  # 快速檢查
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

from experiments.common import (BLUE, CITIES, GREEN, GREY, ORANGE, RESULTS, SEED, STATION_END, STATION_START, TZ,
                                plt, read_source, save_table)
from src.analytics import forecast as fc

HORIZONS = (1, 3, 6)
TRAIN_END = pd.Timestamp("2026-10-14 00:00", tz=TZ)
VAL_END = pd.Timestamp("2026-10-27 00:00", tz=TZ)


def load_stations() -> pd.DataFrame:
    parts = []
    for city in CITIES:
        df = read_source("moenv", city, STATION_START, STATION_END, "siteid")
        parts.append(df.assign(city=city))
    return pd.concat(parts, ignore_index=True)


def tune(make_model, space, train: pd.DataFrame, val: pd.DataFrame, trials: int) -> dict:
    X, y, Xv, yv = train[fc.FEATURES], train["target"], val[fc.FEATURES], val["target"]

    def objective(trial):
        model = make_model(space(trial)).fit(X, y)
        return float(np.mean(np.abs(np.clip(model.predict(Xv), 0, None) - yv)))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=trials, show_progress_bar=False)
    return study.best_params


def rf(params):
    return RandomForestRegressor(random_state=SEED, n_jobs=-1, **params)


def rf_space(t):
    return {"n_estimators": t.suggest_int("n_estimators", 100, 400, step=50),
            "max_depth": t.suggest_int("max_depth", 4, 20),
            "min_samples_leaf": t.suggest_int("min_samples_leaf", 1, 30),
            "max_features": t.suggest_float("max_features", 0.3, 1.0)}


def hgb(params):
    return HistGradientBoostingRegressor(random_state=SEED, **params)


def hgb_space(t):
    return {"learning_rate": t.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "max_iter": t.suggest_int("max_iter", 100, 600, step=50),
            "max_leaf_nodes": t.suggest_int("max_leaf_nodes", 8, 64),
            "min_samples_leaf": t.suggest_int("min_samples_leaf", 10, 80),
            "l2_regularization": t.suggest_float("l2_regularization", 1e-4, 1.0, log=True)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=30)
    args = parser.parse_args()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    stations = load_stations()
    city_of = stations.drop_duplicates("siteid").set_index("siteid")["city"]
    rows, best = [], {}
    for h in HORIZONS:
        feats = fc.build_features(stations, h).dropna(subset=fc.FEATURES + ["target"])
        feats["city"] = feats["siteid"].map(city_of)
        train = feats[feats["time"] < TRAIN_END]
        val = feats[(feats["time"] >= TRAIN_END) & (feats["time"] < VAL_END)]
        test = feats[feats["time"] >= VAL_END]
        fit_set = pd.concat([train, val])
        preds = {"持續性": test["pm25"].to_numpy(),
                 "MLR": fc.MLR().fit(fit_set, fit_set["target"]).predict(test)}
        for name, make, space in (("隨機森林", rf, rf_space), ("梯度提升樹", hgb, hgb_space)):
            params = tune(make, space, train, val, args.trials)
            best[f"{name}_{h}h"] = params
            model = make(params).fit(fit_set[fc.FEATURES], fit_set["target"])
            preds[name] = np.clip(model.predict(test[fc.FEATURES]), 0, None)
        for name, p in preds.items():
            for scope, mask in [("全部", np.ones(len(test), bool))] + [(c, (test["city"] == c).to_numpy()) for c in CITIES]:
                rows.append({"horizon_h": h, "model": name, "scope": scope, **fc.metrics(test["target"][mask], p[mask])})
        print(f"{h} 小時：訓練 {len(train)}、驗證 {len(val)}、測試 {len(test)} 筆", flush=True)
    res = pd.DataFrame(rows)
    base = res[res["model"] == "持續性"].set_index(["horizon_h", "scope"])["MAE"]
    res["skill"] = 1 - res["MAE"] / res.set_index(["horizon_h", "scope"]).index.map(base).to_numpy()
    save_table(res.round(4), "e1_forecast.csv")
    (RESULTS / "e1_best_params.json").write_text(json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8")
    print(res[res["scope"] == "全部"].pivot_table(index="model", columns="horizon_h", values=["MAE", "AQI_hit", "skill"]).round(3).to_string())
    plot(res)


def plot(res: pd.DataFrame) -> None:
    allres = res[res["scope"] == "全部"]
    models = ["持續性", "MLR", "隨機森林", "梯度提升樹"]
    colors = [GREY, BLUE, GREEN, ORANGE]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    width = 0.2
    for i, (m, c) in enumerate(zip(models, colors)):
        vals = [allres[(allres["model"] == m) & (allres["horizon_h"] == h)]["MAE"].iloc[0] for h in HORIZONS]
        bars = ax.bar(np.arange(len(HORIZONS)) + (i - 1.5) * width, vals, width, label=m, color=c)
        ax.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
    ax.set_xticks(range(len(HORIZONS)), [f"{h} 小時後" for h in HORIZONS])
    ax.set_ylabel("測試期 MAE（μg/m³）")
    ax.set_title("E1：國家測站 PM2.5 預測誤差（10/27～11/24，18 站）", loc="left", fontsize=12)
    ax.legend(frameon=False, ncols=4, loc="upper left", fontsize=9)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    fig.tight_layout()
    fig.savefig(RESULTS / "e1_forecast_mae.png", dpi=180)


if __name__ == "__main__":
    main()
