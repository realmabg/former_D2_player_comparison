#!/usr/bin/env python3
"""Validate the current D2 player stat file for impossible event stats."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path("d2_data_cleaned.csv")
DEFAULT_OUTPUT = Path("data/current_d2_suspicious_event_stats.csv")


def number_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-suspicious", action="store_true")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    numeric_columns = [
        "GP",
        "MIN",
        "MPG",
        "PPG",
        "RPG",
        "APG",
        "TOPG",
        "SPG",
        "BPG",
        "AST",
        "TO",
        "STL",
        "BLK",
        "pts_per_40",
        "reb_per_40",
        "ast_per_40",
        "tov_per_40",
        "stl_per_40",
        "blk_per_40",
    ]
    df = number_frame(df, [column for column in numeric_columns if column in df.columns])

    checks = pd.DataFrame(index=df.index)
    checks["assist_stats_suspicious"] = (df["APG"] > 8) | (df["ast_per_40"] > 12)
    checks["turnover_stats_suspicious"] = (df["TOPG"] > 8) | (df["tov_per_40"] > 12)
    checks["steal_stats_suspicious"] = (df["SPG"] > 5) | (df["stl_per_40"] > 8)
    checks["block_stats_suspicious"] = (df["BPG"] > 5) | (df["blk_per_40"] > 8)
    checks["points_per40_suspicious"] = df["pts_per_40"] > 45
    checks["rebounds_per40_suspicious"] = df["reb_per_40"] > 25
    checks["negative_stat_suspicious"] = df[numeric_columns].lt(0).any(axis=1)

    # These are internal consistency checks. They catch accidental edits, while the
    # threshold checks catch parser/source corruption that is mathematically valid.
    checks["ppg_mismatch"] = (df["PTS"] / df["GP"].replace(0, np.nan) - df["PPG"]).abs() > 0.15
    checks["rpg_mismatch"] = (df["TOT RB"] / df["GP"].replace(0, np.nan) - df["RPG"]).abs() > 0.15
    checks["apg_mismatch"] = (df["AST"] / df["GP"].replace(0, np.nan) - df["APG"]).abs() > 0.15

    flagged = df.loc[checks.any(axis=1)].copy()
    flagged = pd.concat([flagged, checks.loc[flagged.index]], axis=1)
    output_columns = [
        "Player Name",
        "Team",
        "Conference",
        "GP",
        "MIN",
        "MPG",
        "PPG",
        "RPG",
        "APG",
        "TOPG",
        "SPG",
        "BPG",
        "AST",
        "TO",
        "STL",
        "BLK",
        "pts_per_40",
        "reb_per_40",
        "ast_per_40",
        "tov_per_40",
        "stl_per_40",
        "blk_per_40",
        *checks.columns,
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    flagged[output_columns].to_csv(args.output, index=False)

    print(f"Checked {len(df)} rows from {args.input}")
    print(f"Suspicious rows: {len(flagged)}")
    print(f"Wrote {args.output}")
    print(checks.sum().sort_values(ascending=False).to_string())

    if args.fail_on_suspicious and len(flagged):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
