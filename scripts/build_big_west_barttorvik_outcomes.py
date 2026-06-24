#!/usr/bin/env python3
"""Build Big West PORPAG outcomes from local BartTorvik/TRank exports."""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd

NEEDED_PATH = Path("data/big_west_barttorvik_needed.csv")
BART_DIR = Path("Bart data")
OUTPUT_PATH = Path("data/big_west_barttorvik_outcomes.csv")
MISSING_PATH = Path("data/big_west_barttorvik_outcomes_missing.csv")

PORPAG_COLUMN = 28
PLAYER_COLUMN = 0
TEAM_COLUMN = 1
YEAR_COLUMN = 31
PLAYER_ID_COLUMN = 32

TEAM_BY_DESTINATION_SLUG = {
    "cal-poly": "Cal Poly",
    "cal-state-bakersfield": "Cal St. Bakersfield",
    "cal-state-fullerton": "Cal St. Fullerton",
    "cal-state-northridge": "Cal St. Northridge",
    "hawaii": "Hawaii",
    "long-beach-state": "Long Beach St.",
    "uc-davis": "UC Davis",
    "uc-irvine": "UC Irvine",
    "uc-riverside": "UC Riverside",
    "uc-san-diego": "UC San Diego",
    "uc-santa-barbara": "UC Santa Barbara",
}

PLAYER_ALIASES = {
    "a j george": {"aj george"},
    "b j kolly": {"bj kolly"},
    "desean allen eikens": {"de sean allen eikens"},
    "dominic brewton": {"dj brewton"},
    "kieves turner": {"deuce turner"},
    "t j wainwright": {"tj wainwright"},
}

MANUAL_OVERRIDES = {
    ("joshua-ward", "cal-state-fullerton", "2025-26"): {
        "big_west_porpag": 2.1,
        "barttorvik_url": "https://barttorvik.com/playerstat.php?year=2026&p=Josh%20Ward&t=Cal%20St.%20Fullerton",
        "barttorvik_player_name": "Josh Ward",
        "barttorvik_team": "Cal St. Fullerton",
        "match_status": "manual_barttorvik_prpg",
        "source_file": "user_provided_barttorvik_row",
    },
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def player_names(player_name: str) -> set[str]:
    base = normalize(player_name)
    return {base, *PLAYER_ALIASES.get(base, set())}


def read_needed() -> list[dict[str, str]]:
    with NEEDED_PATH.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_bart_years() -> dict[int, pd.DataFrame]:
    frames = {}
    for path in sorted(BART_DIR.glob("trank_data_*.csv")):
        year_match = re.search(r"(\d{4})", path.stem)
        if not year_match:
            continue
        year = int(year_match.group(1))
        frame = pd.read_csv(path, header=None)
        frame["_source_file"] = str(path)
        frame["_player_norm"] = frame[PLAYER_COLUMN].map(normalize)
        frame["_team_norm"] = frame[TEAM_COLUMN].map(normalize)
        frames[year] = frame
    return frames


def match_row(needed: dict[str, str], frames: dict[int, pd.DataFrame]) -> tuple[pd.Series | None, str]:
    year = season_end_year(needed["first_big_west_season"])
    frame = frames.get(year)
    if frame is None:
        return None, "missing_bart_year_file"
    team = TEAM_BY_DESTINATION_SLUG.get(needed["destination_school_slug"], needed["destination_school"])
    names = player_names(needed["player_name"])
    matches = frame[
        frame["_player_norm"].isin(names)
        & (frame["_team_norm"] == normalize(team))
    ]
    if matches.empty:
        name_only = frame[frame["_player_norm"].isin(names)]
        if len(name_only) == 1:
            return name_only.iloc[0], "matched_player_name_only"
        return None, "no_matching_player_team_row"
    if len(matches) > 1:
        return matches.sort_values(PORPAG_COLUMN, ascending=False).iloc[0], "multiple_matches_used_highest_porpag"
    return matches.iloc[0], "matched_player_and_team"


def main() -> int:
    needed_rows = read_needed()
    frames = load_bart_years()
    rows = []
    missing = []

    for needed in needed_rows:
        override = MANUAL_OVERRIDES.get(
            (
                needed["player_slug"],
                needed["destination_school_slug"],
                needed["first_big_west_season"],
            )
        )
        if override:
            rows.append(
                {
                    "player_name": needed["player_name"],
                    "player_slug": needed["player_slug"],
                    "destination_school": needed["destination_school"],
                    "destination_school_slug": needed["destination_school_slug"],
                    "first_big_west_season": needed["first_big_west_season"],
                    **override,
                }
            )
            continue

        match, status = match_row(needed, frames)
        if match is None:
            missing.append(
                {
                    **needed,
                    "reason": status,
                }
            )
            continue
        year = int(match[YEAR_COLUMN])
        player_id = str(match[PLAYER_ID_COLUMN])
        rows.append(
            {
                "player_name": needed["player_name"],
                "player_slug": needed["player_slug"],
                "destination_school": needed["destination_school"],
                "destination_school_slug": needed["destination_school_slug"],
                "first_big_west_season": needed["first_big_west_season"],
                "big_west_porpag": float(match[PORPAG_COLUMN]),
                "barttorvik_url": f"https://barttorvik.com/playerstat.php?year={year}&p={player_id}",
                "barttorvik_player_name": match[PLAYER_COLUMN],
                "barttorvik_team": match[TEAM_COLUMN],
                "match_status": status,
                "source_file": match["_source_file"],
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "player_name",
                "player_slug",
                "destination_school",
                "destination_school_slug",
                "first_big_west_season",
                "big_west_porpag",
                "barttorvik_url",
                "barttorvik_player_name",
                "barttorvik_team",
                "match_status",
                "source_file",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        fieldnames = list(needed_rows[0]) + ["reason"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(rows)} BartTorvik outcome rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
