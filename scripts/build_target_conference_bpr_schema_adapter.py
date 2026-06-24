#!/usr/bin/env python3
"""Add EvanMiya BPR outcomes/features to the target-conference model schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


SCHEMA_PATH = Path("data/target_conference_transfer_modeling_big_west_schema.csv")
EVANMIYA_PATH = Path("data/target_conference_transfer_modeling_with_evanmiya.csv")
OUTPUT_PATH = Path("data/target_conference_transfer_modeling_bpr_schema.csv")
SUMMARY_PATH = Path("data/target_conference_bpr_schema_summary.csv")

JOIN_LEFT = [
    "target_conference",
    "player_slug",
    "source_school",
    "destination_school",
    "source_season",
    "first_big_west_season",
]
JOIN_RIGHT = [
    "target_conference",
    "player_key",
    "source_school",
    "destination_school",
    "source_season",
    "first_target_season",
]

EVANMIYA_COLUMNS = [
    "source_evanmiya_match_method",
    "source_evanmiya_player_name",
    "source_evanmiya_team",
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
    "target_evanmiya_match_method",
    "target_evanmiya_player_name",
    "target_evanmiya_team",
    "target_evanmiya_rank",
    "target_evanmiya_obpr",
    "target_evanmiya_dbpr",
    "target_evanmiya_bpr",
    "target_evanmiya_poss",
    "target_evanmiya_box_obpr",
    "target_evanmiya_box_dbpr",
    "target_evanmiya_box_bpr",
    "target_evanmiya_adj_team_off_eff",
    "target_evanmiya_adj_team_def_eff",
    "target_evanmiya_adj_team_eff_margin",
    "target_evanmiya_plus_minus",
]

NUMERIC_BPR_COLUMNS = [
    "big_west_bpr",
    "big_west_obpr",
    "big_west_dbpr",
    "big_west_bpr_poss",
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


def main() -> int:
    schema = pd.read_csv(SCHEMA_PATH)
    evanmiya = pd.read_csv(EVANMIYA_PATH)

    if schema.duplicated(JOIN_LEFT).any():
        raise ValueError(f"{SCHEMA_PATH} has duplicate join keys")
    if evanmiya.duplicated(JOIN_RIGHT).any():
        raise ValueError(f"{EVANMIYA_PATH} has duplicate join keys")

    merged = schema.merge(
        evanmiya[JOIN_RIGHT + EVANMIYA_COLUMNS],
        left_on=JOIN_LEFT,
        right_on=JOIN_RIGHT,
        how="left",
        suffixes=("", "_evanmiya_join"),
        validate="one_to_one",
    )

    merged["big_west_bpr"] = merged["target_evanmiya_bpr"]
    merged["big_west_obpr"] = merged["target_evanmiya_obpr"]
    merged["big_west_dbpr"] = merged["target_evanmiya_dbpr"]
    merged["big_west_bpr_poss"] = merged["target_evanmiya_poss"]
    for column in NUMERIC_BPR_COLUMNS:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    drop_columns = [column for column in ["player_key", "first_target_season"] if column in merged.columns]
    merged = merged.drop(columns=drop_columns)
    merged.to_csv(OUTPUT_PATH, index=False)

    summary_rows = [
        {"metric": "rows", "value": len(merged)},
        {"metric": "rows_with_target_bpr", "value": int(merged["big_west_bpr"].notna().sum())},
        {"metric": "rows_with_source_bpr", "value": int(merged["source_evanmiya_bpr"].notna().sum())},
        {"metric": "rows_missing_evanmiya_join", "value": int(merged["target_evanmiya_match_method"].isna().sum())},
    ]
    pd.DataFrame(summary_rows).to_csv(SUMMARY_PATH, index=False)

    print(f"Wrote {len(merged)} rows to {OUTPUT_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    print(f"Target BPR rows: {int(merged['big_west_bpr'].notna().sum())}")
    print(f"Source BPR rows: {int(merged['source_evanmiya_bpr'].notna().sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
