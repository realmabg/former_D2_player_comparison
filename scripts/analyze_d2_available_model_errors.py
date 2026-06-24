#!/usr/bin/env python3
"""Analyze out-of-fold errors from the D2-available model comparison."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PREDICTIONS_PATH = Path("reports/d2_available_model_comparison/best_cv_predictions.csv")
TRAINING_PATH = Path("data/modeling/training/d2_available_training.csv")
OUT_DIR = Path("reports/d2_available_model_comparison/error_analysis")


JOIN_COLUMNS = [
    "target_conference",
    "player_name",
    "source_school",
    "source_conference",
    "source_level",
    "destination_school",
    "first_big_west_season",
]


def summarize_group(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = (
        frame.groupby(["target"] + group_cols, dropna=False)
        .agg(
            rows=("abs_error", "size"),
            mae=("abs_error", "mean"),
            median_abs_error=("abs_error", "median"),
            mean_error=("cv_error", "mean"),
            actual_mean=("actual", "mean"),
            prediction_mean=("cv_prediction", "mean"),
        )
        .reset_index()
    )
    return grouped.sort_values(["target", "mae"], ascending=[True, False])


def add_error_context(predictions: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    context_columns = JOIN_COLUMNS + [
        "player_slug",
        "source_season",
        "source_stat_source",
        "position",
        "height_in",
        "weight_lbs",
        "source_games",
        "source_mpg",
        "source_minutes_share",
        "source_ppg",
        "source_rpg",
        "source_apg",
        "source_pts_per_40",
        "source_reb_per_40",
        "source_ast_per_40",
        "source_conf_power",
        "destination_conf_power",
        "conf_power_delta",
        "outcome_tier",
        "source_url",
        "outcome_url",
    ]
    context = training[[c for c in context_columns if c in training.columns]].drop_duplicates(JOIN_COLUMNS)
    enriched = predictions.merge(context, on=JOIN_COLUMNS, how="left")
    enriched["abs_error"] = enriched["cv_error"].abs()
    enriched["under_predicted"] = enriched["cv_error"] < 0
    enriched["over_predicted"] = enriched["cv_error"] > 0
    return enriched


def write_markdown(enriched: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# D2-Available Model Error Analysis",
        "",
        "This report analyzes out-of-fold predictions from the best model for each target. `cv_error = prediction - actual`, so negative values mean the model under-predicted the player.",
        "",
        "## Overall Error",
        "",
        "| Target | Rows | MAE | RMSE | Mean Error | Under-predicted % |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            f"| {row['target']} | {int(row['rows'])} | {row['mae']:.3f} | {row['rmse']:.3f} | "
            f"{row['mean_error']:.3f} | {row['under_predicted_pct']:.1f}% |"
        )

    lines.extend(["", "## Biggest BPR Misses", ""])
    bpr = enriched[enriched["target"].eq("bpr")].sort_values("abs_error", ascending=False).head(15)
    lines.append("| Player | Source | Destination | Season | Actual | Pred | Error | MPG | Source Conf | Level |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---|---|")
    for row in bpr.to_dict("records"):
        lines.append(
            f"| {row['player_name']} | {row['source_school']} | {row['destination_school']} | "
            f"{row['first_big_west_season']} | {row['actual']:.2f} | {row['cv_prediction']:.2f} | "
            f"{row['cv_error']:.2f} | {row.get('source_mpg', np.nan):.1f} | {row['source_conference']} | {row['source_level']} |"
        )

    lines.extend(
        [
            "",
            "## What To Check Next",
            "",
            "- Large negative errors are players who were better than the model expected. These may reveal missing context such as role change, injury recovery, age, or undervalued D2 production.",
            "- Large positive errors are players the model liked too much. These may reveal low-minute source samples, poor transfer fit, or destination role limits.",
            "- If one target conference or one season has much higher MAE, that can mean the dataset expansion added noisy rows or that season behaves differently.",
            "",
            "## Output Files",
            "",
            "- `enriched_cv_errors.csv`: every out-of-fold prediction joined to player/source context",
            "- `largest_misses_by_target.csv`: top misses for every target",
            "- `error_by_target_conference.csv`",
            "- `error_by_source_level.csv`",
            "- `error_by_source_conference.csv`",
            "- `error_by_season.csv`",
        ]
    )
    (OUT_DIR / "error_analysis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(PREDICTIONS_PATH)
    training = pd.read_csv(TRAINING_PATH)
    enriched = add_error_context(predictions, training)

    overall = (
        enriched.groupby("target")
        .agg(
            rows=("abs_error", "size"),
            mae=("abs_error", "mean"),
            rmse=("cv_error", lambda x: float(np.sqrt(np.mean(np.square(x))))),
            mean_error=("cv_error", "mean"),
            under_predicted_pct=("under_predicted", lambda x: float(x.mean() * 100)),
        )
        .reset_index()
        .sort_values("target")
    )

    largest = enriched.sort_values(["target", "abs_error"], ascending=[True, False]).groupby("target", group_keys=False).head(25)

    enriched.to_csv(OUT_DIR / "enriched_cv_errors.csv", index=False)
    largest.to_csv(OUT_DIR / "largest_misses_by_target.csv", index=False)
    overall.to_csv(OUT_DIR / "overall_error_summary.csv", index=False)
    summarize_group(enriched, ["target_conference"]).to_csv(OUT_DIR / "error_by_target_conference.csv", index=False)
    summarize_group(enriched, ["source_level"]).to_csv(OUT_DIR / "error_by_source_level.csv", index=False)
    summarize_group(enriched, ["source_conference"]).to_csv(OUT_DIR / "error_by_source_conference.csv", index=False)
    summarize_group(enriched, ["first_big_west_season"]).to_csv(OUT_DIR / "error_by_season.csv", index=False)
    summarize_group(enriched, ["target_conference", "source_level"]).to_csv(
        OUT_DIR / "error_by_target_conference_source_level.csv", index=False
    )
    write_markdown(enriched, overall)

    print(f"Wrote error analysis to {OUT_DIR}")
    print(overall.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
