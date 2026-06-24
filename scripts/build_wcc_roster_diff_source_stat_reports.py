#!/usr/bin/env python3
"""Create source-stat work files from WCC roster-diff possible transfers."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from build_wcc_sports_reference_roster_diff_audit import profile_cache_path
from scrape_phase1_d1_outcomes import parse_table_rows


INPUT_PATH = Path("data/wcc_roster_diff_possible_transfers.csv")
D1_FOUND_PATH = Path("data/wcc_roster_diff_d1_source_stats_found.csv")
NEEDED_PATH = Path("data/wcc_roster_diff_source_stats_needed.csv")
SUMMARY_PATH = Path("data/wcc_roster_diff_source_stats_summary.csv")

D1_COLUMNS = [
    "first_wcc_season",
    "destination_school",
    "player_name",
    "source_school",
    "source_conference",
    "source_level",
    "source_season",
    "class",
    "position",
    "games",
    "mpg",
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
    "source_url",
    "candidate_action",
]

NEEDED_COLUMNS = [
    "first_wcc_season",
    "destination_school",
    "player_name",
    "source_school_or_label",
    "source_level",
    "source_season",
    "sports_reference_player_url",
    "candidate_action",
    "needed",
]


def profile_slug(url: str) -> str:
    return Path(url).stem if url else ""


def matching_prior_row(candidate: dict[str, str], rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if (
            row.get("year_id") == candidate["profile_prior_season"]
            and row.get("team_name_abbr") == candidate["profile_prior_school"]
        ):
            return row
    return {}


def d1_source_row(candidate: dict[str, str], stat: dict[str, str]) -> dict[str, str]:
    return {
        "first_wcc_season": candidate["first_wcc_season"],
        "destination_school": candidate["destination_school"],
        "player_name": candidate["player_name"],
        "source_school": stat.get("team_name_abbr", candidate["profile_prior_school"]),
        "source_conference": stat.get("conf_abbr", candidate["profile_prior_conf"]),
        "source_level": "D1",
        "source_season": stat.get("year_id", candidate["profile_prior_season"]),
        "class": stat.get("class", ""),
        "position": stat.get("pos", ""),
        "games": stat.get("games", ""),
        "mpg": stat.get("mp_per_g", ""),
        "ppg": stat.get("pts_per_g", ""),
        "rpg": stat.get("trb_per_g", ""),
        "apg": stat.get("ast_per_g", ""),
        "spg": stat.get("stl_per_g", ""),
        "bpg": stat.get("blk_per_g", ""),
        "topg": stat.get("tov_per_g", ""),
        "fg_pct": stat.get("fg_pct", ""),
        "fg3_pct": stat.get("fg3_pct", ""),
        "ft_pct": stat.get("ft_pct", ""),
        "efg_pct": stat.get("efg_pct", ""),
        "source_url": candidate["sports_reference_player_url"],
        "candidate_action": candidate["candidate_action"],
    }


def needed_row(candidate: dict[str, str], needed: str) -> dict[str, str]:
    return {
        "first_wcc_season": candidate["first_wcc_season"],
        "destination_school": candidate["destination_school"],
        "player_name": candidate["player_name"],
        "source_school_or_label": candidate["profile_prior_school"],
        "source_level": candidate["profile_prior_level_guess"],
        "source_season": candidate["profile_prior_season"],
        "sports_reference_player_url": candidate["sports_reference_player_url"],
        "candidate_action": candidate["candidate_action"],
        "needed": needed,
    }


def main() -> int:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing {INPUT_PATH}; run build_wcc_sports_reference_roster_diff_audit.py first")

    d1_found: list[dict[str, str]] = []
    needed: list[dict[str, str]] = []
    with INPUT_PATH.open(newline="", encoding="utf-8") as file:
        for candidate in csv.DictReader(file):
            level = candidate["profile_prior_level_guess"]
            if level == "D1":
                profile_path, status = profile_cache_path(
                    candidate["sports_reference_player_url"],
                    profile_slug(candidate["sports_reference_player_url"]),
                )
                if not profile_path or status != "cached":
                    needed.append(needed_row(candidate, "fetch Sports Reference profile, then parse D1 prior stat row"))
                    continue
                rows = parse_table_rows(profile_path.read_text(encoding="utf-8"), "players_per_game")
                stat = matching_prior_row(candidate, rows)
                if stat:
                    d1_found.append(d1_source_row(candidate, stat))
                else:
                    needed.append(needed_row(candidate, "manual check: cached profile did not expose matching D1 prior stat row"))
            elif level in {"D2", "JUCO"}:
                needed.append(needed_row(candidate, f"find {level} prior team and source-season stats from school/VC/official pages"))
            elif level == "NO_STATS":
                needed.append(needed_row(candidate, "exclude or check earlier playable season before adding"))
            else:
                needed.append(needed_row(candidate, "manual review prior school/level"))

    with D1_FOUND_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=D1_COLUMNS)
        writer.writeheader()
        writer.writerows(d1_found)

    with NEEDED_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NEEDED_COLUMNS)
        writer.writeheader()
        writer.writerows(needed)

    summary_counts: dict[tuple[str, str], int] = {}
    for row in d1_found:
        key = ("d1_source_stats_found", row["first_wcc_season"])
        summary_counts[key] = summary_counts.get(key, 0) + 1
    for row in needed:
        key = (row["needed"], row["first_wcc_season"])
        summary_counts[key] = summary_counts.get(key, 0) + 1
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["bucket", "first_wcc_season", "count"])
        writer.writeheader()
        for (bucket, season), count in sorted(summary_counts.items()):
            writer.writerow({"bucket": bucket, "first_wcc_season": season, "count": count})

    print(f"Wrote {len(d1_found)} D1 source stat rows to {D1_FOUND_PATH}")
    print(f"Wrote {len(needed)} source-stat work rows to {NEEDED_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
