#!/usr/bin/env python3
"""Append manual current-D2 verified rows into the school-verified files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_MANUAL = Path("data/current_d2_manual_verified_stats.csv")
DEFAULT_SCHOOL = Path("data/current_d2_school_verified_stats.csv")
DEFAULT_RAW = Path("data/current_d2_school_verified_raw_rows.csv")

STAT_OUTPUT_COLUMNS = [
    "Player Name",
    "Team",
    "Conference",
    "source_url",
    "source_method",
    "row_match_text",
    "GP",
    "MIN",
    "MPG",
    "FGM",
    "FGA",
    "FG%",
    "3PTM",
    "3PTA",
    "3PT%",
    "FTM",
    "FTA",
    "FT%",
    "PTS",
    "PPG",
    "ORB",
    "DRB",
    "TOT RB",
    "RPG",
    "PF",
    "AST",
    "TO",
    "STL",
    "BLK",
    "APG",
    "TOPG",
    "SPG",
    "BPG",
    "pts_per_40",
    "reb_per_40",
    "ast_per_40",
    "stl_per_40",
    "blk_per_40",
    "tov_per_40",
    "eFG",
    "three_share",
    "AST_TOV",
    "FTR",
    "TS_pct",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--school", type=Path, default=DEFAULT_SCHOOL)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    args = parser.parse_args()

    manual = pd.read_csv(args.manual).fillna("")
    if manual.empty:
        print(f"No manual rows found in {args.manual}")
        return 0

    manual_rows = manual.copy()
    if "source_method" not in manual_rows.columns:
        manual_rows["source_method"] = "manual_columns"
    else:
        manual_rows["source_method"] = manual_rows["source_method"].replace("", "manual_columns").fillna("manual_columns")
    manual_rows["row_match_text"] = manual_rows.apply(
        lambda row: f"manual current-D2 row: {row.get('Player Name', '')} {row.get('Team', '')}",
        axis=1,
    )
    for column in STAT_OUTPUT_COLUMNS:
        if column not in manual_rows.columns:
            manual_rows[column] = pd.NA
    manual_rows = manual_rows[STAT_OUTPUT_COLUMNS]

    school = pd.read_csv(args.school) if args.school.exists() else pd.DataFrame(columns=STAT_OUTPUT_COLUMNS)
    combined = pd.concat([school, manual_rows], ignore_index=True)
    combined = combined.drop_duplicates(subset=["Player Name", "Team"], keep="last")
    combined.to_csv(args.school, index=False)

    raw = pd.read_csv(args.raw) if args.raw.exists() else pd.DataFrame()
    raw_rows = []
    for row in manual_rows.to_dict("records"):
        raw_rows.append(
            {
                "Player Name": row.get("Player Name", ""),
                "Team": row.get("Team", ""),
                "Conference": row.get("Conference", ""),
                "source_url": row.get("source_url", ""),
                "source_method": "manual_columns",
                "row_match_text": row.get("row_match_text", ""),
                "raw_row_json": json.dumps(row, default=str, sort_keys=True),
            }
        )
    raw_combined = pd.concat([raw, pd.DataFrame(raw_rows)], ignore_index=True)
    raw_combined = raw_combined.drop_duplicates(subset=["Player Name", "Team"], keep="last")
    raw_combined.to_csv(args.raw, index=False)

    print(f"Appended {len(manual_rows)} manual rows into {args.school}")
    print(f"Updated raw rows at {args.raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
