#!/usr/bin/env python3
"""Audit current D2 school stat rows against official player profile pages.

The team cumulative stats page remains the primary source. This script uses
profile/bio links from the same official stats page as a QA layer and flags
rows where the player profile reports materially different stats.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode, urljoin

import pandas as pd
from bs4 import BeautifulSoup

from fetch_current_d2_school_stats import (
    cache_name,
    fetch_url,
    row_name_score,
    row_text,
    table_rows_from_html,
)
from fetch_current_d2_verified_stats import derive_extra_stats, number, parse_school_row, split_made_attempted


DEFAULT_VERIFIED = Path("data/current_d2_school_verified_stats.csv")
DEFAULT_OUTPUT = Path("data/current_d2_school_profile_audit.csv")
DEFAULT_CACHE_DIR = Path("data/cache/current_d2_school_profiles")
DEFAULT_STATS_CACHE_DIR = Path("data/cache/current_d2_school_stats")

COMPARE_FIELDS = [
    "GP",
    "MIN",
    "MPG",
    "FGM",
    "FGA",
    "FG%",
    "3PTM",
    "3PTA",
    "3PT%",
    "FTM",
    "FTA",
    "FT%",
    "PTS",
    "PPG",
    "TOT RB",
    "RPG",
    "AST",
    "APG",
    "TO",
    "TOPG",
    "STL",
    "SPG",
    "BLK",
    "BPG",
]


def cell_text(tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def extract_profile_url(stats_html: str, stats_url: str, player_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(stats_html, "lxml")
    best_score = 0
    best_link = ""
    best_text = ""
    for row in soup.find_all("tr"):
        text = cell_text(row)
        score = row_name_score(player_name, text)
        if score <= best_score:
            continue
        href = ""
        for link in row.find_all("a", href=True):
            link_text = cell_text(link).lower()
            title = str(link.get("title", "")).lower()
            candidate_href = str(link.get("href", ""))
            if "roster" in candidate_href or "bio" in link_text or "bio" in title:
                href = candidate_href
                break
        if href:
            best_score = score
            best_link = urljoin(stats_url, href)
            best_text = text
    return best_link, best_text[:500]


def profile_candidate_rows(profile_html: str, season: str) -> list[tuple[int, dict[str, object], str]]:
    candidates: list[tuple[int, dict[str, object], str]] = []
    season_short = season.split("-", 1)[0] if season else ""
    for table in table_rows_from_html(profile_html):
        for _, row in table.iterrows():
            text = row_text(row)
            stats = derive_extra_stats(parse_school_row(row))
            if not stats or number(stats.get("GP")) is None:
                continue
            score = 0
            lowered = text.lower()
            if season and season.lower() in lowered:
                score += 100
            elif season_short and season_short in lowered:
                score += 80
            if "total" in lowered or "career" in lowered:
                score -= 50
            usable_count = sum(number(stats.get(field)) is not None for field in COMPARE_FIELDS)
            score += usable_count
            candidates.append((score, stats, text[:500]))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def js_object_value(body: str, key: str) -> str:
    match = re.search(rf"['\"]?{re.escape(key)}['\"]?\s*:\s*('([^']*)'|\"([^\"]*)\"|([^,\s}}]+))", body)
    if not match:
        return ""
    return next((group for group in match.groups()[1:] if group is not None), "").strip()


def extract_profile_stat_params(profile_html: str, season: str) -> dict[str, str]:
    """Find the SIDEARM JSON params embedded on a roster profile page."""
    season_year = season.split("-", 1)[0] if season else ""
    param_bodies = []
    param_bodies.extend(re.findall(r"data-params=(?:'|\")(\{.*?type.*?stats.*?\})(?:'|\")", profile_html, flags=re.I | re.S))
    param_bodies.extend(re.findall(r"_params\s*=\s*(\{.*?type.*?stats.*?\})", profile_html, flags=re.I | re.S))

    parsed: list[dict[str, str]] = []
    for body in param_bodies:
        params = {
            "type": js_object_value(body, "type") or "stats",
            "rp_id": js_object_value(body, "rp_id"),
            "path": js_object_value(body, "path"),
            "year": js_object_value(body, "year"),
            "player_id": js_object_value(body, "player_id") or "0",
        }
        if params["rp_id"] and params["path"] and params["year"]:
            parsed.append(params)

    if parsed:
        parsed.sort(key=lambda params: int(params.get("year") == season_year), reverse=True)
        return parsed[0]

    rp_id = re.search(r"\brp_id\s*=\s*['\"]?(\d+)", profile_html)
    player_id = re.search(r"\bplayer_id\s*=\s*['\"]?(\d+)", profile_html)
    path = re.search(r"\bpath\s*=\s*['\"]([^'\"]+)", profile_html)
    year = re.search(r"\byear\s*=\s*['\"]?(\d{4})", profile_html)
    if not (rp_id and path):
        return {}
    return {
        "type": "stats",
        "rp_id": rp_id.group(1),
        "path": path.group(1),
        "year": year.group(1) if year else season_year,
        "player_id": player_id.group(1) if player_id else "0",
    }


def profile_stats_endpoint(profile_url: str, params: dict[str, str]) -> str:
    return urljoin(profile_url, "/services/responsive-roster-bio.ashx") + "?" + urlencode(params)


def flatten_json(value: object, prefix: str = "") -> dict[str, object]:
    flat: dict[str, object] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            flat.update(flatten_json(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{prefix}.{index}" if prefix else str(index)
            flat.update(flatten_json(item, child))
    else:
        flat[prefix] = value
    return flat


def normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def json_value(flat: dict[str, object], aliases: list[str]) -> object:
    normalized_aliases = [normalized_key(alias) for alias in aliases]
    for key, value in flat.items():
        last = key.rsplit(".", 1)[-1]
        if normalized_key(last) in normalized_aliases:
            return value
    for key, value in flat.items():
        key_norm = normalized_key(key)
        if any(alias and key_norm.endswith(alias) for alias in normalized_aliases):
            return value
    return None


def parse_json_stat_payload(payload: object) -> dict[str, object]:
    flat = flatten_json(payload)
    stats: dict[str, object] = {}
    aliases = {
        "GP": ["gp", "g", "games", "games_played", "gamesplayed"],
        "MIN": ["min", "mins", "minutes", "minutes_played", "minutesplayed"],
        "MPG": ["mpg", "minutes_per_game"],
        "FGM": ["fgm", "field_goals_made", "fieldgoalsmade"],
        "FGA": ["fga", "field_goals_attempted", "fieldgoalsattempted"],
        "FG%": ["fg_pct", "fg_percent", "field_goal_percentage", "fieldgoalpercentage"],
        "3PTM": ["3pm", "3ptm", "three_point_field_goals_made", "threepointfieldgoalsmade"],
        "3PTA": ["3pa", "3pta", "three_point_field_goals_attempted", "threepointfieldgoalsattempted"],
        "3PT%": ["3p_pct", "3pt_pct", "three_point_percentage", "threepointpercentage"],
        "FTM": ["ftm", "free_throws_made", "freethrowsmade"],
        "FTA": ["fta", "free_throws_attempted", "freethrowsattempted"],
        "FT%": ["ft_pct", "ft_percent", "free_throw_percentage", "freethrowpercentage"],
        "PTS": ["pts", "points"],
        "PPG": ["ppg", "points_per_game"],
        "ORB": ["orb", "oreb", "offensive_rebounds", "offensiverebounds"],
        "DRB": ["drb", "dreb", "defensive_rebounds", "defensiverebounds"],
        "TOT RB": ["reb", "rebs", "rebounds", "total_rebounds", "totalrebounds"],
        "RPG": ["rpg", "rebounds_per_game"],
        "AST": ["ast", "assists"],
        "APG": ["apg", "assists_per_game"],
        "TO": ["to", "tov", "turnovers"],
        "TOPG": ["topg", "turnovers_per_game"],
        "STL": ["stl", "steals"],
        "SPG": ["spg", "steals_per_game"],
        "BLK": ["blk", "blocks", "blocked_shots", "blockedshots"],
        "BPG": ["bpg", "blocks_per_game"],
    }
    for field, field_aliases in aliases.items():
        parsed = number(json_value(flat, field_aliases))
        if parsed is not None:
            stats[field] = parsed
    return derive_extra_stats(stats)


def parse_profile_current_stats_table(html_text: str) -> dict[str, object]:
    """Parse SIDEARM profile current_stats game-by-game HTML.

    These profile tables often have no GP column. The cumulative values are in
    the table footer, while GP has to be inferred from the game rows.
    """
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.find("table")
    if table is None:
        return {}
    body_rows = table.select("tbody tr")
    total_row = table.select_one("tfoot tr")
    if total_row is None:
        return {}
    cells = [cell_text(cell) for cell in total_row.find_all(["th", "td"])]
    if len(cells) < 21:
        return {}
    fgm, fga = split_made_attempted(cells[4])
    three_m, three_a = split_made_attempted(cells[6])
    ftm, fta = split_made_attempted(cells[8])
    out: dict[str, object] = {
        "GP": len([row for row in body_rows if cell_text(row)]),
        "MIN": number(cells[3]),
        "FGM": fgm,
        "FGA": fga,
        "FG%": number(cells[5]),
        "3PTM": three_m,
        "3PTA": three_a,
        "3PT%": number(cells[7]),
        "FTM": ftm,
        "FTA": fta,
        "FT%": number(cells[9]),
        "ORB": number(cells[10]),
        "DRB": number(cells[11]),
        "TOT RB": number(cells[12]),
        "RPG": number(cells[13]),
        "PF": number(cells[14]),
        "AST": number(cells[15]),
        "TO": number(cells[16]),
        "BLK": number(cells[17]),
        "STL": number(cells[18]),
        "PTS": number(cells[19]),
        "PPG": number(cells[20]),
    }
    return derive_extra_stats(out)


def collect_json_candidates(payload: object, season: str) -> list[tuple[int, dict[str, object], str]]:
    candidates: list[tuple[int, dict[str, object], str]] = []

    def walk(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            stats = parse_json_stat_payload(value)
            if number(stats.get("GP")) is not None:
                text = json.dumps(value, default=str, sort_keys=True)[:500]
                lowered = f"{path} {text}".lower()
                score = sum(number(stats.get(field)) is not None for field in COMPARE_FIELDS)
                if season and season.lower() in lowered:
                    score += 100
                if "career" in lowered or "total" in lowered:
                    score -= 25
                candidates.append((score, stats, text))
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}.{index}" if path else str(index))
        elif isinstance(value, str) and "<table" in value.lower():
            profile_stats = parse_profile_current_stats_table(value)
            if number(profile_stats.get("GP")) is not None:
                candidates.append((125, profile_stats, "SIDEARM profile current_stats footer"))
            for table in table_rows_from_html(value):
                for _, row in table.iterrows():
                    stats = derive_extra_stats(parse_school_row(row))
                    if number(stats.get("GP")) is not None:
                        candidates.append((75, stats, row_text(row)[:500]))

    walk(payload)
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def profile_json_candidate_rows(profile_html: str, profile_url: str, season: str, args: argparse.Namespace) -> tuple[list[tuple[int, dict[str, object], str]], str, str]:
    params = extract_profile_stat_params(profile_html, season)
    if not params:
        return [], "", "profile_json_params_not_found"
    endpoint = profile_stats_endpoint(profile_url, params)
    try:
        raw = fetch_url(endpoint, args.cache_dir, args.sleep, args.refresh_cache)
    except (urllib.error.URLError, TimeoutError) as error:
        return [], endpoint, f"profile_json_fetch_failed: {error}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        if "<table" in raw.lower():
            return profile_candidate_rows(raw, season), endpoint, "profile_json_returned_html"
        return [], endpoint, "profile_json_parse_failed"
    return collect_json_candidates(payload, season), endpoint, "profile_json_checked"


def diff_value(team_value: object, profile_value: object) -> float | None:
    left = number(team_value)
    right = number(profile_value)
    if left is None or right is None:
        return None
    return right - left


def material_mismatches(team_row: dict[str, object], profile_stats: dict[str, object]) -> list[str]:
    mismatches: list[str] = []
    tolerances = {
        "MIN": 1.0,
        "FG%": 0.01,
        "3PT%": 0.01,
        "FT%": 0.01,
        "MPG": 0.15,
        "PPG": 0.15,
        "RPG": 0.15,
        "APG": 0.15,
        "TOPG": 0.15,
        "SPG": 0.15,
        "BPG": 0.15,
    }
    for field in COMPARE_FIELDS:
        delta = diff_value(team_row.get(field), profile_stats.get(field))
        if delta is None:
            continue
        tolerance = tolerances.get(field, 0.01)
        if abs(delta) > tolerance:
            mismatches.append(field)
    return mismatches


def audit_row(row: dict[str, object], args: argparse.Namespace) -> dict[str, object]:
    player_name = str(row.get("Player Name", ""))
    stats_url = str(row.get("source_url", ""))
    stats_cache_path = args.stats_cache_dir / cache_name(stats_url)
    base = {
        "Player Name": player_name,
        "Team": row.get("Team", ""),
        "source_url": stats_url,
    }
    if not stats_cache_path.exists():
        return {**base, "audit_status": "stats_page_cache_missing"}

    stats_html = stats_cache_path.read_text(encoding="utf-8", errors="replace")
    profile_url, matched_row_text = extract_profile_url(stats_html, stats_url, player_name)
    if not profile_url:
        return {**base, "audit_status": "profile_link_not_found", "stats_page_match_text": matched_row_text}

    try:
        profile_html = fetch_url(profile_url, args.cache_dir, args.sleep, args.refresh_cache)
    except (urllib.error.URLError, TimeoutError) as error:
        return {**base, "audit_status": "profile_fetch_failed", "profile_url": profile_url, "error": str(error)}

    json_candidates, profile_stats_endpoint_url, profile_json_status = profile_json_candidate_rows(
        profile_html, profile_url, args.season, args
    )
    candidates = json_candidates or profile_candidate_rows(profile_html, args.season)
    if not candidates:
        return {
            **base,
            "audit_status": "profile_stat_row_not_found",
            "profile_url": profile_url,
            "profile_stats_endpoint": profile_stats_endpoint_url,
            "profile_json_status": profile_json_status,
        }

    _, profile_stats, profile_text = candidates[0]
    mismatches = material_mismatches(row, profile_stats)
    out = {
        **base,
        "audit_status": "mismatch" if mismatches else "ok",
        "mismatch_fields": ";".join(mismatches),
        "profile_url": profile_url,
        "profile_stats_endpoint": profile_stats_endpoint_url,
        "profile_json_status": profile_json_status,
        "stats_page_match_text": matched_row_text,
        "profile_match_text": profile_text,
        "profile_stats_json": json.dumps(profile_stats, default=str, sort_keys=True),
    }
    for field in COMPARE_FIELDS:
        out[f"team_{field}"] = row.get(field, "")
        out[f"profile_{field}"] = profile_stats.get(field, "")
        out[f"delta_{field}"] = diff_value(row.get(field), profile_stats.get(field))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--stats-cache-dir", type=Path, default=DEFAULT_STATS_CACHE_DIR)
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--names", nargs="*", default=[])
    args = parser.parse_args()

    df = pd.read_csv(args.verified).fillna("")
    if args.names:
        wanted = {name.lower() for name in args.names}
        df = df[df["Player Name"].str.lower().isin(wanted)]
    if args.limit:
        df = df.head(args.limit)

    rows = []
    for index, row in enumerate(df.to_dict("records"), start=1):
        print(f"[{index}/{len(df)}] {row.get('Player Name')} - {row.get('Team')}", flush=True)
        result = audit_row(row, args)
        print(f"  {result.get('audit_status')} {result.get('profile_url', '')}", flush=True)
        rows.append(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"Wrote profile audit to {args.output}")
    if rows:
        print(pd.Series([row.get("audit_status", "") for row in rows]).value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
