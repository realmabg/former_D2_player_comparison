#!/usr/bin/env python3
"""Match EvanMiya BPR player ratings to the target-conference transfer dataset."""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


TRANSFER_PATH = Path("data/target_conference_transfer_modeling_dataset.csv")
EVANMIYA_PATH = Path("data/evanmiya_player_ratings_2020_21_to_2025_26.csv")
OUTPUT_PATH = Path("data/target_conference_transfer_modeling_with_evanmiya.csv")
MISSING_PATH = Path("data/target_conference_evanmiya_missing_matches.csv")
SUMMARY_PATH = Path("data/target_conference_evanmiya_match_summary.csv")


EVANMIYA_COLUMNS = [
    "rank",
    "obpr",
    "dbpr",
    "bpr",
    "poss",
    "box_obpr",
    "box_dbpr",
    "box_bpr",
    "adj_team_off_eff",
    "adj_team_def_eff",
    "adj_team_eff_margin",
    "plus_minus",
]


TEAM_ALIASES = {
    "brigham young": "byu",
    "detroit mercy": "detroit",
    "gcu": "grand canyon",
    "little rock": "arkansas little rock",
    "louisiana state": "lsu",
    "loyola md": "loyola maryland",
    "mcneese": "mcneese state",
    "southern california": "usc",
}

NAME_ALIASES = {
    "desean allen eikens": "de sean allen eikens",
    "joshua ward": "josh ward",
    "josh ogarro": "joshua ogarro",
    "josh o garro": "joshua o garro",
    "john square": "john mikey square",
    "kieves turner": "deuce turner",
}

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_team(value: object) -> str:
    text = normalize_text(value)
    return TEAM_ALIASES.get(text, text)


def normalize_player_name(value: object, *, drop_suffix: bool = False) -> str:
    text = normalize_text(value)
    parts = text.split()
    collapsed: list[str] = []
    index = 0
    while index < len(parts):
        if len(parts[index]) == 1:
            start = index
            while index < len(parts) and len(parts[index]) == 1:
                index += 1
            collapsed.append("".join(parts[start:index]))
        else:
            collapsed.append(parts[index])
            index += 1
    text = " ".join(collapsed)
    if drop_suffix:
        parts = [part for part in text.split() if part not in SUFFIXES]
        text = " ".join(parts)
    text = NAME_ALIASES.get(text, text)
    return text


def load_evanmiya() -> tuple[
    dict[tuple[str, str, str], dict[str, str]],
    dict[tuple[str, str, str], dict[str, str]],
    dict[tuple[str, str], list[dict[str, str]]],
]:
    exact: dict[tuple[str, str, str], dict[str, str]] = {}
    no_suffix: dict[tuple[str, str, str], dict[str, str]] = {}
    by_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with EVANMIYA_PATH.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            season = row["year"]
            player = normalize_player_name(row["player_name"])
            player_no_suffix = normalize_player_name(row["player_name"], drop_suffix=True)
            team = normalize_team(row["team"])
            exact[(season, player, team)] = row
            no_suffix[(season, player_no_suffix, team)] = row
            by_name[(season, player_no_suffix)].append(row)
    return exact, no_suffix, by_name


def find_rating(
    *,
    season: str,
    player_name: str,
    team: str,
    exact: dict[tuple[str, str, str], dict[str, str]],
    no_suffix: dict[tuple[str, str, str], dict[str, str]],
    by_name: dict[tuple[str, str], list[dict[str, str]]],
) -> tuple[dict[str, str] | None, str]:
    player = normalize_player_name(player_name)
    player_no_suffix = normalize_player_name(player_name, drop_suffix=True)
    team_norm = normalize_team(team)

    key = (season, player, team_norm)
    if key in exact:
        return exact[key], "exact_name_team"

    key = (season, player_no_suffix, team_norm)
    if key in no_suffix:
        return no_suffix[key], "suffix_insensitive_name_team"

    candidates = by_name.get((season, player_no_suffix), [])
    if len(candidates) == 1:
        return candidates[0], "unique_name_year"

    return None, "missing"


def add_rating(out: dict[str, str], prefix: str, rating: dict[str, str] | None, method: str) -> None:
    out[f"{prefix}_evanmiya_match_method"] = method
    out[f"{prefix}_evanmiya_player_name"] = rating.get("player_name", "") if rating else ""
    out[f"{prefix}_evanmiya_team"] = rating.get("team", "") if rating else ""
    for column in EVANMIYA_COLUMNS:
        out[f"{prefix}_evanmiya_{column}"] = rating.get(column, "") if rating else ""


def main() -> int:
    exact, no_suffix, by_name = load_evanmiya()
    rows: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    summary = Counter()

    with TRANSFER_PATH.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            out = dict(row)

            if row["source_level"] == "D1":
                rating, method = find_rating(
                    season=row["source_season"],
                    player_name=row["player_name"],
                    team=row["source_school"],
                    exact=exact,
                    no_suffix=no_suffix,
                    by_name=by_name,
                )
                summary[f"source_{method}"] += 1
                if rating is None:
                    missing.append(
                        {
                            "side": "source",
                            "player_name": row["player_name"],
                            "season": row["source_season"],
                            "team": row["source_school"],
                            "source_level": row["source_level"],
                            "target_conference": row["target_conference"],
                            "destination_school": row["destination_school"],
                        }
                    )
                add_rating(out, "source", rating, method)
            else:
                summary["source_not_d1"] += 1
                add_rating(out, "source", None, "not_d1")

            rating, method = find_rating(
                season=row["first_target_season"],
                player_name=row["player_name"],
                team=row["destination_school"],
                exact=exact,
                no_suffix=no_suffix,
                by_name=by_name,
            )
            summary[f"target_{method}"] += 1
            if rating is None:
                missing.append(
                    {
                        "side": "target",
                        "player_name": row["player_name"],
                        "season": row["first_target_season"],
                        "team": row["destination_school"],
                        "source_level": row["source_level"],
                        "target_conference": row["target_conference"],
                        "destination_school": row["destination_school"],
                    }
                )
            add_rating(out, "target", rating, method)
            rows.append(out)

    fieldnames = list(rows[0].keys()) if rows else []
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "side",
            "player_name",
            "season",
            "team",
            "source_level",
            "target_conference",
            "destination_school",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(missing)

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["metric", "count"])
        writer.writeheader()
        for metric, count in sorted(summary.items()):
            writer.writerow({"metric": metric, "count": count})

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing match rows to {MISSING_PATH}")
    print(f"Wrote match summary to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
