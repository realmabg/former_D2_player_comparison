#!/usr/bin/env python3
"""Audit Big West transfer coverage from Sports Reference roster diffs."""

from __future__ import annotations

import csv
import html
import json
import re
import unicodedata
from pathlib import Path

from scrape_phase1_d1_outcomes import parse_table_rows


TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
MODELING_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
BIG_WEST_CACHE_DIR = Path("data/cache/sports_reference_big_west_schools")
PROFILE_CACHE_DIRS = [
    Path("data/cache/sports_reference_roster_diff_profiles"),
    Path("data/cache/sports_reference_review"),
    Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/sports_reference"),
]

OUTPUT_PATH = Path("data/big_west_sports_reference_roster_diff_audit.csv")
SUMMARY_PATH = Path("data/big_west_sports_reference_roster_diff_summary.csv")
POSSIBLE_MISSING_PATH = Path("data/big_west_roster_diff_possible_missing_transfers.csv")

TEAM_NAMES = {
    "cal-poly": "Cal Poly",
    "cal-state-bakersfield": "Cal State Bakersfield",
    "cal-state-fullerton": "Cal State Fullerton",
    "cal-state-northridge": "Cal State Northridge",
    "hawaii": "Hawaii",
    "long-beach-state": "Long Beach State",
    "uc-davis": "UC Davis",
    "uc-irvine": "UC Irvine",
    "uc-riverside": "UC Riverside",
    "uc-san-diego": "UC San Diego",
    "uc-santa-barbara": "UC Santa Barbara",
}

TEAM_ALIASES = {
    "california davis": "uc davis",
    "california irvine": "uc irvine",
    "california riverside": "uc riverside",
    "california san diego": "uc san diego",
    "california santa barbara": "uc santa barbara",
    "long beach state": "long beach state",
    "cal state fullerton": "cal state fullerton",
    "cal state northridge": "cal state northridge",
    "cal state bakersfield": "cal state bakersfield",
    "cal poly": "cal poly",
    "hawaii": "hawaii",
}

TRANSFER_LEVEL_HINTS = {
    "College": "JUCO",
    "Community College": "JUCO",
    "CC": "JUCO",
}

OUTPUT_COLUMNS = [
    "first_big_west_season",
    "destination_school",
    "destination_school_slug",
    "player_name",
    "player_key",
    "class",
    "position",
    "height",
    "weight",
    "sports_reference_player_url",
    "roster_cache_path",
    "previous_team_roster_status",
    "already_in_inbound_transfers",
    "already_in_inbound_same_program",
    "inbound_matched_first_big_west_season",
    "inbound_source_school",
    "inbound_source_level",
    "model_ready_playable",
    "model_source_level",
    "profile_cache_status",
    "profile_prior_season",
    "profile_prior_school",
    "profile_prior_conf",
    "profile_prior_level_guess",
    "profile_transfer_candidate",
    "candidate_action",
    "audit_status",
]


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(str(value)))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def season_from_end_year(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def previous_season(season: str) -> str:
    start = int(season.split("-", 1)[0])
    return f"{start - 1}-{str(start)[-2:]}"


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_roster_rows(page_html: str) -> list[dict[str, str]]:
    table_match = re.search(r'<table[^>]+id="roster".*?</table>', page_html, re.S)
    if not table_match:
        return []
    tbody_match = re.search(r"<tbody[^>]*>(.*?)(?:</tbody>|</table>)", table_match.group(0), re.S)
    if not tbody_match:
        return []

    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", tbody_match.group(1), re.S):
        cells: dict[str, str] = {}
        for cell in re.finditer(r"<(?P<tag>th|td)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>", row_html, re.S):
            attrs = cell.group("attrs")
            stat_match = re.search(r'data-stat="([^"]+)"', attrs)
            if not stat_match:
                continue
            stat = stat_match.group(1)
            body = cell.group("body")
            cells[stat] = strip_tags(body)
            if stat == "player":
                href_match = re.search(r'href="([^"]*/cbb/players/[^"]+)"', body)
                append_match = re.search(r'data-append-csv="([^"]+)"', attrs)
                cells["player_href"] = href_match.group(1) if href_match else ""
                cells["player_slug"] = append_match.group(1) if append_match else Path(cells["player_href"]).stem
        if cells.get("player"):
            rows.append(cells)
    return rows


def load_rosters() -> dict[tuple[str, str], dict[str, dict[str, str]]]:
    rosters: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
    for path in sorted(BIG_WEST_CACHE_DIR.glob("*.html")):
        match = re.match(r"(.+)_(\d{4})\.html$", path.name)
        if not match:
            continue
        school_slug, end_year_text = match.groups()
        season = season_from_end_year(int(end_year_text))
        roster_rows = parse_roster_rows(path.read_text(encoding="utf-8"))
        roster = {}
        for row in roster_rows:
            row["roster_cache_path"] = str(path)
            row["destination_school_slug"] = school_slug
            row["destination_school"] = TEAM_NAMES.get(school_slug, school_slug)
            row["first_big_west_season"] = season
            roster[normalize(row["player"])] = row
        rosters[(school_slug, season)] = roster
    return rosters


def profile_cache_path(player_href: str, player_slug: str) -> tuple[Path | None, str]:
    candidates = set()
    if player_slug:
        candidates.add(player_slug)
        candidates.add(re.sub(r"-\d+$", "", player_slug))
    if player_href:
        stem = Path(player_href).stem
        candidates.add(stem)
        candidates.add(re.sub(r"-\d+$", "", stem))
    for cache_dir in PROFILE_CACHE_DIRS:
        if not cache_dir.exists():
            continue
        for candidate in candidates:
            path = cache_dir / f"{candidate}.html"
            if path.exists():
                return path, "cached"
    return None, "not_cached"


def same_team(left: str, right: str) -> bool:
    left_norm = TEAM_ALIASES.get(normalize(left), normalize(left))
    right_norm = TEAM_ALIASES.get(normalize(right), normalize(right))
    return left_norm == right_norm


def infer_level(team: str, conf: str) -> str:
    text = f"{team} {conf}".lower()
    if "non-major" in text:
        return "D2"
    if "juco" in text:
        return "JUCO"
    if any(token in text for token in ["dnp", "redshirt", "injury", "manager"]):
        return "NO_STATS"
    for token, level in TRANSFER_LEVEL_HINTS.items():
        if token.lower() in text:
            return level
    if conf:
        return "D1"
    return ""


def profile_prior_school(path: Path, current_team: str, current_season: str) -> dict[str, str]:
    rows = parse_table_rows(path.read_text(encoding="utf-8"), "players_per_game")
    if not rows:
        return {}
    rows = [row for row in rows if row.get("year_id") and row.get("team_name_abbr")]
    current_indices = [
        index
        for index, row in enumerate(rows)
        if row.get("year_id") == current_season and same_team(row.get("team_name_abbr", ""), current_team)
    ]
    if current_indices:
        prior_rows = rows[: current_indices[0]]
    else:
        prior_rows = [row for row in rows if row.get("year_id", "") < current_season]
    if not prior_rows:
        return {}
    prior = prior_rows[-1]
    return {
        "profile_prior_season": prior.get("year_id", ""),
        "profile_prior_school": prior.get("team_name_abbr", ""),
        "profile_prior_conf": prior.get("conf_abbr", ""),
        "profile_prior_level_guess": infer_level(prior.get("team_name_abbr", ""), prior.get("conf_abbr", "")),
    }


def load_lookup(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    if not path.exists():
        return {}
    lookup = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            lookup[(normalize(row["player_name"]), row["destination_school_slug"], row["first_big_west_season"])] = row
    return lookup


def load_player_destination_lookup(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    lookup = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            lookup[(normalize(row["player_name"]), row["destination_school_slug"])] = row
    return lookup


def audit_status(row: dict[str, str]) -> str:
    if row["already_in_inbound_transfers"] == "TRUE":
        return "already_in_transfer_table"
    if row["already_in_inbound_same_program"] == "TRUE":
        return "already_in_transfer_table_different_first_season"
    if row["previous_team_roster_status"] == "no_previous_team_cache":
        return "needs_prior_roster_cache"
    if row["profile_cache_status"] != "cached":
        return "new_roster_player_needs_profile_check"
    if row["profile_transfer_candidate"] == "TRUE":
        return "possible_missing_transfer"
    return "new_roster_player_no_prior_school_on_cached_profile"


def candidate_action(row: dict[str, str]) -> str:
    if row["already_in_inbound_transfers"] == "TRUE":
        return "already_in_transfer_table"
    if row["already_in_inbound_same_program"] == "TRUE":
        return "already_in_transfer_table_check_lagged_outcome"
    level = row["profile_prior_level_guess"]
    if level == "D1":
        return "add_transfer_row_and_d1_source_stats"
    if level == "D2":
        return "add_transfer_row_and_find_d2_source_stats"
    if level == "JUCO":
        return "add_transfer_row_and_find_juco_source_stats"
    if level == "NO_STATS":
        return "do_not_use_as_source_stat_row_without_earlier_playable_season"
    if row["profile_cache_status"] != "cached":
        return "fetch_or_review_player_profile"
    return "manual_review_prior_school"


def main() -> int:
    rosters = load_rosters()
    transfers = load_lookup(TRANSFERS_PATH)
    transfers_by_player_destination = load_player_destination_lookup(TRANSFERS_PATH)
    modeling = load_lookup(MODELING_PATH)

    audit_rows: list[dict[str, str]] = []
    for (school_slug, season), roster in sorted(rosters.items()):
        prior = rosters.get((school_slug, previous_season(season)))
        for player_key, row in sorted(roster.items()):
            if prior is not None and player_key in prior:
                continue
            transfer_key = (player_key, school_slug, season)
            transfer = transfers.get(transfer_key, {})
            program_transfer = transfers_by_player_destination.get((player_key, school_slug), {})
            matched_transfer = transfer or program_transfer
            model_row = modeling.get(transfer_key, {})
            profile_path, profile_status = profile_cache_path(row.get("player_href", ""), row.get("player_slug", ""))
            prior_profile = (
                profile_prior_school(profile_path, row["destination_school"], season)
                if profile_path
                else {}
            )
            prior_school = prior_profile.get("profile_prior_school", "")
            profile_transfer_candidate = (
                "TRUE"
                if prior_school and not same_team(prior_school, row["destination_school"])
                else "FALSE"
            )
            out = {
                "first_big_west_season": season,
                "destination_school": row["destination_school"],
                "destination_school_slug": school_slug,
                "player_name": row.get("player", ""),
                "player_key": player_key,
                "class": row.get("class", ""),
                "position": row.get("pos", ""),
                "height": row.get("height", ""),
                "weight": row.get("weight", ""),
                "sports_reference_player_url": (
                    f"https://www.sports-reference.com{row.get('player_href', '')}"
                    if row.get("player_href", "").startswith("/")
                    else row.get("player_href", "")
                ),
                "roster_cache_path": row.get("roster_cache_path", ""),
                "previous_team_roster_status": "had_previous_team_cache" if prior is not None else "no_previous_team_cache",
                "already_in_inbound_transfers": "TRUE" if transfer else "FALSE",
                "already_in_inbound_same_program": "TRUE" if program_transfer else "FALSE",
                "inbound_matched_first_big_west_season": matched_transfer.get("first_big_west_season", ""),
                "inbound_source_school": matched_transfer.get("source_school", ""),
                "inbound_source_level": matched_transfer.get("source_level", ""),
                "model_ready_playable": "TRUE" if model_row else "FALSE",
                "model_source_level": model_row.get("source_level", ""),
                "profile_cache_status": profile_status,
                "profile_prior_season": prior_profile.get("profile_prior_season", ""),
                "profile_prior_school": prior_school,
                "profile_prior_conf": prior_profile.get("profile_prior_conf", ""),
                "profile_prior_level_guess": prior_profile.get("profile_prior_level_guess", ""),
                "profile_transfer_candidate": profile_transfer_candidate,
                "candidate_action": "",
                "audit_status": "",
            }
            out["candidate_action"] = candidate_action(out)
            out["audit_status"] = audit_status(out)
            audit_rows.append(out)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(audit_rows)

    summary_rows = []
    if audit_rows:
        counts: dict[tuple[str, str, str], int] = {}
        for row in audit_rows:
            summary_key = (row["first_big_west_season"], row["destination_school"], row["audit_status"])
            counts[summary_key] = counts.get(summary_key, 0) + 1
        summary_rows = [
            {
                "first_big_west_season": season,
                "destination_school": school,
                "audit_status": status,
                "count": count,
            }
            for (season, school, status), count in sorted(counts.items())
        ]
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        fieldnames = ["first_big_west_season", "destination_school", "audit_status", "count"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    possible_rows = [row for row in audit_rows if row["audit_status"] == "possible_missing_transfer"]
    possible_columns = [
        "first_big_west_season",
        "destination_school",
        "destination_school_slug",
        "player_name",
        "class",
        "position",
        "height",
        "weight",
        "profile_prior_season",
        "profile_prior_school",
        "profile_prior_conf",
        "profile_prior_level_guess",
        "candidate_action",
        "sports_reference_player_url",
        "already_in_inbound_transfers",
        "already_in_inbound_same_program",
        "inbound_matched_first_big_west_season",
        "inbound_source_school",
        "inbound_source_level",
        "model_ready_playable",
        "audit_status",
    ]
    with POSSIBLE_MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=possible_columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in possible_columns} for row in possible_rows])

    print(f"Wrote {len(audit_rows)} roster-diff audit rows to {OUTPUT_PATH}")
    print(f"Wrote {len(summary_rows)} summary rows to {SUMMARY_PATH}")
    print(f"Wrote {len(possible_rows)} possible missing transfer rows to {POSSIBLE_MISSING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
