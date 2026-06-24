#!/usr/bin/env python3
"""Write current missing feature/target coverage reports from the rebuilt training file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRAINING_PATH = Path("data/modeling/training/d2_available_training.csv")
OUT_DIR = Path("data/modeling/training")

KEY_COLUMNS = [
    "player_name",
    "target_conference",
    "source_level",
    "source_school",
    "destination_school",
    "source_season",
    "first_big_west_season",
]

FEATURE_COLUMNS = [
    "height_in",
    "weight_lbs",
    "position",
    "position_bucket",
    "height_bucket",
    "source_class",
    "source_class_context",
    "class_entering_destination",
    "years_in_college_entering_destination",
    "college_stat_seasons_before_transfer",
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
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_conf_power",
    "destination_conf_power",
    "conf_power_delta",
    "source_team_power",
    "destination_team_power",
    "team_power_delta",
]

TARGET_COLUMNS = [
    "big_west_bpr",
    "big_west_obpr",
    "big_west_dbpr",
    "big_west_bpr_poss",
    "big_west_bpm",
    "big_west_bpm_percentile",
    "big_west_porpag",
    "target_porpag",
    "target_barttorvik_bpm",
]


def missing_rows(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        if column not in frame.columns:
            continue
        missing = frame[frame[column].isna()][KEY_COLUMNS].copy()
        missing["missing_column"] = column
        rows.append(missing)
    if not rows:
        return pd.DataFrame(columns=KEY_COLUMNS + ["missing_column"])
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    frame = pd.read_csv(TRAINING_PATH)
    feature_columns = [column for column in FEATURE_COLUMNS if column in frame.columns]
    target_columns = [column for column in TARGET_COLUMNS if column in frame.columns]

    feature_missing = missing_rows(frame, feature_columns)
    target_missing = missing_rows(frame, target_columns)
    feature_missing.to_csv(OUT_DIR / "current_missing_feature_fields.csv", index=False)
    target_missing.to_csv(OUT_DIR / "current_missing_target_fields.csv", index=False)

    summary = []
    for field_type, columns in [("feature", feature_columns), ("target", target_columns)]:
        for column in columns:
            missing_count = int(frame[column].isna().sum())
            summary.append(
                {
                    "field_type": field_type,
                    "column": column,
                    "missing_rows": missing_count,
                    "coverage_pct": round(100 * (1 - frame[column].isna().mean()), 1),
                }
            )

    summary_frame = pd.DataFrame(summary).sort_values(
        ["field_type", "missing_rows", "column"], ascending=[True, False, True]
    )
    summary_frame.to_csv(OUT_DIR / "current_missing_stats_summary.csv", index=False)
    print(summary_frame[summary_frame["missing_rows"].gt(0)].to_string(index=False))

    non_bpr = target_missing[
        target_missing["missing_column"].isin(
            ["big_west_porpag", "target_porpag", "target_barttorvik_bpm"]
        )
    ].sort_values(["player_name", "missing_column"])
    print("\nRemaining non-BPR target rows:")
    print(non_bpr.to_string(index=False))

    print("\nRemaining feature rows:")
    print(feature_missing.to_string(index=False))


if __name__ == "__main__":
    main()
