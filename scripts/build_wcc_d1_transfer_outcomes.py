#!/usr/bin/env python3
"""Build WCC outcome rows for D1-to-WCC transfer candidates."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from build_wcc_sports_reference_roster_diff_audit import profile_cache_path, same_team
from scrape_phase1_d1_outcomes import parse_table_rows


INPUT_PATH = Path("data/wcc_d1_transfer_candidates_model_ready.csv")
POSSIBLE_TRANSFERS_PATH = Path("data/wcc_roster_diff_possible_transfers.csv")
OUTPUT_PATH = Path("data/wcc_d1_transfer_outcomes_found.csv")
MISSING_PATH = Path("data/wcc_d1_transfer_outcomes_missing.csv")
MODELING_PATH = Path("data/wcc_d1_transfer_modeling_dataset.csv")
SUMMARY_PATH = Path("data/wcc_d1_transfer_outcome_summary.csv")
EXCLUSIONS_PATH = Path("data/wcc_d1_transfer_exclusions.csv")

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
    "reason",
]

EXCLUSION_COLUMNS = [
    "first_wcc_season",
    "destination_school",
    "player_name",
    "sports_reference_player_url",
    "reason",
]

EXCLUDED_OUTCOME_REASONS = {
    ("Tanner Thomas", "Loyola Marymount", "2025-26"): "2025-26 redshirt",
    ("Dominic Capriotti", "Pacific", "2025-26"): "2025-26 redshirt",
    ("Jazz Gardner", "Saint Mary's", "2025-26"): "2025-26 redshirt",
    ("Isa Silva", "San Francisco", "2025-26"): "2025-26 injury",
    ("Chris Tadjo", "Santa Clara", "2025-26"): "2025-26 medical redshirt",
    ("Gehrig Normand", "Santa Clara", "2025-26"): "2025-26 medical redshirt",
}

MANUAL_D1_SOURCE_OVERRIDES = [
    {
        "player_name": "Vukasin Masic",
        "destination_school": "Portland",
        "first_wcc_season": "2023-24",
        "source_school": "Maine",
        "source_season": "2021-22",
    },
]

MODELING_COLUMNS = [
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


def number(value: object, fallback: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return fallback
        text = str(value).strip()
        if text.startswith("."):
            text = f"0{text}"
        if text.startswith("-."):
            text = text.replace("-.", "-0.", 1)
        return float(text)
    except (TypeError, ValueError):
        return fallback


def profile_slug(url: str) -> str:
    return Path(url).stem if url else ""


def choose_row(rows: list[dict[str, str]], season: str, school: str) -> dict[str, str]:
    for row in rows:
        if row.get("year_id") == season and same_team(row.get("team_name_abbr", ""), school):
            return row
    return {}


def outcome_row(candidate: dict[str, str], per_game: dict[str, str], advanced: dict[str, str]) -> dict[str, object]:
    games = number(per_game.get("games", ""))
    mpg = number(per_game.get("mp_per_g", ""))
    fga = number(per_game.get("fga_per_g", ""))
    fg3a = number(per_game.get("fg3a_per_g", ""))
    fta = number(per_game.get("fta_per_g", ""))
    pts = number(per_game.get("pts_per_g", ""))
    denominator = 2 * (fga + 0.44 * fta)
    return {
        "first_wcc_season": candidate["first_wcc_season"],
        "destination_school": candidate["destination_school"],
        "player_name": candidate["player_name"],
        "sr_season": per_game.get("year_id", ""),
        "sr_team": per_game.get("team_name_abbr", ""),
        "sr_conf": per_game.get("conf_abbr", ""),
        "class": per_game.get("class", ""),
        "position": per_game.get("pos", ""),
        "games": int(games),
        "games_started": int(number(per_game.get("games_started", ""))),
        "mpg": mpg,
        "minutes": games * mpg,
        "minutes_share": mpg / 40 if mpg else 0,
        "ppg": pts,
        "rpg": number(per_game.get("trb_per_g", "")),
        "apg": number(per_game.get("ast_per_g", "")),
        "spg": number(per_game.get("stl_per_g", "")),
        "bpg": number(per_game.get("blk_per_g", "")),
        "topg": number(per_game.get("tov_per_g", "")),
        "fg_pct": number(per_game.get("fg_pct", "")),
        "fg3_pct": number(per_game.get("fg3_pct", "")),
        "ft_pct": number(per_game.get("ft_pct", "")),
        "efg_pct": number(per_game.get("efg_pct", "")),
        "ts_pct": pts / denominator if denominator else 0,
        "three_rate": fg3a / fga if fga else 0,
        "ft_rate": fta / fga if fga else 0,
        "per": number(advanced.get("per", "")),
        "ts_pct_advanced": number(advanced.get("ts_pct", "")),
        "usg_pct": number(advanced.get("usg_pct", "")),
        "ows": number(advanced.get("ows", "")),
        "dws": number(advanced.get("dws", "")),
        "ws": number(advanced.get("ws", "")),
        "ws_per_40": number(advanced.get("ws_per_40", "")),
        "bpm": number(advanced.get("bpm", "")),
        "source_url": candidate["sports_reference_player_url"],
    }


def per_40(value: object, mpg: object) -> float:
    minutes = number(mpg)
    return number(value) * 40 / minutes if minutes else 0.0


def modeling_row(candidate: dict[str, str], outcome: dict[str, object]) -> dict[str, object]:
    return {
        "target_conference": "WCC",
        "player_name": candidate["player_name"],
        "player_key": candidate["player_key"],
        "source_school": candidate["source_school"],
        "source_conference": candidate["source_conference"],
        "source_level": "D1",
        "destination_school": candidate["destination_school"],
        "first_target_season": candidate["first_wcc_season"],
        "source_season": candidate["source_season"],
        "position": candidate["position"] or outcome["position"],
        "height": candidate["height"],
        "weight": candidate["weight"],
        "source_games": int(number(candidate["games"])),
        "source_mpg": number(candidate["mpg"]),
        "source_minutes_share": number(candidate["mpg"]) / 40 if number(candidate["mpg"]) else 0,
        "source_ppg": number(candidate["ppg"]),
        "source_rpg": number(candidate["rpg"]),
        "source_apg": number(candidate["apg"]),
        "source_spg": number(candidate["spg"]),
        "source_bpg": number(candidate["bpg"]),
        "source_topg": number(candidate["topg"]),
        "source_fg_pct": number(candidate["fg_pct"]),
        "source_fg3_pct": number(candidate["fg3_pct"]),
        "source_ft_pct": number(candidate["ft_pct"]),
        "source_efg_pct": number(candidate["efg_pct"]),
        "source_pts_per_40": per_40(candidate["ppg"], candidate["mpg"]),
        "source_reb_per_40": per_40(candidate["rpg"], candidate["mpg"]),
        "source_ast_per_40": per_40(candidate["apg"], candidate["mpg"]),
        "source_stl_per_40": per_40(candidate["spg"], candidate["mpg"]),
        "source_blk_per_40": per_40(candidate["bpg"], candidate["mpg"]),
        "source_tov_per_40": per_40(candidate["topg"], candidate["mpg"]),
        "target_games": outcome["games"],
        "target_games_started": outcome["games_started"],
        "target_mpg": outcome["mpg"],
        "target_minutes": outcome["minutes"],
        "target_minutes_share": outcome["minutes_share"],
        "target_ppg": outcome["ppg"],
        "target_rpg": outcome["rpg"],
        "target_apg": outcome["apg"],
        "target_spg": outcome["spg"],
        "target_bpg": outcome["bpg"],
        "target_topg": outcome["topg"],
        "target_ts_pct": outcome["ts_pct"],
        "target_per": outcome["per"],
        "target_usg_pct": outcome["usg_pct"],
        "target_ws": outcome["ws"],
        "target_ws_per_40": outcome["ws_per_40"],
        "target_bpm": outcome["bpm"],
        "source_url": candidate["source_url"],
        "outcome_url": outcome["source_url"],
    }


def manual_source_candidates() -> list[dict[str, str]]:
    if not POSSIBLE_TRANSFERS_PATH.exists():
        return []
    with POSSIBLE_TRANSFERS_PATH.open(newline="", encoding="utf-8") as file:
        possible = list(csv.DictReader(file))
    rows: list[dict[str, str]] = []
    for override in MANUAL_D1_SOURCE_OVERRIDES:
        base = next(
            (
                row
                for row in possible
                if row["player_name"] == override["player_name"]
                and row["destination_school"] == override["destination_school"]
                and row["first_wcc_season"] == override["first_wcc_season"]
            ),
            None,
        )
        if not base:
            continue
        path, status = profile_cache_path(
            base["sports_reference_player_url"],
            profile_slug(base["sports_reference_player_url"]),
        )
        if not path or status != "cached":
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        source = choose_row(
            parse_table_rows(html, "players_per_game"),
            override["source_season"],
            override["source_school"],
        )
        if not source:
            continue
        base = base.copy()
        base.update(
            {
                "source_school": source.get("team_name_abbr", override["source_school"]),
                "source_conference": source.get("conf_abbr", ""),
                "source_season": source.get("year_id", override["source_season"]),
                "games": source.get("games", ""),
                "mpg": source.get("mp_per_g", ""),
                "ppg": source.get("pts_per_g", ""),
                "rpg": source.get("trb_per_g", ""),
                "apg": source.get("ast_per_g", ""),
                "spg": source.get("stl_per_g", ""),
                "bpg": source.get("blk_per_g", ""),
                "topg": source.get("tov_per_g", ""),
                "fg_pct": source.get("fg_pct", ""),
                "fg3_pct": source.get("fg3_pct", ""),
                "ft_pct": source.get("ft_pct", ""),
                "efg_pct": source.get("efg_pct", ""),
                "source_url": base["sports_reference_player_url"],
                "model_recommendation": "include_d1_transfer_manual_prior_playable_season",
            }
        )
        rows.append(base)
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    candidates = list(csv.DictReader(INPUT_PATH.open(newline="", encoding="utf-8")))
    candidates.extend(manual_source_candidates())
    outcomes: list[dict[str, object]] = []
    modeling_rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []

    for candidate in candidates:
        exclusion_reason = EXCLUDED_OUTCOME_REASONS.get(
            (
                candidate["player_name"],
                candidate["destination_school"],
                candidate["first_wcc_season"],
            )
        )
        if exclusion_reason:
            exclusions.append(
                {
                    "first_wcc_season": candidate["first_wcc_season"],
                    "destination_school": candidate["destination_school"],
                    "player_name": candidate["player_name"],
                    "sports_reference_player_url": candidate["sports_reference_player_url"],
                    "reason": exclusion_reason,
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
                    "reason": "wcc_outcome_row_not_found_on_profile",
                }
            )
            continue
        row = outcome_row(candidate, per_game, advanced)
        outcomes.append(row)
        modeling_rows.append(modeling_row(candidate, row))

    write_csv(OUTPUT_PATH, OUTCOME_COLUMNS, outcomes)
    write_csv(MISSING_PATH, MISSING_COLUMNS, missing)
    write_csv(MODELING_PATH, MODELING_COLUMNS, modeling_rows)
    write_csv(EXCLUSIONS_PATH, EXCLUSION_COLUMNS, exclusions)
    summary = [
        {"bucket": "d1_candidates", "count": len(candidates)},
        {"bucket": "outcomes_found", "count": len(outcomes)},
        {"bucket": "outcomes_missing", "count": len(missing)},
        {"bucket": "excluded_no_outcome", "count": len(exclusions)},
    ]
    write_csv(SUMMARY_PATH, ["bucket", "count"], summary)

    print(f"Wrote {len(outcomes)} outcome rows to {OUTPUT_PATH}")
    print(f"Wrote {len(modeling_rows)} modeling rows to {MODELING_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    print(f"Wrote {len(exclusions)} exclusions to {EXCLUSIONS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
