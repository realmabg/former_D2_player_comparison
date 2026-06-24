#!/usr/bin/env python3
"""Discover inbound transfers for a configured target conference from roster/profile history."""

from __future__ import annotations

import argparse
import csv
import html
import re
import unicodedata
from pathlib import Path

from scrape_phase1_d1_outcomes import parse_table_rows
from target_conference_configs import (
    CONFERENCE_LABELS,
    TEAM_ALIASES,
    TEAM_NAMES,
    TEAMS_BY_CONFERENCE_SEASON,
    season_end_year,
)


PROFILE_CACHE_DIRS = [
    Path("data/cache/sports_reference_roster_diff_profiles"),
    Path("data/cache/sports_reference_d1_profile_audit"),
    Path("data/cache/sports_reference_d2_outcome_audit"),
    Path("data/cache/sports_reference_review"),
]

OUTPUT_COLUMNS = [
    "target_conference",
    "first_target_season",
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
    "profile_cache_status",
    "profile_prior_season",
    "profile_prior_school",
    "profile_prior_conf",
    "profile_prior_level_guess",
    "profile_transfer_candidate",
    "candidate_action",
    "audit_status",
]


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(str(value)))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def team_norm(value: object) -> str:
    norm = normalize(value)
    return TEAM_ALIASES.get(norm, norm)


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
    rows: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", tbody_match.group(1), re.S):
        cells: dict[str, str] = {}
        for cell in re.finditer(r"<(?P<tag>th|td)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>", row_html, re.S):
            stat_match = re.search(r'data-stat="([^"]+)"', cell.group("attrs"))
            if not stat_match:
                continue
            stat = stat_match.group(1)
            body = cell.group("body")
            cells[stat] = strip_tags(body)
            if stat == "player":
                href_match = re.search(r'href="([^"]*/cbb/players/[^"]+)"', body)
                append_match = re.search(r'data-append-csv="([^"]+)"', cell.group("attrs"))
                cells["player_href"] = href_match.group(1) if href_match else ""
                cells["player_slug"] = append_match.group(1) if append_match else Path(cells["player_href"]).stem
        if cells.get("player"):
            rows.append(cells)
    return rows


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
    return team_norm(left) == team_norm(right)


def infer_level(team: str, conf: str) -> str:
    text = f"{team} {conf}".lower()
    if "non-major" in text:
        return "D2"
    if "juco" in text:
        return "JUCO"
    if any(token in text for token in ["dnp", "redshirt", "injury"]):
        return "NO_STATS"
    if conf:
        return "D1"
    return ""


def profile_prior_school(path: Path, current_team: str, current_season: str) -> dict[str, str]:
    rows = parse_table_rows(path.read_text(encoding="utf-8", errors="ignore"), "players_per_game")
    rows = [row for row in rows if row.get("year_id") and row.get("team_name_abbr")]
    if not rows:
        return {}
    current_indices = [
        index
        for index, row in enumerate(rows)
        if row.get("year_id") == current_season and same_team(row.get("team_name_abbr", ""), current_team)
    ]
    prior_rows = rows[: current_indices[0]] if current_indices else [row for row in rows if row.get("year_id", "") < current_season]
    if not prior_rows:
        return {}
    prior = prior_rows[-1]
    return {
        "profile_prior_season": prior.get("year_id", ""),
        "profile_prior_school": prior.get("team_name_abbr", ""),
        "profile_prior_conf": prior.get("conf_abbr", ""),
        "profile_prior_level_guess": infer_level(prior.get("team_name_abbr", ""), prior.get("conf_abbr", "")),
    }


def load_rosters(conference: str) -> dict[tuple[str, str], dict[str, dict[str, str]]]:
    cache_dir = Path(f"data/cache/sports_reference_{conference}_schools")
    rosters: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
    for season, team_slugs in TEAMS_BY_CONFERENCE_SEASON[conference].items():
        year = season_end_year(season)
        for school_slug in team_slugs:
            path = cache_dir / f"{school_slug}_{year}.html"
            if not path.exists():
                continue
            roster_rows = parse_roster_rows(path.read_text(encoding="utf-8", errors="ignore"))
            roster = {}
            for row in roster_rows:
                row["roster_cache_path"] = str(path)
                row["destination_school_slug"] = school_slug
                row["destination_school"] = TEAM_NAMES.get(school_slug, school_slug)
                row["first_target_season"] = season
                roster[normalize(row["player"])] = row
            rosters[(school_slug, season)] = roster
    return rosters


def audit_status(row: dict[str, str]) -> str:
    if row["previous_team_roster_status"] == "no_previous_team_cache":
        return "needs_prior_roster_cache"
    if row["profile_cache_status"] != "cached":
        return "new_roster_player_needs_profile_check"
    if row["profile_transfer_candidate"] == "TRUE":
        return "possible_transfer"
    return "returning_or_freshman"


def candidate_action(row: dict[str, str]) -> str:
    if row["profile_transfer_candidate"] != "TRUE":
        return ""
    level = row["profile_prior_level_guess"]
    if level == "D1":
        return "add_transfer_row_and_d1_source_stats"
    if level == "D2":
        return "add_transfer_row_and_find_d2_source_stats"
    if level == "JUCO":
        return "add_transfer_row_and_find_juco_source_stats"
    if level == "NO_STATS":
        return "do_not_use_without_earlier_playable_season"
    return "manual_review_prior_school"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conference", choices=sorted(TEAMS_BY_CONFERENCE_SEASON), required=True)
    args = parser.parse_args()

    rosters = load_rosters(args.conference)
    rows: list[dict[str, str]] = []
    for (school_slug, season), roster in sorted(rosters.items()):
        prior_roster = rosters.get((school_slug, previous_season(season)))
        for player_key, roster_row in sorted(roster.items()):
            if prior_roster is None:
                previous_status = "no_previous_team_cache"
            elif player_key in prior_roster:
                previous_status = "returning_same_roster"
            else:
                previous_status = "not_on_previous_roster"
            profile_url = (
                f"https://www.sports-reference.com{roster_row.get('player_href', '')}"
                if roster_row.get("player_href", "").startswith("/")
                else roster_row.get("player_href", "")
            )
            profile_path, cache_status = profile_cache_path(profile_url, roster_row.get("player_slug", ""))
            prior = profile_prior_school(profile_path, roster_row["destination_school"], season) if profile_path else {}
            prior_school = prior.get("profile_prior_school", "")
            transfer_candidate = (
                previous_status == "not_on_previous_roster"
                and bool(prior_school)
                and not same_team(prior_school, roster_row["destination_school"])
            )
            row = {
                "target_conference": CONFERENCE_LABELS[args.conference],
                "first_target_season": season,
                "destination_school": roster_row["destination_school"],
                "destination_school_slug": school_slug,
                "player_name": roster_row.get("player", ""),
                "player_key": player_key,
                "class": roster_row.get("class", ""),
                "position": roster_row.get("pos", ""),
                "height": roster_row.get("height", ""),
                "weight": roster_row.get("weight", ""),
                "sports_reference_player_url": profile_url,
                "roster_cache_path": roster_row.get("roster_cache_path", ""),
                "previous_team_roster_status": previous_status,
                "profile_cache_status": cache_status,
                "profile_prior_season": prior.get("profile_prior_season", ""),
                "profile_prior_school": prior_school,
                "profile_prior_conf": prior.get("profile_prior_conf", ""),
                "profile_prior_level_guess": prior.get("profile_prior_level_guess", ""),
                "profile_transfer_candidate": "TRUE" if transfer_candidate else "FALSE",
                "candidate_action": "",
                "audit_status": "",
            }
            row["candidate_action"] = candidate_action(row)
            row["audit_status"] = audit_status(row)
            rows.append(row)

    possible = [row for row in rows if row["audit_status"] == "possible_transfer"]
    audit_path = Path(f"data/{args.conference}_sports_reference_roster_diff_audit.csv")
    possible_path = Path(f"data/{args.conference}_roster_diff_possible_transfers.csv")
    summary_path = Path(f"data/{args.conference}_sports_reference_roster_diff_summary.csv")
    write_csv(audit_path, OUTPUT_COLUMNS, rows)
    write_csv(possible_path, OUTPUT_COLUMNS, possible)

    summary_counts: dict[tuple[str, str, str], int] = {}
    for row in rows:
        key = (row["first_target_season"], row["destination_school"], row["audit_status"])
        summary_counts[key] = summary_counts.get(key, 0) + 1
    summary_rows = [
        {"first_target_season": season, "destination_school": school, "audit_status": status, "count": count}
        for (season, school, status), count in sorted(summary_counts.items())
    ]
    write_csv(summary_path, ["first_target_season", "destination_school", "audit_status", "count"], summary_rows)

    print(f"Wrote {len(rows)} roster audit rows to {audit_path}")
    print(f"Wrote {len(possible)} possible transfers to {possible_path}")
    print(f"Wrote summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
