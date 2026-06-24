#!/usr/bin/env python3
"""Create a review file for the largest BPR model misses."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ERRORS_PATH = Path("reports/d2_available_model_comparison/error_analysis/enriched_cv_errors.csv")
OUT_DIR = Path("reports/d2_available_model_comparison/bpr_miss_review")


def tag_row(row: pd.Series) -> list[str]:
    tags: list[str] = []
    error = float(row["cv_error"])
    source_mpg = pd.to_numeric(row.get("source_mpg"), errors="coerce")
    source_ppg = pd.to_numeric(row.get("source_ppg"), errors="coerce")
    source_level = str(row.get("source_level", ""))
    jump = pd.to_numeric(row.get("conf_power_delta"), errors="coerce")
    actual = float(row["actual"])
    pred = float(row["cv_prediction"])

    if error < -2.5:
        tags.append("under_predicted_breakout")
    if error > 2.5:
        tags.append("over_predicted_translation")
    if pd.notna(source_mpg) and source_mpg < 10:
        tags.append("low_source_minutes")
    if pd.notna(source_mpg) and source_mpg >= 20 and error < -2.5:
        tags.append("real_prior_role_underweighted")
    if pd.notna(source_ppg) and source_ppg >= 15 and error > 2.5:
        tags.append("scorer_overvalued")
    if pd.notna(jump) and jump >= 10 and error > 2.5:
        tags.append("large_jump_up_overvalued")
    if pd.notna(jump) and jump <= -7 and error < -2.5:
        tags.append("power_drop_breakout")
    if source_level == "D2" and error > 2.5:
        tags.append("d2_to_d1_translation_miss")
    if actual >= 5 and pred <= 2:
        tags.append("star_outcome_missed")
    if actual <= -2 and pred >= 0:
        tags.append("negative_outcome_overpredicted")
    return tags


def reason_from_tags(tags: list[str]) -> str:
    if not tags:
        return "needs_manual_review"
    if "low_source_minutes" in tags and "under_predicted_breakout" in tags:
        return "Prior box score understated player because source role was tiny."
    if "power_drop_breakout" in tags:
        return "High-major or stronger-conference player improved after moving down in conference strength."
    if "d2_to_d1_translation_miss" in tags:
        return "Strong lower-division box production did not translate to the target role."
    if "scorer_overvalued" in tags:
        return "Source scoring volume looked promising but did not translate."
    if "real_prior_role_underweighted" in tags:
        return "Player already had real minutes, but model still missed the breakout."
    if "negative_outcome_overpredicted" in tags:
        return "Model projected a playable outcome, but target-conference performance was negative."
    if "star_outcome_missed" in tags:
        return "Model did not identify a star/impact outcome."
    return ", ".join(tags)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors = pd.read_csv(ERRORS_PATH)
    bpr = errors[errors["target"].eq("bpr")].copy()
    bpr["initial_tags"] = bpr.apply(lambda row: ";".join(tag_row(row)), axis=1)
    bpr["suggested_review_reason"] = bpr["initial_tags"].str.split(";").apply(reason_from_tags)

    review_columns = [
        "player_name",
        "target_conference",
        "source_school",
        "source_conference",
        "source_level",
        "destination_school",
        "first_big_west_season",
        "actual",
        "cv_prediction",
        "cv_error",
        "abs_error",
        "source_games",
        "source_mpg",
        "source_ppg",
        "source_rpg",
        "source_apg",
        "source_pts_per_40",
        "source_reb_per_40",
        "source_ast_per_40",
        "source_conf_power",
        "destination_conf_power",
        "conf_power_delta",
        "position",
        "height_in",
        "weight_lbs",
        "outcome_tier",
        "initial_tags",
        "suggested_review_reason",
        "source_url",
        "outcome_url",
    ]
    review = bpr.sort_values("abs_error", ascending=False)[[c for c in review_columns if c in bpr.columns]]
    review.to_csv(OUT_DIR / "bpr_largest_miss_review.csv", index=False)

    tag_counts = (
        review.assign(initial_tags=review["initial_tags"].replace("", np.nan))
        .dropna(subset=["initial_tags"])
        .assign(initial_tags=lambda df: df["initial_tags"].str.split(";"))
        .explode("initial_tags")
        .groupby("initial_tags")
        .agg(rows=("player_name", "size"), mean_abs_error=("abs_error", "mean"))
        .reset_index()
        .sort_values(["rows", "mean_abs_error"], ascending=[False, False])
    )
    tag_counts.to_csv(OUT_DIR / "bpr_miss_tag_summary.csv", index=False)

    lines = [
        "# BPR Miss Review",
        "",
        "This file reviews the largest out-of-fold BPR misses from the D2-available model. Tags are heuristic starting points, not final labels.",
        "",
        "## Files",
        "",
        "- `bpr_largest_miss_review.csv`: sorted player-level miss review with suggested tags",
        "- `bpr_miss_tag_summary.csv`: aggregate tag counts",
        "",
        "## Most Common Tags",
        "",
        "| Tag | Rows | Mean Abs Error |",
        "|---|---:|---:|",
    ]
    for row in tag_counts.head(15).to_dict("records"):
        lines.append(f"| {row['initial_tags']} | {int(row['rows'])} | {row['mean_abs_error']:.2f} |")
    lines.extend(
        [
            "",
            "## Feature Ideas From Misses",
            "",
            "- `low_source_minutes`: add multi-year trend/context because one-year box score undersells bench players who later broke out.",
            "- `power_drop_breakout`: conference-strength delta helps, but high-major bench-to-mid-major role expansion may need class/age and minutes trend.",
            "- `d2_to_d1_translation_miss`: lower-division scoring volume needs stronger adjustment by conference/team quality and position archetype.",
            "- `scorer_overvalued`: source PPG/per-40 alone can overrate players without efficiency, assists, rebounds, or defensive indicators.",
        ]
    )
    (OUT_DIR / "bpr_miss_review_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote BPR miss review to {OUT_DIR}")
    print(tag_counts.head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
