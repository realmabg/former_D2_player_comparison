#!/usr/bin/env python3
"""Build WCC D2/non-major transfer modeling rows."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from build_wcc_d1_transfer_outcomes import (
    MODELING_COLUMNS,
    choose_row,
    modeling_row as d1_modeling_row,
    outcome_row,
    profile_slug,
)
from build_wcc_sports_reference_roster_diff_audit import profile_cache_path
from scrape_phase1_d1_outcomes import parse_table_rows


CANDIDATES_PATH = Path("data/wcc_roster_diff_possible_transfers.csv")
SOURCE_PATH = Path("data/wcc_d2_source_stats.csv")
OUTPUT_PATH = Path("data/wcc_d2_transfer_modeling_dataset.csv")
OUTCOMES_PATH = Path("data/wcc_d2_transfer_outcomes_found.csv")
MISSING_PATH = Path("data/wcc_d2_transfer_modeling_missing.csv")

OUTCOME_COLUMNS = [
    "first_wcc_season",
    "destination_school",
    "player_name",
    "sr_season",
    "sr_team",
    "sr_conf",
    "class",
    "position",
    "games",
    "games_started",
    "mpg",
    "minutes",
    "minutes_share",
    "ppg",
    "rpg",
    "apg",
    "spg",
    "bpg",
    "topg",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "efg_pct",
    "ts_pct",
    "three_rate",
    "ft_rate",
    "per",
    "ts_pct_advanced",
    "usg_pct",
    "ows",
    "dws",
    "ws",
    "ws_per_40",
    "bpm",
    "source_url",
]

MISSING_COLUMNS = [
    "first_wcc_season",
    "destination_school",
    "player_name",
    "sports_reference_player_url",
    "missing_source_stats",
    "missing_outcome_stats",
    "reason",
]


def key_name_season(row: dict[str, str], name_col: str, season_col: str) -> tuple[str, str]:
    return (row[name_col].lower().replace(".", "").replace(",", "").strip(), row[season_col])


def d2_candidate_rows() -> list[dict[str, str]]:
    with CANDIDATES_PATH.open(newline="", encoding="utf-8") as file:
        return [row for row in csv.DictReader(file) if row["profile_prior_level_guess"] == "D2"]


def d2_source_lookup() -> dict[tuple[str, str], dict[str, str]]:
    with SOURCE_PATH.open(newline="", encoding="utf-8") as file:
        return {
            key_name_season(row, "Player Name", "first_d1_season"): row
            for row in csv.DictReader(file)
        }


def source_enriched_candidate(candidate: dict[str, str], source: dict[str, str]) -> dict[str, str]:
    row = candidate.copy()
    row.update(
        {
            "source_school": source["Team"],
            "source_conference": source["Conference"],
            "source_level": "D2",
            "source_season": source["Season"],
            "source_url": source["source_url"],
            "games": source["GP"],
            "mpg": source["MPG"],
            "ppg": source["PPG"],
            "rpg": source["RPG"],
            "apg": source["APG"],
            "spg": source["SPG"],
            "bpg": source["BPG"],
            "topg": source["TOPG"],
            "fg_pct": source["FG%"],
            "fg3_pct": source["3PT%"],
            "ft_pct": source["FT%"],
            "efg_pct": source["eFG"],
        }
    )
    return row


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    sources = d2_source_lookup()
    outcomes: list[dict[str, object]] = []
    modeling_rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []

    for candidate in d2_candidate_rows():
        source = sources.get(key_name_season(candidate, "player_name", "first_wcc_season"))
        if not source:
            missing.append(
                {
                    "first_wcc_season": candidate["first_wcc_season"],
                    "destination_school": candidate["destination_school"],
                    "player_name": candidate["player_name"],
                    "sports_reference_player_url": candidate["sports_reference_player_url"],
                    "missing_source_stats": "TRUE",
                    "missing_outcome_stats": "FALSE",
                    "reason": "missing_d2_source_stats",
                }
            )
            continue
        path, status = profile_cache_path(
            candidate["sports_reference_player_url"],
            profile_slug(candidate["sports_reference_player_url"]),
        )
        if not path or status != "cached":
            missing.append(
                {
                    "first_wcc_season": candidate["first_wcc_season"],
                    "destination_school": candidate["destination_school"],
                    "player_name": candidate["player_name"],
                    "sports_reference_player_url": candidate["sports_reference_player_url"],
                    "missing_source_stats": "FALSE",
                    "missing_outcome_stats": "TRUE",
                    "reason": "profile_not_cached",
                }
            )
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        per_game = choose_row(
            parse_table_rows(html, "players_per_game"),
            candidate["first_wcc_season"],
            candidate["destination_school"],
        )
        advanced = choose_row(
            parse_table_rows(html, "players_advanced"),
            candidate["first_wcc_season"],
            candidate["destination_school"],
        )
        if not per_game:
            missing.append(
                {
                    "first_wcc_season": candidate["first_wcc_season"],
                    "destination_school": candidate["destination_school"],
                    "player_name": candidate["player_name"],
                    "sports_reference_player_url": candidate["sports_reference_player_url"],
                    "missing_source_stats": "FALSE",
                    "missing_outcome_stats": "TRUE",
                    "reason": "wcc_outcome_row_not_found_on_profile",
                }
            )
            continue
        enriched = source_enriched_candidate(candidate, source)
        outcome = outcome_row(enriched, per_game, advanced)
        row = d1_modeling_row(enriched, outcome)
        row["source_level"] = "D2"
        outcomes.append(outcome)
        modeling_rows.append(row)

    write_csv(OUTCOMES_PATH, OUTCOME_COLUMNS, outcomes)
    write_csv(OUTPUT_PATH, MODELING_COLUMNS, modeling_rows)
    write_csv(MISSING_PATH, MISSING_COLUMNS, missing)

    print(f"Wrote {len(outcomes)} outcome rows to {OUTCOMES_PATH}")
    print(f"Wrote {len(modeling_rows)} modeling rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
