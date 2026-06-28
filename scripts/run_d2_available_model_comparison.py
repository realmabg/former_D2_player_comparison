#!/usr/bin/env python3
"""Run D2-available feature model comparison with hyperparameter tuning."""

from __future__ import annotations

import json
import math
import warnings
import argparse
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


warnings.filterwarnings("ignore", message="X does not have valid feature names.*")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

RANDOM_STATE = 42
DATA_PATH = Path("data/modeling/training/d2_available_training.csv")
OUT_DIR = Path("reports/d2_available_model_comparison")
BART_EXCLUSIONS_PATH = Path("data/modeling/training/bart_outcome_training_exclusions.csv")

TARGETS = {
    "bpr": {"column": "big_west_bpr", "label": "EvanMiya BPR"},
    "bpm": {"column": "big_west_bpm", "label": "Sports Reference BPM"},
    "bpm_percentile": {"column": "big_west_bpm_percentile", "label": "BPM percentile"},
    "porpag": {"column": "target_porpag", "label": "BartTorvik PORPAG"},
}

KEY_COLUMNS = [
    "player_name",
    "destination_school",
    "first_big_west_season",
]

NUMERIC_FEATURES = [
    "height_in",
    "weight_lbs",
    "source_games",
    "source_mpg",
    "source_minutes_share",
    "source_fg_pct",
    "source_fg3_pct",
    "source_ft_pct",
    "source_efg_pct",
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
    "source_conf_power",
    "destination_conf_power",
    "conf_power_delta",
    "source_team_power",
    "destination_team_power",
    "team_power_delta",
    "projected_destination_mpg",
    "source_low_minutes_flag",
    "source_low_games_flag",
]
CATEGORICAL_FEATURES = [
    "destination_school",
    "position",
    "position_bucket",
    "height_bucket",
    "source_role_bucket",
    "class_entering_destination",
    "source_level",
    "source_conference",
]


@dataclass(frozen=True)
class Candidate:
    model_name: str
    family: str
    estimator: object
    params: dict[str, object]


def number_frame(frame: pd.DataFrame, numeric_features: list[str], categorical_features: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in numeric_features:
        values = pd.to_numeric(out[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        fill = float(values.median()) if values.notna().any() else 0.0
        out[column] = values.fillna(fill)
    for column in categorical_features:
        out[column] = out[column].fillna("").astype(str)
    return out


def normalized_key(frame: pd.DataFrame) -> pd.Series:
    key = pd.Series([""] * len(frame), index=frame.index, dtype="object")
    for column in KEY_COLUMNS:
        values = frame[column].fillna("").astype(str).str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
        key = key + "|" + values
    return key


def load_bart_exclusion_keys() -> set[str]:
    if not BART_EXCLUSIONS_PATH.exists():
        return set()
    exclusions = pd.read_csv(BART_EXCLUSIONS_PATH)
    if not set(KEY_COLUMNS).issubset(exclusions.columns):
        return set()
    active = exclusions.copy()
    if "exclude_from_porpag_training" in active.columns:
        active = active[active["exclude_from_porpag_training"].astype(str).str.lower().isin(["1", "true", "yes", "y"])]
    return set(normalized_key(active))


def make_pipeline(estimator: object, numeric_features: list[str], categorical_features: list[str]) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "preprocess",
                ColumnTransformer(
                    transformers=[
                        ("num", StandardScaler(), numeric_features),
                        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
                    ]
                ),
            ),
            ("model", estimator),
        ]
    )


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    corr = float(np.corrcoef(y_true, y_pred)[0, 1]) if len(y_true) > 1 and np.std(y_pred) else 0.0
    spear = spearmanr(y_true, y_pred).correlation if len(y_true) > 1 else 0.0
    if math.isnan(spear):
        spear = 0.0
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "pearson": corr,
        "spearman": float(spear),
    }


def top_decile_lift(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    n_top = max(1, int(math.ceil(len(y_true) * 0.10)))
    top_idx = np.argsort(y_pred)[-n_top:]
    return {
        "top_decile_count": float(n_top),
        "top_decile_actual_mean": float(np.mean(y_true[top_idx])),
        "overall_actual_mean": float(np.mean(y_true)),
        "top_decile_lift": float(np.mean(y_true[top_idx]) - np.mean(y_true)),
    }


def cross_val_predict_model(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series, groups: pd.Series) -> np.ndarray:
    cv = GroupKFold(n_splits=min(5, groups.nunique()))
    predictions = np.zeros(len(y), dtype=float)
    for train_idx, test_idx in cv.split(X, y, groups):
        fold = clone(pipeline)
        fold.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions[test_idx] = fold.predict(X.iloc[test_idx])
    return predictions


def candidates() -> list[Candidate]:
    specs: list[Candidate] = []
    for alpha in [0.03, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000]:
        specs.append(Candidate(f"ridge_alpha_{alpha}", "ridge", Ridge(alpha=alpha), {"alpha": alpha}))

    for alpha in [0.01, 0.03, 0.1, 0.3, 1.0]:
        for l1_ratio in [0.05, 0.15, 0.35, 0.65]:
            specs.append(
                Candidate(
                    f"elastic_alpha_{alpha}_l1_{l1_ratio}",
                    "elastic_net",
                    ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=30000, random_state=RANDOM_STATE),
                    {"alpha": alpha, "l1_ratio": l1_ratio},
                )
            )

    for depth in [2, 3, 4, 6, None]:
        for leaf in [3, 6, 10]:
            specs.append(
                Candidate(
                    f"rf_depth_{depth}_leaf_{leaf}",
                    "random_forest",
                    RandomForestRegressor(
                        n_estimators=250,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        max_features=0.75,
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                    {"n_estimators": 250, "max_depth": depth, "min_samples_leaf": leaf, "max_features": 0.75},
                )
            )

    for depth in [2, 3, 5, None]:
        for leaf in [3, 6, 10]:
            specs.append(
                Candidate(
                    f"extra_trees_depth_{depth}_leaf_{leaf}",
                    "extra_trees",
                    ExtraTreesRegressor(
                        n_estimators=250,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        max_features=0.75,
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                    {"n_estimators": 250, "max_depth": depth, "min_samples_leaf": leaf, "max_features": 0.75},
                )
            )

    for depth in [1, 2, 3]:
        for lr in [0.015, 0.03, 0.06]:
            for leaf in [5, 10]:
                specs.append(
                    Candidate(
                        f"gbr_depth_{depth}_lr_{lr}_leaf_{leaf}",
                        "gradient_boosting",
                        GradientBoostingRegressor(
                            n_estimators=180,
                            learning_rate=lr,
                            max_depth=depth,
                            min_samples_leaf=leaf,
                            subsample=0.8,
                            random_state=RANDOM_STATE,
                        ),
                        {"n_estimators": 180, "learning_rate": lr, "max_depth": depth, "min_samples_leaf": leaf},
                    )
                )

    for lr in [0.015, 0.03, 0.06]:
        for leaves in [4, 6, 10, 16]:
            for l2 in [1.0, 5.0, 12.0]:
                specs.append(
                    Candidate(
                        f"histgb_lr_{lr}_leaves_{leaves}_l2_{l2}",
                        "hist_gradient_boosting",
                        HistGradientBoostingRegressor(
                            max_iter=180,
                            learning_rate=lr,
                            max_leaf_nodes=leaves,
                            min_samples_leaf=12,
                            l2_regularization=l2,
                            random_state=RANDOM_STATE,
                        ),
                        {"max_iter": 180, "learning_rate": lr, "max_leaf_nodes": leaves, "l2_regularization": l2},
                    )
                )

    for lr in [0.015, 0.03, 0.06]:
        for leaves in [4, 7, 15]:
            for reg_lambda in [1.0, 5.0, 12.0]:
                specs.append(
                    Candidate(
                        f"lgbm_lr_{lr}_leaves_{leaves}_lambda_{reg_lambda}",
                        "lightgbm",
                        lgb.LGBMRegressor(
                            objective="regression",
                            n_estimators=180,
                            learning_rate=lr,
                            num_leaves=leaves,
                            min_child_samples=12,
                            subsample=0.85,
                            colsample_bytree=0.85,
                            reg_alpha=0.2,
                            reg_lambda=reg_lambda,
                            random_state=RANDOM_STATE,
                            verbose=-1,
                            n_jobs=1,
                        ),
                        {"n_estimators": 180, "learning_rate": lr, "num_leaves": leaves, "reg_lambda": reg_lambda},
                    )
                )

    for lr in [0.015, 0.03, 0.06]:
        for depth in [2, 3, 4]:
            for reg_lambda in [2.0, 8.0]:
                specs.append(
                    Candidate(
                        f"xgb_lr_{lr}_depth_{depth}_lambda_{reg_lambda}",
                        "xgboost",
                        xgb.XGBRegressor(
                            objective="reg:squarederror",
                            n_estimators=180,
                            learning_rate=lr,
                            max_depth=depth,
                            min_child_weight=3,
                            subsample=0.85,
                            colsample_bytree=0.85,
                            reg_alpha=0.2,
                            reg_lambda=reg_lambda,
                            random_state=RANDOM_STATE,
                            n_jobs=1,
                        ),
                        {"n_estimators": 180, "learning_rate": lr, "max_depth": depth, "reg_lambda": reg_lambda},
                    )
                )
    return specs


def model_row(target_name: str, candidate: Candidate, y: pd.Series, cv_pred: np.ndarray, train_pred: np.ndarray) -> dict[str, object]:
    cv_metrics = metrics(y.to_numpy(), cv_pred)
    train_metrics = metrics(y.to_numpy(), train_pred)
    lift = top_decile_lift(y.to_numpy(), cv_pred)
    return {
        "target": target_name,
        "model_name": candidate.model_name,
        "family": candidate.family,
        "status": "ok",
        "cv_mae": cv_metrics["mae"],
        "cv_rmse": cv_metrics["rmse"],
        "cv_r2": cv_metrics["r2"],
        "cv_pearson": cv_metrics["pearson"],
        "cv_spearman": cv_metrics["spearman"],
        "train_mae": train_metrics["mae"],
        "train_rmse": train_metrics["rmse"],
        "train_r2": train_metrics["r2"],
        "top_decile_actual_mean": lift["top_decile_actual_mean"],
        "overall_actual_mean": lift["overall_actual_mean"],
        "top_decile_lift": lift["top_decile_lift"],
        "params_json": json.dumps(candidate.params, sort_keys=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=DATA_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--min-target-mpg", type=float, default=0.0)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(args.data_path)
    if args.min_target_mpg > 0:
        if "big_west_mpg" not in raw.columns:
            raise ValueError("--min-target-mpg requires `big_west_mpg` in the dataset")
        raw = raw[pd.to_numeric(raw["big_west_mpg"], errors="coerce").fillna(0) >= args.min_target_mpg].copy()
    raw["big_west_bpm_percentile"] = pd.to_numeric(raw["big_west_bpm"], errors="coerce").rank(pct=True) * 100
    numeric_features = [feature for feature in NUMERIC_FEATURES if feature in raw.columns]
    categorical_features = [feature for feature in CATEGORICAL_FEATURES if feature in raw.columns]
    all_candidates = candidates()
    bart_exclusion_keys = load_bart_exclusion_keys()
    bart_exclusions_applied = 0

    all_rows: list[dict[str, object]] = []
    prediction_frames = []
    for target_name, target_spec in TARGETS.items():
        target_column = target_spec["column"]
        included = raw[pd.to_numeric(raw[target_column], errors="coerce").notna()].copy()
        if target_name == "porpag" and bart_exclusion_keys:
            before_count = len(included)
            included = included[~normalized_key(included).isin(bart_exclusion_keys)].copy()
            bart_exclusions_applied = before_count - len(included)
        included = number_frame(included, numeric_features, categorical_features)
        X = included[numeric_features + categorical_features]
        y = pd.to_numeric(included[target_column], errors="coerce")
        groups = included["first_big_west_season"].astype(str)

        baseline_pred = np.zeros(len(y), dtype=float)
        cv = GroupKFold(n_splits=min(5, groups.nunique()))
        for train_idx, test_idx in cv.split(X, y, groups):
            baseline_pred[test_idx] = float(y.iloc[train_idx].mean())
        baseline_metrics = metrics(y.to_numpy(), baseline_pred)
        baseline_lift = top_decile_lift(y.to_numpy(), baseline_pred)
        all_rows.append(
            {
                "target": target_name,
                "model_name": "mean_baseline",
                "family": "baseline",
                "status": "baseline",
                "cv_mae": baseline_metrics["mae"],
                "cv_rmse": baseline_metrics["rmse"],
                "cv_r2": baseline_metrics["r2"],
                "cv_pearson": baseline_metrics["pearson"],
                "cv_spearman": baseline_metrics["spearman"],
                "train_mae": baseline_metrics["mae"],
                "train_rmse": baseline_metrics["rmse"],
                "train_r2": baseline_metrics["r2"],
                "top_decile_actual_mean": baseline_lift["top_decile_actual_mean"],
                "overall_actual_mean": baseline_lift["overall_actual_mean"],
                "top_decile_lift": baseline_lift["top_decile_lift"],
                "params_json": "{}",
                "rows_used": len(included),
                "notes": "Mean prediction within each training fold",
            }
        )

        best_pred = None
        best_name = ""
        best_mae = float("inf")
        target_rows: list[dict[str, object]] = []
        for index, candidate in enumerate(all_candidates, start=1):
            pipeline = make_pipeline(candidate.estimator, numeric_features, categorical_features)
            try:
                cv_pred = cross_val_predict_model(pipeline, X, y, groups)
                pipeline.fit(X, y)
                train_pred = pipeline.predict(X)
                row = model_row(target_name, candidate, y, cv_pred, train_pred)
                row["rows_used"] = len(included)
                row["notes"] = ""
                target_rows.append(row)
                if row["cv_mae"] < best_mae:
                    best_mae = float(row["cv_mae"])
                    best_pred = cv_pred
                    best_name = candidate.model_name
            except Exception as error:
                target_rows.append(
                    {
                        "target": target_name,
                        "model_name": candidate.model_name,
                        "family": candidate.family,
                        "status": "failed",
                        "cv_mae": np.nan,
                        "cv_rmse": np.nan,
                        "cv_r2": np.nan,
                        "cv_pearson": np.nan,
                        "cv_spearman": np.nan,
                        "train_mae": np.nan,
                        "train_rmse": np.nan,
                        "train_r2": np.nan,
                        "top_decile_actual_mean": np.nan,
                        "overall_actual_mean": np.nan,
                        "top_decile_lift": np.nan,
                        "params_json": json.dumps(candidate.params, sort_keys=True),
                        "rows_used": len(included),
                        "notes": str(error),
                    }
                )
        all_rows.extend(target_rows)

        if best_pred is not None:
            prediction_frame = included[
                [
                    "target_conference",
                    "player_name",
                    "source_school",
                    "source_conference",
                    "source_level",
                    "destination_school",
                    "first_big_west_season",
                ]
            ].copy()
            prediction_frame["target"] = target_name
            prediction_frame["actual"] = y.to_numpy()
            prediction_frame["cv_prediction"] = best_pred
            prediction_frame["cv_error"] = best_pred - y.to_numpy()
            prediction_frame["best_model"] = best_name
            prediction_frames.append(prediction_frame)

        print(f"{target_name}: evaluated {len(target_rows)} candidates on {len(included)} rows; best={best_name} mae={best_mae:.3f}")

    leaderboard = pd.DataFrame(all_rows)
    leaderboard.to_csv(args.out_dir / "leaderboard.csv", index=False)
    if prediction_frames:
        pd.concat(prediction_frames, ignore_index=True).to_csv(args.out_dir / "best_cv_predictions.csv", index=False)

    ok = leaderboard[leaderboard["status"].isin(["ok", "baseline"])].copy()
    ok = ok.sort_values(["target", "cv_mae", "cv_rmse"])
    top20 = ok.groupby("target", group_keys=False).head(20)
    top20.to_csv(args.out_dir / "top20_by_target.csv", index=False)
    best = ok[ok["status"].eq("ok")].sort_values(["target", "cv_mae"]).groupby("target", as_index=False).head(1)
    baseline = ok[ok["model_name"].eq("mean_baseline")][["target", "cv_mae", "cv_rmse", "cv_r2", "cv_pearson", "cv_spearman"]]
    baseline = baseline.rename(
        columns={
            "cv_mae": "baseline_mae",
            "cv_rmse": "baseline_rmse",
            "cv_r2": "baseline_r2",
            "cv_pearson": "baseline_pearson",
            "cv_spearman": "baseline_spearman",
        }
    )
    summary = best.merge(baseline, on="target", how="left")
    summary["mae_gain_vs_baseline"] = summary["baseline_mae"] - summary["cv_mae"]
    summary.to_csv(args.out_dir / "best_models_summary.csv", index=False)

    lines = [
        "# D2-Available Model Comparison",
        "",
        "This report intentionally excludes source-side features that current D2 players cannot have, including source EvanMiya, BartTorvik, or other D1-only advanced ratings.",
        "",
        "## Setup",
        "",
        f"- Dataset: `{args.data_path}`",
        f"- Rows available: {len(raw)}",
        f"- Minimum target MPG filter: {args.min_target_mpg:g}",
        f"- Bart/PORPAG target exclusions applied: {bart_exclusions_applied}",
        f"- Candidate model configurations per target: {len(all_candidates)}",
        "- Validation: season-holdout GroupKFold using `first_big_west_season`",
        "- Selection objective: lowest cross-validated MAE",
        "- Features: D2-available box/per-40 stats, destination school, assumed destination MPG, position, source level/conference, source Massey power, destination Massey power, and conference/team power jump.",
        "",
        "## Best Models",
        "",
        "| Target | Rows | Best model | Family | CV MAE | CV RMSE | CV R2 | Pearson | Spearman | MAE gain vs baseline | Top-decile lift |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.sort_values("target").to_dict("records"):
        lines.append(
            f"| {row['target']} | {int(row['rows_used'])} | {row['model_name']} | {row['family']} | "
            f"{row['cv_mae']:.3f} | {row['cv_rmse']:.3f} | {row['cv_r2']:.3f} | "
            f"{row['cv_pearson']:.3f} | {row['cv_spearman']:.3f} | "
            f"{row['mae_gain_vs_baseline']:.3f} | {row['top_decile_lift']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `CV MAE` is the average absolute miss in the target stat using out-of-fold predictions.",
            "- `CV R2` measures variance explained out of fold; values near zero mean little improvement over a mean predictor.",
            "- `Pearson` measures linear correlation between predicted and actual values.",
            "- `Spearman` measures ranking quality.",
            "- `Top-decile lift` measures whether the players ranked in the top 10% by the model actually beat the average outcome.",
            "",
            "## Outputs",
            "",
            "- `leaderboard.csv`: all tuned configurations and metrics",
            "- `top20_by_target.csv`: best 20 configurations for each target",
            "- `best_models_summary.csv`: one-line summary of the best model per target",
            "- `best_cv_predictions.csv`: out-of-fold predictions from each target's best model",
        ]
    )
    (args.out_dir / "model_comparison_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report to {args.out_dir / 'model_comparison_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
