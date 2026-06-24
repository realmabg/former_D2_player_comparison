#!/usr/bin/env python3
"""Build D1-to-target-conference modeling rows from roster-diff candidates."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from build_target_conference_sports_reference_roster_diff_audit import profile_cache_path, same_team
from scrape_phase1_d1_outcomes import parse_table_rows
from target_conference_configs import TEAMS_BY_CONFERENCE_SEASON


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

OUTCOME_COLUMNS = [
    "target_conference",
    "first_target_season",
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
    "target_conference",
    "first_target_season",
    "destination_school",
    "player_name",
    "sports_reference_player_url",
    "reason",
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
        "target_conference": candidate["target_conference"],
        "first_target_season": candidate["first_target_season"],
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
        "target_conference": candidate["target_conference"],
        "player_name": candidate["player_name"],
        "player_key": candidate["player_key"],
        "source_school": candidate["source_school"],
        "source_conference": candidate["source_conference"],
        "source_level": "D1",
        "destination_school": candidate["destination_school"],
        "first_target_season": candidate["first_target_season"],
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


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conference", choices=sorted(TEAMS_BY_CONFERENCE_SEASON), required=True)
    args = parser.parse_args()

    input_path = Path(f"data/{args.conference}_roster_diff_d1_source_stats_found.csv")
    candidates = list(csv.DictReader(input_path.open(newline="", encoding="utf-8"))) if input_path.exists() else []
    outcomes: list[dict[str, object]] = []
    modeling_rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []

    for candidate in candidates:
        path, status = profile_cache_path(
            candidate["sports_reference_player_url"],
            profile_slug(candidate["sports_reference_player_url"]),
        )
        if not path or status != "cached":
            missing.append(
                {
                    "target_conference": candidate["target_conference"],
                    "first_target_season": candidate["first_target_season"],
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
            candidate["first_target_season"],
            candidate["destination_school"],
        )
        advanced = choose_row(
            parse_table_rows(html, "players_advanced"),
            candidate["first_target_season"],
            candidate["destination_school"],
        )
        if not per_game:
            missing.append(
                {
                    "target_conference": candidate["target_conference"],
                    "first_target_season": candidate["first_target_season"],
                    "destination_school": candidate["destination_school"],
                    "player_name": candidate["player_name"],
                    "sports_reference_player_url": candidate["sports_reference_player_url"],
                    "reason": "target_outcome_row_not_found_on_profile",
                }
            )
            continue
        row = outcome_row(candidate, per_game, advanced)
        outcomes.append(row)
        modeling_rows.append(modeling_row(candidate, row))

    outcome_path = Path(f"data/{args.conference}_d1_transfer_outcomes_found.csv")
    modeling_path = Path(f"data/{args.conference}_d1_transfer_modeling_dataset.csv")
    missing_path = Path(f"data/{args.conference}_d1_transfer_outcomes_missing.csv")
    summary_path = Path(f"data/{args.conference}_d1_transfer_outcome_summary.csv")
    write_csv(outcome_path, OUTCOME_COLUMNS, outcomes)
    write_csv(modeling_path, MODELING_COLUMNS, modeling_rows)
    write_csv(missing_path, MISSING_COLUMNS, missing)
    write_csv(
        summary_path,
        ["bucket", "count"],
        [
            {"bucket": "d1_candidates", "count": len(candidates)},
            {"bucket": "outcomes_found", "count": len(outcomes)},
            {"bucket": "outcomes_missing", "count": len(missing)},
        ],
    )

    print(f"Wrote {len(outcomes)} outcome rows to {outcome_path}")
    print(f"Wrote {len(modeling_rows)} modeling rows to {modeling_path}")
    print(f"Wrote {len(missing)} missing rows to {missing_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
