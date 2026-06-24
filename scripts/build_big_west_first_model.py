#!/usr/bin/env python3
"""Compare first-pass Big West transfer impact models."""

from __future__ import annotations

import csv
import argparse
import json
import re
import warnings
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", message="X does not have valid feature names.*")
warnings.filterwarnings("ignore", message="`sklearn.utils.parallel.delayed` should be used.*")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

MODELING_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
MASSEY_POWER_PATHS = [
    Path("data/massey_conference_power.csv"),
    Path("data/massey_conference_ratings.csv"),
    Path("data/massey_power.csv"),
]
PREDICTIONS_PATH = Path("data/big_west_model_predictions.csv")
FEATURE_IMPORTANCE_PATH = Path("data/big_west_model_feature_importance.csv")
LEADERBOARD_PATH = Path("data/big_west_model_leaderboard.csv")
METRICS_PATH = Path("data/big_west_model_metrics.json")
WEIGHTS_PATH = Path("data/big_west_model_learned_weights.json")

TARGETS = {
    "impact_score": {
        "column": "impact_score",
        "higher_is_better": True,
        "label": "Big West impact score",
    },
    "bpm": {
        "column": "big_west_bpm",
        "higher_is_better": True,
        "label": "Big West BPM",
    },
    "bpm_percentile": {
        "column": "big_west_bpm_percentile",
        "higher_is_better": True,
        "label": "Big West BPM percentile",
    },
    "porpag": {
        "column": "big_west_porpag",
        "higher_is_better": True,
        "label": "Big West PORPAG",
    },
    "bpr": {
        "column": "big_west_bpr",
        "higher_is_better": True,
        "label": "Target-conference EvanMiya BPR",
    },
}

RANDOM_STATE = 42

NUMERIC_FEATURES = [
    "height_in",
    "weight_lbs",
    "source_games",
    "source_mpg",
    "source_minutes_share",
    "source_ppg",
    "source_rpg",
    "source_apg",
    "source_spg",
    "source_bpg",
    "source_topg",
    "source_fg_pct",
    "source_fg3_pct",
    "source_ft_pct",
    "source_efg_pct",
    "source_ts_pct",
    "source_three_rate",
    "source_ft_rate",
    "source_per",
    "source_usg_pct",
    "source_ws",
    "source_bpm",
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
]
COMMON_BOX_NUMERIC_FEATURES = [
    "height_in",
    "weight_lbs",
    "source_games",
    "source_mpg",
    "source_minutes_share",
    "source_ppg",
    "source_rpg",
    "source_apg",
    "source_spg",
    "source_bpg",
    "source_topg",
    "source_fg_pct",
    "source_fg3_pct",
    "source_ft_pct",
    "source_efg_pct",
    "source_ts_pct",
    "source_three_rate",
    "source_ft_rate",
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
]
PER40_CORE_NUMERIC_FEATURES = [
    "height_in",
    "weight_lbs",
    "source_games",
    "source_mpg",
    "source_minutes_share",
    "source_fg_pct",
    "source_fg3_pct",
    "source_ft_pct",
    "source_efg_pct",
    "source_ts_pct",
    "source_three_rate",
    "source_ft_rate",
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
]
OPTIONAL_NUMERIC_FEATURES = [
    "source_conf_power",
    "destination_conf_power",
    "conf_power_delta",
    "source_evanmiya_rank",
    "source_evanmiya_obpr",
    "source_evanmiya_dbpr",
    "source_evanmiya_bpr",
    "source_evanmiya_poss",
    "source_evanmiya_box_obpr",
    "source_evanmiya_box_dbpr",
    "source_evanmiya_box_bpr",
    "source_evanmiya_adj_team_off_eff",
    "source_evanmiya_adj_team_def_eff",
    "source_evanmiya_adj_team_eff_margin",
    "source_evanmiya_plus_minus",
]
CATEGORICAL_FEATURES = ["position", "source_level", "source_conference"]
OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "source_school",
    "source_conference",
    "source_level",
    "destination_school",
    "first_big_west_season",
    "impact_score",
    "predicted_impact_score",
    "cv_predicted_impact_score",
    "prediction_error",
    "projected_tier",
    "outcome_tier",
]


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def number(value: object, fallback: float = 0.0) -> float:
    try:
        if value == "" or pd.isna(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def possible_columns(row: dict[str, str], names: list[str]) -> str:
    lowered = {normalize(key).replace(" ", "_"): key for key in row}
    for name in names:
        key = lowered.get(normalize(name).replace(" ", "_"))
        if key:
            return row.get(key, "")
    return ""


def load_massey_power() -> tuple[dict[tuple[str, str], float], str]:
    for path in MASSEY_POWER_PATHS:
        if not path.exists():
            continue
        power: dict[tuple[str, str], float] = {}
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                season = possible_columns(row, ["season", "year", "season_start"])
                conference = possible_columns(row, ["conference", "conf", "source_conference"])
                value = possible_columns(row, ["power", "conference_power", "rating", "massey_power"])
                if not season or not conference or value == "":
                    continue
                if len(season) == 4:
                    season = f"{season}-{str(int(season) + 1)[-2:]}"
                power[(season, normalize(conference))] = number(value)
        if power:
            return power, str(path)
    return {}, ""


def include_row(row: pd.Series, massey_power: dict[tuple[str, str], float]) -> tuple[bool, str, float | None]:
    source_level = str(row["source_level"])
    if source_level in {"D1", "D2"}:
        conf_power = number(row.get("source_conf_power", ""), fallback=np.nan)
        return True, "d1_d2_model_scope", None if pd.isna(conf_power) else conf_power
    if source_level == "JUCO":
        key = (str(row["source_season"]), normalize(row["source_conference"]))
        if key in massey_power:
            return True, "juco_massey_power_matched", massey_power[key]
        return False, "juco_without_massey_power"
    return False, f"{source_level.lower()}_excluded"


def outcome_tier(score: float) -> str:
    if score >= 80:
        return "Big West impact starter"
    if score >= 65:
        return "Big West starter/plus rotation"
    if score >= 45:
        return "Big West rotation"
    return "Limited Big West role"


def make_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
        ]
    )


def model_specs() -> list[tuple[str, object]]:
    return [
        ("ridge_alpha_0_1", Ridge(alpha=0.1, random_state=RANDOM_STATE)),
        ("ridge_alpha_1", Ridge(alpha=1.0, random_state=RANDOM_STATE)),
        ("ridge_alpha_3", Ridge(alpha=3.0, random_state=RANDOM_STATE)),
        ("ridge_alpha_10", Ridge(alpha=10.0, random_state=RANDOM_STATE)),
        ("ridge_alpha_30", Ridge(alpha=30.0, random_state=RANDOM_STATE)),
        ("ridge_alpha_100", Ridge(alpha=100.0, random_state=RANDOM_STATE)),
        ("elastic_net_a0_05_l10_15", ElasticNet(alpha=0.05, l1_ratio=0.15, max_iter=20000, random_state=RANDOM_STATE)),
        ("elastic_net_a0_10_l10_50", ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=20000, random_state=RANDOM_STATE)),
        ("elastic_net_a0_20_l10_25", ElasticNet(alpha=0.2, l1_ratio=0.25, max_iter=20000, random_state=RANDOM_STATE)),
        ("elastic_net_a0_50_l10_10", ElasticNet(alpha=0.5, l1_ratio=0.1, max_iter=20000, random_state=RANDOM_STATE)),
        ("elastic_net_a1_00_l10_05", ElasticNet(alpha=1.0, l1_ratio=0.05, max_iter=20000, random_state=RANDOM_STATE)),
        (
            "rf_300_depth2_leaf8",
            RandomForestRegressor(
                n_estimators=300,
                max_depth=2,
                min_samples_leaf=8,
                max_features=0.7,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "rf_500_depth3_leaf5",
            RandomForestRegressor(
                n_estimators=500,
                max_depth=3,
                min_samples_leaf=5,
                max_features=0.7,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "rf_500_depth4_leaf4",
            RandomForestRegressor(
                n_estimators=500,
                max_depth=4,
                min_samples_leaf=4,
                max_features="sqrt",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "rf_800_depth6_leaf3",
            RandomForestRegressor(
                n_estimators=800,
                max_depth=6,
                min_samples_leaf=3,
                max_features=0.8,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "rf_800_depth_none_leaf5",
            RandomForestRegressor(
                n_estimators=800,
                max_depth=None,
                min_samples_leaf=5,
                max_features=0.6,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "extra_trees_500_leaf4",
            ExtraTreesRegressor(
                n_estimators=500,
                max_depth=4,
                min_samples_leaf=4,
                max_features="sqrt",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "extra_trees_800_depth3_leaf6",
            ExtraTreesRegressor(
                n_estimators=800,
                max_depth=3,
                min_samples_leaf=6,
                max_features=0.8,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "extra_trees_800_depth_none_leaf5",
            ExtraTreesRegressor(
                n_estimators=800,
                max_depth=None,
                min_samples_leaf=5,
                max_features=0.6,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "gradient_boosting_shallow",
            GradientBoostingRegressor(
                n_estimators=120,
                learning_rate=0.035,
                max_depth=2,
                min_samples_leaf=8,
                subsample=0.8,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "gradient_boosting_deeper",
            GradientBoostingRegressor(
                n_estimators=240,
                learning_rate=0.02,
                max_depth=3,
                min_samples_leaf=6,
                subsample=0.75,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "gradient_boosting_many_tiny",
            GradientBoostingRegressor(
                n_estimators=400,
                learning_rate=0.0125,
                max_depth=2,
                min_samples_leaf=5,
                subsample=0.85,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "hist_gradient_boosting_l2",
            HistGradientBoostingRegressor(
                max_iter=160,
                learning_rate=0.035,
                max_leaf_nodes=8,
                min_samples_leaf=10,
                l2_regularization=2.0,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "hist_gradient_boosting_more_l2",
            HistGradientBoostingRegressor(
                max_iter=260,
                learning_rate=0.02,
                max_leaf_nodes=6,
                min_samples_leaf=15,
                l2_regularization=8.0,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "lightgbm_small_leaf",
            lgb.LGBMRegressor(
                objective="regression",
                n_estimators=180,
                learning_rate=0.03,
                num_leaves=7,
                min_child_samples=10,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.2,
                reg_lambda=2.0,
                random_state=RANDOM_STATE,
                verbose=-1,
            ),
        ),
        (
            "lightgbm_depth2_regularized",
            lgb.LGBMRegressor(
                objective="regression",
                n_estimators=260,
                learning_rate=0.02,
                num_leaves=4,
                max_depth=2,
                min_child_samples=12,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.5,
                reg_lambda=8.0,
                random_state=RANDOM_STATE,
                verbose=-1,
            ),
        ),
        (
            "lightgbm_more_regularized",
            lgb.LGBMRegressor(
                objective="regression",
                n_estimators=240,
                learning_rate=0.02,
                num_leaves=5,
                min_child_samples=15,
                subsample=0.75,
                colsample_bytree=0.75,
                reg_alpha=0.5,
                reg_lambda=5.0,
                random_state=RANDOM_STATE,
                verbose=-1,
            ),
        ),
        (
            "lightgbm_wider",
            lgb.LGBMRegressor(
                objective="regression",
                n_estimators=180,
                learning_rate=0.025,
                num_leaves=15,
                min_child_samples=8,
                subsample=0.8,
                colsample_bytree=0.75,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=RANDOM_STATE,
                verbose=-1,
            ),
        ),
        (
            "xgboost_depth2_regularized",
            xgb.XGBRegressor(
                objective="reg:squarederror",
                n_estimators=260,
                learning_rate=0.025,
                max_depth=2,
                min_child_weight=4,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.5,
                reg_lambda=8.0,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "xgboost_depth3_balanced",
            xgb.XGBRegressor(
                objective="reg:squarederror",
                n_estimators=220,
                learning_rate=0.03,
                max_depth=3,
                min_child_weight=3,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.2,
                reg_lambda=3.0,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "xgboost_depth4_slow",
            xgb.XGBRegressor(
                objective="reg:squarederror",
                n_estimators=420,
                learning_rate=0.0125,
                max_depth=4,
                min_child_weight=5,
                subsample=0.75,
                colsample_bytree=0.75,
                reg_alpha=0.8,
                reg_lambda=10.0,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "xgboost_wide_low_reg",
            xgb.XGBRegressor(
                objective="reg:squarederror",
                n_estimators=180,
                learning_rate=0.035,
                max_depth=4,
                min_child_weight=2,
                subsample=0.85,
                colsample_bytree=0.7,
                reg_alpha=0.05,
                reg_lambda=1.5,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
    ]


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "corr": float(np.corrcoef(y_true, y_pred)[0, 1]) if len(y_true) > 1 and np.std(y_pred) else 0.0,
    }


def make_cv(included: pd.DataFrame, validation: str) -> tuple[object, pd.Series | None, str]:
    if validation == "season_holdout":
        groups = included["first_big_west_season"].astype(str)
        season_count = groups.nunique()
        if season_count < 2:
            raise ValueError("Season-holdout validation requires at least two seasons.")
        split_count = min(5, season_count)
        return GroupKFold(n_splits=split_count), groups, f"GroupKFold by first_big_west_season ({split_count} folds)"
    return KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE), None, "shuffled KFold (5 folds)"


def manual_cross_val_predict(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    cv: object,
    groups: pd.Series | None,
    target_column: str,
) -> np.ndarray:
    predictions = np.zeros(len(y), dtype=float)
    split_iter = cv.split(X, y, groups) if groups is not None else cv.split(X, y)
    for train_index, test_index in split_iter:
        fold_pipeline = clone(pipeline)
        fold_pipeline.fit(X.iloc[train_index], y.iloc[train_index])
        predictions[test_index] = fold_pipeline.predict(X.iloc[test_index])
    if target_column == "impact_score":
        return clipped(predictions)
    return predictions


def mean_baseline_cv_predictions(y: pd.Series, cv: object, groups: pd.Series | None) -> np.ndarray:
    predictions = np.zeros(len(y), dtype=float)
    split_iter = cv.split(np.zeros(len(y)), y, groups) if groups is not None else cv.split(np.zeros(len(y)), y)
    for train_index, test_index in split_iter:
        predictions[test_index] = float(y.iloc[train_index].mean())
    return predictions


def clipped(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0, 100)


def aggregate_importance(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    transformed_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    result = permutation_importance(
        pipeline,
        X,
        y,
        n_repeats=40,
        random_state=RANDOM_STATE,
        scoring="neg_mean_absolute_error",
    )
    source_names = numeric_features + categorical_features
    rows = []
    for index, source_name in enumerate(source_names):
        rows.append(
            {
                "feature": source_name,
                "label": source_name,
                "permutation_importance_mean": float(result.importances_mean[index]),
                "permutation_importance_std": float(result.importances_std[index]),
                "model_feature_importance": 0.0,
            }
        )

    model = pipeline.named_steps["model"]
    def base_feature_name(transformed_name: str) -> str:
        clean_name = transformed_name.split("__", 1)[-1]
        if not transformed_name.startswith("cat__"):
            return clean_name
        for feature in categorical_features:
            prefix = f"{feature}_"
            if clean_name.startswith(prefix):
                return feature
        return clean_name

    if hasattr(model, "feature_importances_"):
        raw_importances = model.feature_importances_
        grouped = Counter()
        for name, value in zip(transformed_names, raw_importances):
            grouped[base_feature_name(name)] += float(value)
        for row in rows:
            row["model_feature_importance"] = grouped.get(row["feature"], 0.0)
    elif hasattr(model, "coef_"):
        grouped = Counter()
        for name, value in zip(transformed_names, model.coef_):
            grouped[base_feature_name(name)] += abs(float(value))
        for row in rows:
            row["model_feature_importance"] = grouped.get(row["feature"], 0.0)

    frame = pd.DataFrame(rows)
    max_perm = frame["permutation_importance_mean"].abs().max() or 1.0
    max_model = frame["model_feature_importance"].abs().max() or 1.0
    frame["importance"] = (
        0.6 * frame["permutation_importance_mean"].abs() / max_perm
        + 0.4 * frame["model_feature_importance"].abs() / max_model
    )
    frame["direction"] = np.where(frame["permutation_importance_mean"] >= 0, "positive", "negative")
    return frame.sort_values("importance", ascending=False)


def normalized_weights(importance: pd.DataFrame) -> dict[str, float]:
    max_value = importance["importance"].max() or 1.0
    return {
        row["feature"]: round(0.25 + 1.5 * float(row["importance"]) / max_value, 3)
        for _index, row in importance.iterrows()
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(TARGETS), default="impact_score", help="Outcome column to predict.")
    parser.add_argument(
        "--validation",
        choices=["random_kfold", "season_holdout"],
        default="random_kfold",
        help="Validation scheme. season_holdout keeps whole first-Big-West seasons together.",
    )
    parser.add_argument(
        "--feature-set",
        choices=["all", "common_box", "per40_core"],
        default="all",
        help="Use all available source features or only box-score features available across D1/D2 rows.",
    )
    parser.add_argument(
        "--min-big-west-mpg",
        type=float,
        default=0.0,
        help="Exclude rows below this Big West MPG threshold before training/evaluation.",
    )
    parser.add_argument(
        "--modeling-path",
        type=Path,
        default=MODELING_PATH,
        help="Modeling dataset path. Defaults to the Big West-only dataset.",
    )
    parser.add_argument(
        "--output-prefix",
        default="big_west_model",
        help="Prefix for output files in data/. Defaults to big_west_model.",
    )
    return parser.parse_args()


def target_output_path(
    path: Path,
    target_name: str,
    validation: str,
    feature_set: str,
    min_big_west_mpg: float = 0.0,
) -> Path:
    suffix_parts = []
    if target_name != "impact_score":
        suffix_parts.append(target_name)
    if validation != "random_kfold":
        suffix_parts.append(validation)
    if feature_set != "all":
        suffix_parts.append(feature_set)
    if min_big_west_mpg > 0:
        clean_threshold = str(min_big_west_mpg).replace(".", "p")
        suffix_parts.append(f"min_bw_mpg_{clean_threshold}")
    if not suffix_parts:
        return path
    return path.with_name(f"{path.stem}_{'_'.join(suffix_parts)}{path.suffix}")


def main() -> int:
    args = parse_args()
    target_name = args.target
    validation = args.validation
    feature_set = args.feature_set
    min_big_west_mpg = args.min_big_west_mpg
    target_column = TARGETS[target_name]["column"]
    output_base = Path("data") / args.output_prefix
    predictions_path = target_output_path(output_base.with_name(f"{output_base.name}_predictions.csv"), target_name, validation, feature_set, min_big_west_mpg)
    feature_importance_path = target_output_path(output_base.with_name(f"{output_base.name}_feature_importance.csv"), target_name, validation, feature_set, min_big_west_mpg)
    leaderboard_path = target_output_path(output_base.with_name(f"{output_base.name}_leaderboard.csv"), target_name, validation, feature_set, min_big_west_mpg)
    metrics_path = target_output_path(output_base.with_name(f"{output_base.name}_metrics.json"), target_name, validation, feature_set, min_big_west_mpg)
    weights_path = target_output_path(output_base.with_name(f"{output_base.name}_learned_weights.json"), target_name, validation, feature_set, min_big_west_mpg)

    raw = pd.read_csv(args.modeling_path)
    raw["big_west_bpm_percentile"] = raw["big_west_bpm"].rank(pct=True) * 100
    if target_column not in raw.columns:
        raise ValueError(f"Target column {target_column!r} is not present in {args.modeling_path}")
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
    excluded = raw[~raw["model_include"]].copy()
    if min_big_west_mpg > 0:
        before_minutes_filter = len(included)
        included["big_west_mpg"] = pd.to_numeric(included["big_west_mpg"], errors="coerce")
        low_minutes = included[included["big_west_mpg"].fillna(0.0) < min_big_west_mpg].copy()
        if not low_minutes.empty:
            low_minutes["model_include"] = False
            low_minutes["model_include_reason"] = f"below_min_big_west_mpg_{min_big_west_mpg:g}"
            excluded = pd.concat([excluded, low_minutes], ignore_index=True)
        included = included[included["big_west_mpg"].fillna(0.0) >= min_big_west_mpg].copy()
    else:
        before_minutes_filter = len(included)
    feature_sets = {
        "all": NUMERIC_FEATURES,
        "common_box": COMMON_BOX_NUMERIC_FEATURES,
        "per40_core": PER40_CORE_NUMERIC_FEATURES,
    }
    numeric_features = feature_sets[feature_set][:]
    categorical_features = CATEGORICAL_FEATURES[:]
    for optional_feature in OPTIONAL_NUMERIC_FEATURES:
        if optional_feature in included.columns and pd.to_numeric(included[optional_feature], errors="coerce").notna().any():
            numeric_features.append(optional_feature)
    numeric_features = [feature for feature in numeric_features if feature in included.columns]
    categorical_features = [feature for feature in categorical_features if feature in included.columns]

    included[target_column] = pd.to_numeric(included[target_column], errors="coerce")
    included = included[included[target_column].notna()].copy()
    if included.empty:
        if target_name == "porpag":
            raise ValueError(
                "No usable PORPAG rows yet. Fill data/big_west_barttorvik_outcomes.csv "
                "using data/big_west_barttorvik_outcomes_template.csv, then rebuild "
                "data/big_west_transfer_modeling_dataset.csv."
            )
        raise ValueError(f"No rows have usable values for target {target_name!r} / {target_column!r}")

    for column in numeric_features:
        values = pd.to_numeric(included[column], errors="coerce")
        fill_value = float(values.median()) if values.notna().any() else 0.0
        included[column] = values.fillna(fill_value)
    for column in categorical_features:
        included[column] = included[column].fillna("").astype(str)

    X = included[numeric_features + categorical_features]
    y = included[target_column]
    cv, groups, validation_label = make_cv(included, validation)

    leaderboard_rows = []
    fitted_predictions: dict[str, np.ndarray] = {}
    cv_predictions: dict[str, np.ndarray] = {}
    pipelines: dict[str, Pipeline] = {}
    baseline = mean_baseline_cv_predictions(y, cv, groups)
    baseline_metrics = metrics(y.to_numpy(), baseline)
    leaderboard_rows.append(
        {
            "model_name": "mean_baseline",
            "status": "baseline",
            "cv_mae": baseline_metrics["mae"],
            "cv_rmse": baseline_metrics["rmse"],
            "cv_r2": baseline_metrics["r2"],
            "cv_corr": baseline_metrics["corr"],
            "train_mae": baseline_metrics["mae"],
            "train_rmse": baseline_metrics["rmse"],
            "notes": "predicts the training-set mean impact score for every row",
        }
    )

    for name, model in model_specs():
        pipeline = Pipeline(
            steps=[
                ("preprocess", make_preprocessor(numeric_features, categorical_features)),
                ("model", model),
            ]
        )
        try:
            cv_pred = manual_cross_val_predict(pipeline, X, y, cv, groups, target_column)
            pipeline.fit(X, y)
            fitted = pipeline.predict(X)
            if target_column == "impact_score":
                cv_pred = clipped(cv_pred)
                fitted = clipped(fitted)
        except Exception as error:
            leaderboard_rows.append(
                {
                    "model_name": name,
                    "status": "failed",
                    "cv_mae": "",
                    "cv_rmse": "",
                    "cv_r2": "",
                    "cv_corr": "",
                    "train_mae": "",
                    "train_rmse": "",
                    "notes": str(error),
                }
            )
            continue

        cv_metric = metrics(y.to_numpy(), cv_pred)
        train_metric = metrics(y.to_numpy(), fitted)
        leaderboard_rows.append(
            {
                "model_name": name,
                "status": "ok",
                "cv_mae": cv_metric["mae"],
                "cv_rmse": cv_metric["rmse"],
                "cv_r2": cv_metric["r2"],
                "cv_corr": cv_metric["corr"],
                "train_mae": train_metric["mae"],
                "train_rmse": train_metric["rmse"],
                "notes": "",
            }
        )
        fitted_predictions[name] = fitted
        cv_predictions[name] = cv_pred
        pipelines[name] = pipeline

    leaderboard = pd.DataFrame(leaderboard_rows)
    ok_leaderboard = leaderboard[leaderboard["status"] == "ok"].copy()
    ok_leaderboard["cv_mae_numeric"] = pd.to_numeric(ok_leaderboard["cv_mae"])
    ok_leaderboard = ok_leaderboard.sort_values(["cv_mae_numeric", "cv_rmse"], ascending=True)
    best_model_name = str(ok_leaderboard.iloc[0]["model_name"])
    best_pipeline = pipelines[best_model_name]
    leaderboard["cv_mae_numeric"] = pd.to_numeric(leaderboard["cv_mae"], errors="coerce")
    leaderboard["cv_rmse_numeric"] = pd.to_numeric(leaderboard["cv_rmse"], errors="coerce")
    scored_leaderboard = leaderboard[leaderboard["status"].isin(["ok", "baseline"])].copy()
    scored_leaderboard = scored_leaderboard.sort_values(["cv_mae_numeric", "cv_rmse_numeric"], ascending=True)
    best_overall = scored_leaderboard.iloc[0]

    prediction_columns = [
        "player_name",
        "player_slug",
        "source_school",
        "source_conference",
        "source_level",
        "destination_school",
        "first_big_west_season",
        "impact_score",
        target_column,
        "outcome_tier",
    ]
    prediction_columns = list(dict.fromkeys(prediction_columns))
    predictions = included[prediction_columns].copy()
    predicted_column = f"predicted_{target_column}"
    cv_predicted_column = f"cv_predicted_{target_column}"
    predictions[predicted_column] = fitted_predictions[best_model_name]
    predictions[cv_predicted_column] = cv_predictions[best_model_name]
    predictions["prediction_error"] = predictions[cv_predicted_column] - predictions[target_column]
    if target_column == "impact_score":
        predictions["projected_tier"] = predictions[cv_predicted_column].map(outcome_tier)
        predictions = predictions[OUTPUT_COLUMNS].sort_values(cv_predicted_column, ascending=False)
    else:
        predictions = predictions.sort_values(cv_predicted_column, ascending=False)

    importance = aggregate_importance(best_pipeline, X, y, numeric_features, categorical_features)
    weights = normalized_weights(importance)

    leaderboard["status_order"] = leaderboard["status"].map({"ok": 0, "baseline": 0, "failed": 1}).fillna(2)
    leaderboard = leaderboard.sort_values(["status_order", "cv_mae_numeric", "cv_rmse_numeric"], ascending=True)
    leaderboard = leaderboard.drop(
        columns=[
            column
            for column in ["status_order", "cv_mae_numeric", "cv_rmse_numeric"]
            if column in leaderboard.columns
        ]
    )

    metrics_payload = {
        "target": target_name,
        "target_column": target_column,
        "target_label": TARGETS[target_name]["label"],
        "validation": validation,
        "validation_label": validation_label,
        "feature_set": feature_set,
        "min_big_west_mpg": min_big_west_mpg,
        "rows_available": int(len(raw)),
        "rows_used": int(len(included)),
        "rows_before_minutes_filter": int(before_minutes_filter),
        "rows_excluded_by_minutes_filter": int(before_minutes_filter - len(included)),
        "included_reasons": dict(Counter(included["model_include_reason"])),
        "excluded_reasons": dict(Counter(excluded["model_include_reason"])),
        "source_level_counts": dict(Counter(included["source_level"])),
        "massey_power_source": massey_source,
        "juco_policy": "include only rows with matched Massey conference power; none included if no power file/match exists",
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "baseline": baseline_metrics,
        "best_trained_model": best_model_name,
        "best_trained_model_metrics": ok_leaderboard.iloc[0][
            ["cv_mae", "cv_rmse", "cv_r2", "cv_corr", "train_mae", "train_rmse"]
        ].to_dict(),
        "best_overall": str(best_overall["model_name"]),
        "best_overall_status": str(best_overall["status"]),
        "best_overall_metrics": best_overall[
            ["cv_mae", "cv_rmse", "cv_r2", "cv_corr", "train_mae", "train_rmse"]
        ].to_dict(),
        "model_count": int(len(leaderboard)),
        "successful_model_count": int(len(ok_leaderboard)),
    }

    predictions.to_csv(predictions_path, index=False)
    importance.to_csv(feature_importance_path, index=False)
    leaderboard.to_csv(leaderboard_path, index=False)
    metrics_path.write_text(json.dumps(metrics_payload, indent=2) + "\n", encoding="utf-8")
    weights_path.write_text(json.dumps(weights, indent=2) + "\n", encoding="utf-8")

    print(f"Best trained model: {best_model_name}")
    print(f"Best overall row: {best_overall['model_name']}")
    print(f"Wrote {len(predictions)} predictions to {predictions_path}")
    print(f"Wrote {len(importance)} feature rows to {feature_importance_path}")
    print(f"Wrote {len(leaderboard)} leaderboard rows to {leaderboard_path}")
    print(f"Wrote metrics to {metrics_path}")
    print(f"Wrote learned weights to {weights_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
