#!/usr/bin/env python3
"""Tune the main Big West impact model with resumable Optuna CV search."""

from __future__ import annotations

import argparse
import json
import os
import pickle
import time
from collections import Counter
from pathlib import Path

import lightgbm as lgb
os.environ["MPLCONFIGDIR"] = str(Path("data/cache/matplotlib").resolve())
os.environ.setdefault("XDG_CACHE_HOME", str(Path("data/cache").resolve()))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from optuna.importance import get_param_importances
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from build_big_west_first_model import (
    CATEGORICAL_FEATURES,
    MODELING_PATH,
    PER40_CORE_NUMERIC_FEATURES,
    RANDOM_STATE,
    clipped,
    include_row,
    load_massey_power,
    make_preprocessor,
    mean_baseline_cv_predictions,
    metrics,
)


TARGET_COLUMN = "impact_score"
FEATURE_SET = "per40_core"
VALIDATION = "season_holdout"
STUDY_NAME = "big_west_impact_per40_season_holdout"
STORAGE_PATH = Path("data/optuna_big_west_impact_per40.sqlite3")
OUTPUT_DIR = Path("reports/optuna_big_west_impact_per40")
TRIALS_PATH = OUTPUT_DIR / "trials.csv"
TOP20_PATH = OUTPUT_DIR / "top20_trials.csv"
IMPORTANCE_PATH = OUTPUT_DIR / "param_importance.csv"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"
REPORT_PATH = OUTPUT_DIR / "tuning_report.md"
MODEL_PATH = OUTPUT_DIR / "best_model.pkl"
PREDICTIONS_PATH = OUTPUT_DIR / "cv_predictions.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-trials", type=int, default=1000, help="Additional Optuna trials to run.")
    parser.add_argument("--timeout", type=int, default=None, help="Optional timeout in seconds.")
    parser.add_argument(
        "--study-name",
        default=STUDY_NAME,
        help="Optuna study name. Same name/storage resumes an existing study.",
    )
    parser.add_argument(
        "--storage",
        default=str(STORAGE_PATH),
        help="SQLite storage path for the resumable study.",
    )
    return parser.parse_args()


def prepare_training_data() -> tuple[pd.DataFrame, pd.Series, pd.Series, list[str], list[str], dict[str, object]]:
    raw = pd.read_csv(MODELING_PATH)
    massey_power, massey_source = load_massey_power()

    include_flags = []
    reasons = []
    conf_powers = []
    for _index, row in raw.iterrows():
        include, reason, conf_power = include_row(row, massey_power)
        include_flags.append(include)
        reasons.append(reason)
        conf_powers.append(conf_power)
    raw["model_include"] = include_flags
    raw["model_include_reason"] = reasons
    raw["source_conf_power"] = conf_powers

    included = raw[raw["model_include"]].copy()
    included[TARGET_COLUMN] = pd.to_numeric(included[TARGET_COLUMN], errors="coerce")
    included = included[included[TARGET_COLUMN].notna()].copy()

    numeric_features = PER40_CORE_NUMERIC_FEATURES[:]
    for optional_feature in ["source_conf_power", "destination_conf_power", "conf_power_delta"]:
        if optional_feature in included.columns and pd.to_numeric(included[optional_feature], errors="coerce").notna().any():
            numeric_features.append(optional_feature)
    numeric_features = [feature for feature in numeric_features if feature in included.columns]
    categorical_features = [feature for feature in CATEGORICAL_FEATURES if feature in included.columns]

    for column in numeric_features:
        included[column] = pd.to_numeric(included[column], errors="coerce").fillna(0.0)
    for column in categorical_features:
        included[column] = included[column].fillna("").astype(str)

    X = included[numeric_features + categorical_features]
    y = included[TARGET_COLUMN]
    groups = included["first_big_west_season"].astype(str)
    meta = {
        "rows_available": int(len(raw)),
        "rows_used": int(len(included)),
        "source_level_counts": dict(Counter(included["source_level"])),
        "season_counts": dict(Counter(groups)),
        "massey_power_source": massey_source,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
    }
    return X, y, groups, numeric_features, categorical_features, meta


def suggest_model(trial: optuna.Trial):
    family = trial.suggest_categorical(
        "family",
        [
            "ridge",
            "elastic_net",
            "random_forest",
            "extra_trees",
            "gradient_boosting",
            "hist_gradient_boosting",
            "lightgbm",
            "xgboost",
        ],
    )

    if family == "ridge":
        return Ridge(alpha=trial.suggest_float("ridge_alpha", 0.01, 300.0, log=True), random_state=RANDOM_STATE)

    if family == "elastic_net":
        return ElasticNet(
            alpha=trial.suggest_float("elastic_alpha", 0.005, 3.0, log=True),
            l1_ratio=trial.suggest_float("elastic_l1_ratio", 0.0, 0.9),
            max_iter=50000,
            random_state=RANDOM_STATE,
        )

    if family == "random_forest":
        max_depth_choice = trial.suggest_categorical("rf_max_depth", [2, 3, 4, 5, 6, 8, None])
        return RandomForestRegressor(
            n_estimators=trial.suggest_int("rf_n_estimators", 200, 1000, step=100),
            max_depth=max_depth_choice,
            min_samples_leaf=trial.suggest_int("rf_min_samples_leaf", 2, 12),
            min_samples_split=trial.suggest_int("rf_min_samples_split", 2, 20),
            max_features=trial.suggest_float("rf_max_features", 0.35, 1.0),
            bootstrap=trial.suggest_categorical("rf_bootstrap", [True, False]),
            random_state=RANDOM_STATE,
            n_jobs=1,
        )

    if family == "extra_trees":
        max_depth_choice = trial.suggest_categorical("et_max_depth", [2, 3, 4, 5, 6, 8, None])
        return ExtraTreesRegressor(
            n_estimators=trial.suggest_int("et_n_estimators", 200, 1000, step=100),
            max_depth=max_depth_choice,
            min_samples_leaf=trial.suggest_int("et_min_samples_leaf", 2, 12),
            min_samples_split=trial.suggest_int("et_min_samples_split", 2, 20),
            max_features=trial.suggest_float("et_max_features", 0.35, 1.0),
            bootstrap=trial.suggest_categorical("et_bootstrap", [True, False]),
            random_state=RANDOM_STATE,
            n_jobs=1,
        )

    if family == "gradient_boosting":
        return GradientBoostingRegressor(
            n_estimators=trial.suggest_int("gb_n_estimators", 80, 700, step=20),
            learning_rate=trial.suggest_float("gb_learning_rate", 0.005, 0.08, log=True),
            max_depth=trial.suggest_int("gb_max_depth", 1, 4),
            min_samples_leaf=trial.suggest_int("gb_min_samples_leaf", 2, 20),
            min_samples_split=trial.suggest_int("gb_min_samples_split", 2, 30),
            subsample=trial.suggest_float("gb_subsample", 0.55, 1.0),
            max_features=trial.suggest_float("gb_max_features", 0.45, 1.0),
            random_state=RANDOM_STATE,
        )

    if family == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            max_iter=trial.suggest_int("hgb_max_iter", 80, 600, step=20),
            learning_rate=trial.suggest_float("hgb_learning_rate", 0.005, 0.08, log=True),
            max_leaf_nodes=trial.suggest_int("hgb_max_leaf_nodes", 3, 24),
            min_samples_leaf=trial.suggest_int("hgb_min_samples_leaf", 5, 30),
            l2_regularization=trial.suggest_float("hgb_l2_regularization", 0.01, 30.0, log=True),
            random_state=RANDOM_STATE,
        )

    if family == "lightgbm":
        return lgb.LGBMRegressor(
            objective="regression",
            n_estimators=trial.suggest_int("lgb_n_estimators", 80, 700, step=20),
            learning_rate=trial.suggest_float("lgb_learning_rate", 0.005, 0.08, log=True),
            num_leaves=trial.suggest_int("lgb_num_leaves", 3, 31),
            max_depth=trial.suggest_categorical("lgb_max_depth", [2, 3, 4, 5, 6, -1]),
            min_child_samples=trial.suggest_int("lgb_min_child_samples", 5, 35),
            subsample=trial.suggest_float("lgb_subsample", 0.55, 1.0),
            colsample_bytree=trial.suggest_float("lgb_colsample_bytree", 0.45, 1.0),
            reg_alpha=trial.suggest_float("lgb_reg_alpha", 0.001, 10.0, log=True),
            reg_lambda=trial.suggest_float("lgb_reg_lambda", 0.01, 30.0, log=True),
            random_state=RANDOM_STATE,
            n_jobs=1,
            verbose=-1,
        )

    return xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=trial.suggest_int("xgb_n_estimators", 80, 700, step=20),
        learning_rate=trial.suggest_float("xgb_learning_rate", 0.005, 0.08, log=True),
        max_depth=trial.suggest_int("xgb_max_depth", 1, 5),
        min_child_weight=trial.suggest_float("xgb_min_child_weight", 1.0, 12.0),
        subsample=trial.suggest_float("xgb_subsample", 0.55, 1.0),
        colsample_bytree=trial.suggest_float("xgb_colsample_bytree", 0.45, 1.0),
        reg_alpha=trial.suggest_float("xgb_reg_alpha", 0.001, 10.0, log=True),
        reg_lambda=trial.suggest_float("xgb_reg_lambda", 0.01, 30.0, log=True),
        random_state=RANDOM_STATE,
        n_jobs=1,
    )


def cross_val_predictions(
    model,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
) -> tuple[np.ndarray, list[float]]:
    cv = GroupKFold(n_splits=min(5, groups.nunique()))
    predictions = np.zeros(len(y), dtype=float)
    fold_maes = []
    for train_idx, test_idx in cv.split(X, y, groups):
        pipeline = Pipeline(
            steps=[
                ("preprocess", make_preprocessor(numeric_features, categorical_features)),
                ("model", clone(model)),
            ]
        )
        pipeline.fit(X.iloc[train_idx], y.iloc[train_idx])
        fold_pred = clipped(pipeline.predict(X.iloc[test_idx]))
        predictions[test_idx] = fold_pred
        fold_maes.append(float(mean_absolute_error(y.iloc[test_idx], fold_pred)))
    return predictions, fold_maes


def make_objective(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
):
    def objective(trial: optuna.Trial) -> float:
        model = suggest_model(trial)
        preds, fold_maes = cross_val_predictions(model, X, y, groups, numeric_features, categorical_features)
        score = float(mean_absolute_error(y, preds))
        trial.set_user_attr("fold_maes", fold_maes)
        trial.set_user_attr("cv_rmse", metrics(y.to_numpy(), preds)["rmse"])
        trial.set_user_attr("cv_r2", metrics(y.to_numpy(), preds)["r2"])
        trial.set_user_attr("cv_corr", metrics(y.to_numpy(), preds)["corr"])
        return score

    return objective


def trials_dataframe(study: optuna.Study) -> pd.DataFrame:
    frame = study.trials_dataframe(attrs=("number", "value", "state", "params", "user_attrs", "datetime_start", "datetime_complete"))
    if "value" in frame:
        frame = frame.sort_values("value", ascending=True)
    return frame


def save_plots(study: optuna.Study, trials: pd.DataFrame, importances: dict[str, float]) -> None:
    complete = trials[trials["state"] == "COMPLETE"].sort_values("number")
    if not complete.empty:
        running_best = complete["value"].cummin()
        plt.figure(figsize=(10, 5))
        plt.scatter(complete["number"], complete["value"], s=12, alpha=0.35, label="Trial CV MAE")
        plt.plot(complete["number"], running_best, color="#c0392b", linewidth=2, label="Best so far")
        plt.xlabel("Trial")
        plt.ylabel("Season-holdout CV MAE")
        plt.title("Optuna Optimization History")
        plt.legend()
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "optimization_history.png", dpi=180)
        plt.close()

    if importances:
        names = list(importances)[:20]
        values = [importances[name] for name in names]
        plt.figure(figsize=(10, max(4, len(names) * 0.32)))
        plt.barh(names[::-1], values[::-1], color="#2c7fb8")
        plt.xlabel("Optuna parameter importance")
        plt.title("Parameter Importance")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "parameter_importance.png", dpi=180)
        plt.close()


def convergence_summary(complete_values: list[float]) -> dict[str, object]:
    if not complete_values:
        return {"status": "no_complete_trials"}
    best = min(complete_values)
    recent_windows = {}
    for window in [50, 100, 250]:
        if len(complete_values) > window:
            before = min(complete_values[:-window])
            after = min(complete_values[-window:])
            recent_windows[f"best_before_last_{window}"] = before
            recent_windows[f"best_in_last_{window}"] = after
            recent_windows[f"improvement_last_{window}"] = max(0.0, before - min(before, after))
    plateau = False
    if "improvement_last_100" in recent_windows:
        plateau = recent_windows["improvement_last_100"] < 0.05
    return {"best_value": best, "trial_count": len(complete_values), "plateau_last_100_lt_0_05_mae": plateau, **recent_windows}


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = f"{value:.4f}"
            cells.append(str(value))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_report(summary: dict[str, object], top20: pd.DataFrame, importances: dict[str, float]) -> None:
    top_rows = []
    param_cols = [col for col in top20.columns if col.startswith("params_")]
    for _, row in top20.head(20).iterrows():
        params = {col.replace("params_", ""): row[col] for col in param_cols if pd.notna(row.get(col))}
        top_rows.append(
            {
                "trial": int(row["number"]),
                "cv_mae": float(row["value"]),
                "family": params.get("family", ""),
                "params": json.dumps(params, sort_keys=True),
            }
        )

    importance_rows = [{"parameter": key, "importance": value} for key, value in list(importances.items())[:20]]
    lines = [
        "# Big West Per-40 Impact Optuna Tuning",
        "",
        "This study tunes the main model only: `impact_score` target, `per40_core` features, and season-holdout cross-validation.",
        "No held-out test set is used or inspected in this workflow; the objective is cross-validation MAE.",
        "",
        "## Summary",
        "",
        f"- Study name: `{summary['study_name']}`",
        f"- Storage: `{summary['storage']}`",
        f"- Trials before run: `{summary['trials_before']}`",
        f"- Trials after run: `{summary['trials_after']}`",
        f"- Complete trials: `{summary['complete_trials']}`",
        f"- Best CV MAE: `{summary['best_cv_mae']:.4f}`",
        f"- Baseline CV MAE: `{summary['baseline']['mae']:.4f}`",
        f"- Improvement vs baseline: `{summary['mae_improvement_vs_baseline']:.4f}`",
        f"- Best model family: `{summary['best_family']}`",
        f"- Best CV R2: `{summary['best_cv_metrics']['r2']:.4f}`",
        f"- Best CV Corr: `{summary['best_cv_metrics']['corr']:.4f}`",
        f"- Convergence note: `{summary['convergence_note']}`",
        "",
        "## Top 20 Trials",
        "",
        markdown_table(top_rows, ["trial", "cv_mae", "family", "params"]),
        "",
        "## Parameter Importance",
        "",
        markdown_table(importance_rows, ["parameter", "importance"]),
        "",
        "## Artifacts",
        "",
        "- `trials.csv`: all trials",
        "- `top20_trials.csv`: top 20 completed trials",
        "- `optimization_history.png`: trial values and best-so-far curve",
        "- `parameter_importance.png`: Optuna parameter importance",
        "- `best_model.pkl`: best model retrained on all available training rows",
        "- `cv_predictions.csv`: out-of-fold predictions for the best tuned configuration",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    storage_path = Path(args.storage)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    X, y, groups, numeric_features, categorical_features, meta = prepare_training_data()
    cv = GroupKFold(n_splits=min(5, groups.nunique()))
    baseline_pred = mean_baseline_cv_predictions(y, cv, groups)
    baseline_metrics = metrics(y.to_numpy(), baseline_pred)

    sampler = optuna.samplers.TPESampler(seed=RANDOM_STATE, multivariate=True, group=True, constant_liar=True)
    study = optuna.create_study(
        study_name=args.study_name,
        direction="minimize",
        sampler=sampler,
        storage=f"sqlite:///{storage_path}",
        load_if_exists=True,
    )
    trials_before = len(study.trials)
    started = time.time()
    study.optimize(
        make_objective(X, y, groups, numeric_features, categorical_features),
        n_trials=args.n_trials,
        timeout=args.timeout,
        show_progress_bar=True,
    )
    elapsed = time.time() - started

    trials_after = len(study.trials)
    trials = trials_dataframe(study)
    trials.to_csv(TRIALS_PATH, index=False)
    complete = trials[trials["state"] == "COMPLETE"].copy()
    top20 = complete.head(20).copy()
    top20.to_csv(TOP20_PATH, index=False)

    try:
        importances = get_param_importances(study)
    except Exception:
        importances = {}
    pd.DataFrame([{"parameter": key, "importance": value} for key, value in importances.items()]).to_csv(
        IMPORTANCE_PATH, index=False
    )
    save_plots(study, trials, importances)

    best_model = suggest_model(study.best_trial)
    best_pred, best_fold_maes = cross_val_predictions(best_model, X, y, groups, numeric_features, categorical_features)
    best_cv_metrics = metrics(y.to_numpy(), best_pred)
    best_pipeline = Pipeline(
        steps=[
            ("preprocess", make_preprocessor(numeric_features, categorical_features)),
            ("model", clone(best_model)),
        ]
    )
    best_pipeline.fit(X, y)
    with MODEL_PATH.open("wb") as file:
        pickle.dump(best_pipeline, file)

    predictions = pd.DataFrame(
        {
            "actual_impact_score": y,
            "cv_predicted_impact_score": best_pred,
            "prediction_error": best_pred - y.to_numpy(),
            "first_big_west_season": groups,
        }
    )
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    complete_values = [float(value) for value in complete["value"].tolist()]
    convergence = convergence_summary(complete_values)
    if convergence.get("plateau_last_100_lt_0_05_mae"):
        convergence_note = "best CV MAE changed by less than 0.05 over the last 100 complete trials"
    else:
        convergence_note = "no clear plateau under the current threshold"

    summary = {
        "study_name": args.study_name,
        "storage": str(storage_path),
        "target": TARGET_COLUMN,
        "feature_set": FEATURE_SET,
        "validation": VALIDATION,
        "trials_before": trials_before,
        "trials_after": trials_after,
        "additional_trials_requested": args.n_trials,
        "elapsed_seconds": elapsed,
        "complete_trials": int(len(complete)),
        "best_trial_number": int(study.best_trial.number),
        "best_cv_mae": float(study.best_value),
        "best_params": study.best_trial.params,
        "best_family": study.best_trial.params.get("family", ""),
        "best_fold_maes": best_fold_maes,
        "best_cv_metrics": best_cv_metrics,
        "baseline": baseline_metrics,
        "mae_improvement_vs_baseline": float(baseline_metrics["mae"] - study.best_value),
        "training_data": meta,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "convergence": convergence,
        "convergence_note": convergence_note,
        "artifacts": {
            "trials": str(TRIALS_PATH),
            "top20": str(TOP20_PATH),
            "param_importance": str(IMPORTANCE_PATH),
            "optimization_history": str(OUTPUT_DIR / "optimization_history.png"),
            "parameter_importance_plot": str(OUTPUT_DIR / "parameter_importance.png"),
            "best_model": str(MODEL_PATH),
            "cv_predictions": str(PREDICTIONS_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(summary, top20, importances)

    print(f"Trials before: {trials_before}")
    print(f"Trials after: {trials_after}")
    print(f"Best trial: {study.best_trial.number}")
    print(f"Best CV MAE: {study.best_value:.4f}")
    print(f"Baseline CV MAE: {baseline_metrics['mae']:.4f}")
    print(f"Best family: {study.best_trial.params.get('family')}")
    print(f"Wrote report to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
