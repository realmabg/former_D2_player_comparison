#!/usr/bin/env python3
"""Match target-conference modeling rows to local BartTorvik/TRank exports."""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/target_conference_transfer_modeling_big_west_schema.csv")
BART_DIR = Path("Bart data")
OUTPUT_PATH = Path("data/target_conference_barttorvik_outcomes.csv")
MISSING_PATH = Path("data/target_conference_barttorvik_outcomes_missing.csv")

PLAYER_COLUMN = 0
TEAM_COLUMN = 1
PORPAG_COLUMN = 28
YEAR_COLUMN = 31
PLAYER_ID_COLUMN = 32
BPM_COLUMN = 50
OBPM_COLUMN = 51
DBPM_COLUMN = 52

TEAM_ALIASES = {
    "byu": "brigham young",
    "cal poly": "cal poly",
    "cal state bakersfield": "cal st bakersfield",
    "cal state fullerton": "cal st fullerton",
    "cal state northridge": "cal st northridge",
    "central florida": "ucf",
    "long beach state": "long beach st",
    "loyola ca": "loyola marymount",
    "saint mary s": "saint mary s",
    "saint mary s ca": "saint mary s",
    "saint marys ca": "saint mary s",
    "san jose state": "san jose st",
    "southern methodist": "smu",
    "texas san antonio": "utsa",
    "uc san diego": "uc san diego",
    "uc santa barbara": "uc santa barbara",
    "unlv": "unlv",
    "virginia commonwealth": "vcu",
    "washington state": "washington st",
}

PLAYER_ALIASES = {
    "a j george": {"aj george"},
    "b j kolly": {"bj kolly"},
    "desean allen eikens": {"de sean allen eikens"},
    "dominic brewton": {"dj brewton"},
    "kieves turner": {"deuce turner"},
    "t j wainwright": {"tj wainwright"},
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return TEAM_ALIASES.get(text, text)


def player_names(player_name: str) -> set[str]:
    base = normalize(player_name)
    return {base, *PLAYER_ALIASES.get(base, set())}


def season_end_year(season: str) -> int:
    return int(str(season).split("-", 1)[0]) + 1


def load_bart_years() -> dict[int, pd.DataFrame]:
    frames = {}
    for path in sorted(BART_DIR.glob("trank_data_*.csv")):
        match = re.search(r"(\d{4})", path.stem)
        if not match:
            continue
        year = int(match.group(1))
        frame = pd.read_csv(path, header=None)
        frame["_source_file"] = str(path)
        frame["_player_norm"] = frame[PLAYER_COLUMN].map(normalize)
        frame["_team_norm"] = frame[TEAM_COLUMN].map(normalize)
        frames[year] = frame
    return frames


def match_row(row: dict[str, object], frames: dict[int, pd.DataFrame]) -> tuple[pd.Series | None, str]:
    year = season_end_year(str(row["first_big_west_season"]))
    frame = frames.get(year)
    if frame is None:
        return None, "missing_bart_year_file"
    names = player_names(str(row["player_name"]))
    team = normalize(row["destination_school"])
    matches = frame[frame["_player_norm"].isin(names) & (frame["_team_norm"] == team)]
    if len(matches) == 1:
        return matches.iloc[0], "matched_player_and_team"
    if len(matches) > 1:
        return matches.sort_values(PORPAG_COLUMN, ascending=False).iloc[0], "multiple_matches_used_highest_porpag"
    name_only = frame[frame["_player_norm"].isin(names)]
    if len(name_only) == 1:
        return name_only.iloc[0], "matched_player_name_only"
    return None, "no_matching_player_team_row"


def main() -> int:
    rows = pd.read_csv(INPUT_PATH).to_dict("records")
    frames = load_bart_years()
    found: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    for row in rows:
        match, status = match_row(row, frames)
        base = {
            "target_conference": row["target_conference"],
            "player_name": row["player_name"],
            "player_slug": row["player_slug"],
            "destination_school": row["destination_school"],
            "destination_school_slug": row["destination_school_slug"],
            "first_big_west_season": row["first_big_west_season"],
        }
        if match is None:
            missing.append({**base, "reason": status})
            continue
        year = int(match[YEAR_COLUMN])
        player_id = str(match[PLAYER_ID_COLUMN])
        found.append(
            {
                **base,
                "big_west_porpag": float(match[PORPAG_COLUMN]),
                "barttorvik_bpm": float(match[BPM_COLUMN]) if pd.notna(match[BPM_COLUMN]) else "",
                "barttorvik_obpm": float(match[OBPM_COLUMN]) if pd.notna(match[OBPM_COLUMN]) else "",
                "barttorvik_dbpm": float(match[DBPM_COLUMN]) if pd.notna(match[DBPM_COLUMN]) else "",
                "barttorvik_url": f"https://barttorvik.com/playerstat.php?year={year}&p={player_id}",
                "barttorvik_player_name": match[PLAYER_COLUMN],
                "barttorvik_team": match[TEAM_COLUMN],
                "match_status": status,
                "source_file": match["_source_file"],
            }
        )

    fieldnames = [
        "target_conference",
        "player_name",
        "player_slug",
        "destination_school",
        "destination_school_slug",
        "first_big_west_season",
        "big_west_porpag",
        "barttorvik_bpm",
        "barttorvik_obpm",
        "barttorvik_dbpm",
        "barttorvik_url",
        "barttorvik_player_name",
        "barttorvik_team",
        "match_status",
        "source_file",
    ]
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(found)
    with MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["target_conference", "player_name", "player_slug", "destination_school", "destination_school_slug", "first_big_west_season", "reason"])
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(found)} BartTorvik outcome rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
