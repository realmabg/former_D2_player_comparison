#!/usr/bin/env python3
"""Combine Big West and WCC transfer rows into one common-box modeling file."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


BIG_WEST_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
WCC_PATH = Path("data/wcc_d1_transfer_modeling_dataset.csv")
WCC_D2_PATH = Path("data/wcc_d2_transfer_modeling_dataset.csv")
EXTRA_D1_PATHS = [
    Path("data/mwc_d1_transfer_modeling_dataset.csv"),
    Path("data/a10_d1_transfer_modeling_dataset.csv"),
    Path("data/aac_d1_transfer_modeling_dataset.csv"),
    Path("data/mvc_d1_transfer_modeling_dataset.csv"),
]
OUTPUT_PATH = Path("data/target_conference_transfer_modeling_dataset.csv")
SUMMARY_PATH = Path("data/target_conference_transfer_modeling_summary.csv")

OUTPUT_COLUMNS = [
    "target_conference",
    "player_name",
    "player_key",
    "source_school",
    "source_conference",
    "source_level",
    "destination_school",
    "first_target_season",
    "source_season",
    "position",
    "height",
    "weight",
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
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
    "target_games",
    "target_games_started",
    "target_mpg",
    "target_minutes",
    "target_minutes_share",
    "target_ppg",
    "target_rpg",
    "target_apg",
    "target_spg",
    "target_bpg",
    "target_topg",
    "target_ts_pct",
    "target_per",
    "target_usg_pct",
    "target_ws",
    "target_ws_per_40",
    "target_bpm",
    "source_url",
    "outcome_url",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def big_west_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "target_conference": "Big West",
        "player_name": row["player_name"],
        "player_key": row["player_slug"],
        "source_school": row["source_school"],
        "source_conference": row["source_conference"],
        "source_level": row["source_level"],
        "destination_school": row["destination_school"],
        "first_target_season": row["first_big_west_season"],
        "source_season": row["source_season"],
        "position": row["position"],
        "height": row["height_in"],
        "weight": row["weight_lbs"],
        "source_games": row["source_games"],
        "source_mpg": row["source_mpg"],
        "source_minutes_share": row["source_minutes_share"],
        "source_ppg": row["source_ppg"],
        "source_rpg": row["source_rpg"],
        "source_apg": row["source_apg"],
        "source_spg": row["source_spg"],
        "source_bpg": row["source_bpg"],
        "source_topg": row["source_topg"],
        "source_fg_pct": row["source_fg_pct"],
        "source_fg3_pct": row["source_fg3_pct"],
        "source_ft_pct": row["source_ft_pct"],
        "source_efg_pct": row["source_efg_pct"],
        "source_pts_per_40": row["source_pts_per_40"],
        "source_reb_per_40": row["source_reb_per_40"],
        "source_ast_per_40": row["source_ast_per_40"],
        "source_stl_per_40": row["source_stl_per_40"],
        "source_blk_per_40": row["source_blk_per_40"],
        "source_tov_per_40": row["source_tov_per_40"],
        "target_games": row["big_west_games"],
        "target_games_started": row["big_west_games_started"],
        "target_mpg": row["big_west_mpg"],
        "target_minutes": row["big_west_minutes"],
        "target_minutes_share": row["big_west_minutes_share"],
        "target_ppg": row["big_west_ppg"],
        "target_rpg": row["big_west_rpg"],
        "target_apg": row["big_west_apg"],
        "target_spg": row["big_west_spg"],
        "target_bpg": row["big_west_bpg"],
        "target_topg": row["big_west_topg"],
        "target_ts_pct": row["big_west_ts_pct"],
        "target_per": row["big_west_per"],
        "target_usg_pct": row["big_west_usg_pct"],
        "target_ws": row["big_west_ws"],
        "target_ws_per_40": row["big_west_ws_per_40"],
        "target_bpm": row["big_west_bpm"],
        "source_url": row["source_url"],
        "outcome_url": row["outcome_url"],
    }


def main() -> int:
    big_west = [big_west_row(row) for row in read_rows(BIG_WEST_PATH)]
    extra_d1 = []
    for path in EXTRA_D1_PATHS:
        extra_d1.extend(read_rows(path))
    wcc = read_rows(WCC_PATH) + read_rows(WCC_D2_PATH)
    rows = big_west + wcc + extra_d1

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["target_conference"], row["source_level"])
        counts[key] = counts.get(key, 0) + 1
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["target_conference", "source_level", "count"])
        writer.writeheader()
        for (conference, level), count in sorted(counts.items()):
            writer.writerow({"target_conference": conference, "source_level": level, "count": count})

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
