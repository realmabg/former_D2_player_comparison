#!/usr/bin/env python3
"""Write review files for Big West modeling gaps and external rating needs."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MODELING_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
MISSING_PATH = Path("data/big_west_transfer_modeling_dataset_missing.csv")
WORK_QUEUE_PATH = Path("data/big_west_source_stats_work_queue.csv")
INBOUND_PATH = Path("data/big_west_inbound_transfers.csv")

SUMMARY_PATH = Path("data/big_west_modeling_missing_summary.csv")
HISTORICAL_ROWS_NEEDED_PATH = Path("data/big_west_historical_transfer_rows_needed.csv")
MASSEY_NEEDED_PATH = Path("data/massey_conference_power_needed.csv")
MASSEY_TEMPLATE_PATH = Path("data/massey_conference_power_template.csv")
BARTTORVIK_NEEDED_PATH = Path("data/big_west_barttorvik_needed.csv")
BARTTORVIK_TEMPLATE_PATH = Path("data/big_west_barttorvik_outcomes_template.csv")


def previous_season(season: str) -> str:
    start = int(str(season).split("-", 1)[0])
    return f"{start - 1}-{str(start)[-2:]}"


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def completed_season(season: str) -> bool:
    return str(season) != "2026-27"


def main() -> int:
    modeling = pd.read_csv(MODELING_PATH)
    missing = pd.read_csv(MISSING_PATH)
    work_queue = pd.read_csv(WORK_QUEUE_PATH)
    inbound = pd.read_csv(INBOUND_PATH)

    summary = (
        missing.groupby(["first_big_west_season", "source_level", "reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["first_big_west_season", "source_level", "reason"])
    )
    summary.to_csv(SUMMARY_PATH, index=False)

    historical = missing[missing["first_big_west_season"].map(completed_season)].copy()
    historical = historical.merge(
        work_queue[
            [
                "player_slug",
                "destination_school",
                "first_big_west_season",
                "priority",
                "expected_source_season",
                "recommended_next_step",
                "current_missing_reason",
            ]
        ],
        on=["player_slug", "destination_school", "first_big_west_season"],
        how="left",
    )
    historical["collection_bucket"] = "needs_outcome_stats"
    historical.loc[historical["missing_source_stats"], "collection_bucket"] = "needs_source_stats"
    historical.loc[
        historical["missing_source_stats"] & historical["missing_outcome_stats"],
        "collection_bucket",
    ] = "needs_source_and_outcome_stats"
    historical["priority"] = historical["priority"].fillna(3).astype(int)
    historical = historical.sort_values(
        ["priority", "collection_bucket", "first_big_west_season", "source_level", "player_name"]
    )
    historical.to_csv(HISTORICAL_ROWS_NEEDED_PATH, index=False)

    massey_rows = []
    for row in inbound.to_dict("records"):
        massey_rows.append(
            {
                "season": previous_season(row["first_big_west_season"]),
                "conference": row["source_conference"],
                "level": row["source_level"],
                "needed_for": "source_conf_power",
            }
        )
        massey_rows.append(
            {
                "season": row["first_big_west_season"],
                "conference": row["destination_conference"],
                "level": row["destination_level"],
                "needed_for": "destination_conf_power",
            }
        )
    massey = pd.DataFrame(massey_rows)
    massey = massey[massey["conference"].fillna("").astype(str).str.strip() != ""].copy()
    massey["conference_key"] = massey["conference"].map(normalize)
    massey = (
        massey.drop_duplicates(["season", "conference_key", "needed_for"])
        .drop(columns=["conference_key"])
        .sort_values(["season", "level", "conference", "needed_for"])
    )
    massey.to_csv(MASSEY_NEEDED_PATH, index=False)
    massey[["season", "conference", "level"]].drop_duplicates(["season", "conference"]).assign(
        power=""
    ).to_csv(MASSEY_TEMPLATE_PATH, index=False)

    barttorvik_columns = [
        "player_name",
        "player_slug",
        "destination_school",
        "destination_school_slug",
        "first_big_west_season",
        "big_west_porpag",
        "barttorvik_url",
    ]
    barttorvik = modeling[barttorvik_columns[:-2]].copy()
    barttorvik["big_west_porpag"] = ""
    barttorvik["barttorvik_url"] = ""
    barttorvik.to_csv(BARTTORVIK_NEEDED_PATH, index=False)
    barttorvik.head(0).to_csv(BARTTORVIK_TEMPLATE_PATH, index=False)

    print(f"Wrote {len(summary)} summary rows to {SUMMARY_PATH}")
    print(f"Wrote {len(historical)} historical rows to {HISTORICAL_ROWS_NEEDED_PATH}")
    print(f"Wrote {len(massey)} Massey needs to {MASSEY_NEEDED_PATH}")
    print(f"Wrote Massey template to {MASSEY_TEMPLATE_PATH}")
    print(f"Wrote {len(barttorvik)} BartTorvik rows to {BARTTORVIK_NEEDED_PATH}")
    print(f"Wrote BartTorvik template to {BARTTORVIK_TEMPLATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
