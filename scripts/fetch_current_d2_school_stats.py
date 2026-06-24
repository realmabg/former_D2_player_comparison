#!/usr/bin/env python3
"""Fetch current D2 stat overrides from official school stats pages.

This is designed for local, slow runs. It starts from suspicious rows by
default, guesses each school's official stats page from data/d2_team_directory,
caches every page, and writes dashboard-compatible verified stat overrides.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import ssl
import subprocess
import time
import urllib.error
from urllib.parse import urljoin
import urllib.request
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path

import pandas as pd

from fetch_current_d2_verified_stats import derive_extra_stats, flatten_columns, normalize, number, parse_school_row


DEFAULT_CURRENT_D2 = Path("d2_data_cleaned.csv")
DEFAULT_SUSPICIOUS = Path("data/current_d2_suspicious_event_stats.csv")
DEFAULT_TEAM_DIRECTORY = Path("data/d2_team_directory.csv")
DEFAULT_URL_OVERRIDES = Path("data/current_d2_school_stat_url_overrides.csv")
DEFAULT_NAME_ALIASES = Path("data/current_d2_school_player_name_aliases.csv")
DEFAULT_OUTPUT = Path("data/current_d2_school_verified_stats.csv")
DEFAULT_RAW_OUTPUT = Path("data/current_d2_school_verified_raw_rows.csv")
DEFAULT_MISSING = Path("data/current_d2_school_stats_missing.csv")
DEFAULT_QUEUE = Path("data/current_d2_school_stats_queue.csv")
DEFAULT_CACHE_DIR = Path("data/cache/current_d2_school_stats")

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
NAME_ALIASES: dict[str, list[str]] = {}

STAT_OUTPUT_COLUMNS = [
    "Player Name",
    "Team",
    "Conference",
    "source_url",
    "source_method",
    "row_match_text",
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
    "ORB",
    "DRB",
    "TOT RB",
    "RPG",
    "PF",
    "AST",
    "TO",
    "STL",
    "BLK",
    "APG",
    "TOPG",
    "SPG",
    "BPG",
    "pts_per_40",
    "reb_per_40",
    "ast_per_40",
    "stl_per_40",
    "blk_per_40",
    "tov_per_40",
    "eFG",
    "three_share",
    "AST_TOV",
    "FTR",
    "TS_pct",
]


def display_name(value: object) -> str:
    raw = str(value or "").strip()
    parts = [part.strip() for part in raw.split(",", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        if normalize_key(parts[1]) in SUFFIXES:
            return raw
        return f"{parts[1]} {parts[0]}".strip()
    return raw


def normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def load_name_aliases(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["player_name", "team", "alias"]).to_csv(path, index=False)
        return {}
    df = pd.read_csv(path).fillna("")
    required = {"player_name", "team", "alias"}
    if not required.issubset(df.columns):
        return {}
    aliases: dict[str, list[str]] = {}
    for row in df.to_dict("records"):
        player_name = normalize_key(row.get("player_name"))
        team = normalize_key(row.get("team"))
        alias = str(row.get("alias", "")).strip()
        if player_name and team and alias:
            aliases.setdefault(f"{player_name}|{team}", []).append(alias)
    return aliases


def cache_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")[:180] + ".html"


def fetch_url(url: str, cache_dir: Path, sleep: float, refresh: bool) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name(url)
    if cache_path.exists() and not refresh:
        print(f"    cache hit: {cache_path}", flush=True)
        cached_text = cache_path.read_text(encoding="utf-8", errors="replace")
        if cached_text.strip():
            return cached_text
        print("    empty cache ignored; refetching", flush=True)
    print(f"    fetch: {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 current-d2-school-stats"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        html_text = response.read().decode("utf-8", errors="replace")
    if not html_text.strip():
        curl = subprocess.run(
            ["curl", "-L", "--max-time", "45", "-A", "Mozilla/5.0 current-d2-school-stats", url],
            text=True,
            capture_output=True,
            check=False,
        )
        if curl.returncode == 0 and curl.stdout.strip():
            html_text = curl.stdout
    if not html_text.strip():
        raise ValueError(f"empty response from {url}")
    cache_path.write_text(html_text, encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return html_text


def classify_page(html_text: str) -> str:
    lowered = html_text.lower()
    if "_incapsula_resource" in lowered or "incapsula" in lowered:
        return "incapsula_protected_or_template_page"
    if "c-events__team" in lowered and "data-bind" in lowered and "<table" not in lowered:
        return "sidearm_template_without_static_tables"
    if "enable javascript" in lowered or "just a moment" in lowered:
        return "challenge_or_javascript_required_page"
    if "<table" not in lowered:
        return "no_static_html_tables"
    return "html_with_tables"


def extract_embedded_json_objects(html_text: str) -> list[object]:
    """Best-effort extraction for pages with JSON blobs in script tags."""
    objects: list[object] = []
    for match in re.finditer(r"(\{[^{}]{0,2000}(?:players|stats|statistics|roster)[^{}]{0,2000}\})", html_text, flags=re.I):
        text = match.group(1)
        try:
            objects.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return objects


def discover_embedded_stat_urls(base_url: str, html_text: str) -> list[str]:
    """Find Presto/SIDEARM stat fragments loaded after the outer page.

    Several Presto team pages render the visible player tables through AJAX
    fragments. The outer HTML only contains team split tables, so we follow
    the embedded player/stat fragment URLs and parse those tables too.
    """
    urls: list[str] = []
    seen: set[str] = set()
    patterns = [
        r'data-url="([^"]+)"',
        r"value=\"([^\"]*brief-category-template[^\"]*)\"",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html_text, flags=re.I):
            raw = html_lib.unescape(match.group(1))
            lowered = raw.lower()
            if "stats-bios-template" not in lowered and "brief-category-template" not in lowered:
                continue
            # Only fetch the overall total categories we need. Presto also
            # exposes per-game, per-40, monthly, and split fragments whose
            # columns look similar and can overwrite the true total line.
            if "r=1" in lowered:
                continue
            if "stats-bios-template" in lowered and not re.search(r"[?&]pos=(sh|bc|bcext)(&|$)", lowered):
                continue
            if "brief-category-template" in lowered and not re.search(r"[?&]pos=(sh|bc|st|bt)(&|$)", lowered):
                continue
            absolute = urljoin(base_url, raw)
            if absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
    return urls


def table_rows_from_html(html_text: str) -> list[pd.DataFrame]:
    try:
        tables = pd.read_html(StringIO(html_text))
    except (ImportError, ValueError, OSError, Exception):
        return []
    cleaned: list[pd.DataFrame] = []
    for table in tables:
        table = table.copy()
        table.columns = flatten_columns(table.columns)
        cleaned.append(table)
    return cleaned


def load_domain_lookup(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    df = pd.read_csv(path).fillna("")
    lookup: dict[str, str] = {}
    for row in df.to_dict("records"):
        team = row.get("team_name", "")
        domain = str(row.get("school_domain", "")).strip()
        if team and domain:
            lookup[normalize_key(team)] = domain
    return lookup


def load_url_overrides(path: Path) -> dict[tuple[str, str], str]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["team", "season", "stats_url", "notes"]).to_csv(path, index=False)
        return {}
    df = pd.read_csv(path).fillna("")
    required = {"team", "season", "stats_url"}
    if not required.issubset(df.columns):
        return {}
    overrides: dict[tuple[str, str], str] = {}
    for row in df.to_dict("records"):
        url = str(row.get("stats_url", "")).strip()
        if not url:
            continue
        overrides[(normalize_key(row.get("team")), str(row.get("season", "")).strip())] = url
    return overrides


def candidate_urls(team: object, season: str, domain_lookup: dict[str, str], overrides: dict[tuple[str, str], str]) -> list[str]:
    key = normalize_key(team)
    override = overrides.get((key, season))
    if override:
        return [override]
    domain = domain_lookup.get(key, "")
    if not domain:
        return []
    return [
        f"https://{domain}/sports/mens-basketball/stats/{season}",
        f"https://{domain}/sports/mbkb/stats/{season}",
        f"https://{domain}/sports/mens-basketball/{season}/stats",
        f"https://{domain}/sports/mbkb/{season}/stats",
    ]


def load_candidates(args: argparse.Namespace) -> pd.DataFrame:
    current = pd.read_csv(args.input)
    if args.mode == "all":
        candidates = current.copy()
    else:
        if not args.suspicious_input.exists():
            raise FileNotFoundError(f"{args.suspicious_input} does not exist. Run validate_current_d2_stats.py first.")
        suspicious = pd.read_csv(args.suspicious_input)
        keys = suspicious[["Player Name", "Team"]].drop_duplicates()
        candidates = current.merge(keys, on=["Player Name", "Team"], how="inner")
    if args.names:
        wanted = {normalize(display_name(name)) for name in args.names}
        candidates = candidates[candidates["Player Name"].map(lambda value: normalize(display_name(value))).isin(wanted)]
    candidates = candidates.drop_duplicates(subset=["Player Name", "Team"], keep="first")
    if args.limit:
        candidates = candidates.head(args.limit)
    return candidates.reset_index(drop=True)


def row_text(row: pd.Series) -> str:
    return " ".join(str(value) for value in row.tolist() if str(value) and str(value).lower() != "nan")


def aliases_for_player(player_name: object, team: object = "") -> list[str]:
    player_key = normalize_key(player_name)
    team_key = normalize_key(team)
    aliases = list(NAME_ALIASES.get(f"{player_key}|{team_key}", []))
    aliases.extend(NAME_ALIASES.get(f"{player_key}|", []))
    return aliases


def meaningful_name_tokens(player_name: object, team: object = "") -> list[str]:
    alias = aliases_for_player(player_name, team)
    shown = alias[0] if alias else display_name(player_name)
    return [token for token in normalize(shown).split() if token not in SUFFIXES]


def name_variants(player_name: object, team: object = "") -> set[str]:
    shown = display_name(player_name)
    raw = str(player_name or "").strip()
    variants = {normalize(shown), normalize(raw)}
    for alias in aliases_for_player(player_name, team):
        variants.add(normalize(alias))
        alias_tokens = [token for token in normalize(alias).split() if token not in SUFFIXES]
        if len(alias_tokens) >= 2:
            variants.add(normalize(" ".join(reversed(alias_tokens))))
    parts = [part.strip() for part in raw.split(",", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        variants.add(normalize(f"{parts[0]} {parts[1]}"))
    shown_tokens = [token for token in normalize(shown).split() if token not in SUFFIXES]
    if len(shown_tokens) >= 2:
        variants.add(normalize(" ".join(reversed(shown_tokens))))
    variants.add(" ".join(meaningful_name_tokens(player_name, team)))
    return {variant for variant in variants if variant}


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def row_name_score(player_name: object, text: str, team: object = "") -> int:
    target_tokens = meaningful_name_tokens(player_name, team)
    if not target_tokens:
        return 0

    text_norm = normalize(text)
    text_tokens = set(text_norm.split())
    text_compact = compact(text_norm)
    variants = name_variants(player_name, team)

    # Strong match: the cleaned full name appears contiguously, including
    # punctuation variants such as "JP Ricks" vs "J.P. Ricks".
    for variant in variants:
        variant_tokens = [token for token in variant.split() if token not in SUFFIXES]
        variant_clean = " ".join(variant_tokens)
        if not variant_clean:
            continue
        if variant_clean in text_norm:
            return 100
        compact_variant = compact(variant_clean)
        if len(compact_variant) >= 5 and compact_variant in text_compact:
            return 95

    # Safe token match: all meaningful name tokens appear somewhere in the row.
    if len(target_tokens) >= 2 and all(token in text_tokens for token in target_tokens):
        return 90

    first = target_tokens[0]
    last = target_tokens[-1]
    if len(target_tokens) >= 2 and last in text_tokens:
        # Allow first-initial matches for rows where a school writes Jake/Jacob,
        # J.P./JP, etc. Never accept last-name-only or suffix-only matches.
        first_initial = first[0]
        if first in text_tokens or any(token.startswith(first_initial) and len(token) <= 4 for token in text_tokens):
            return 70

    best_ratio = 0.0
    target_clean = " ".join(target_tokens)
    for window_size in range(max(1, len(target_tokens) - 1), len(target_tokens) + 2):
        row_tokens = text_norm.split()
        for start in range(0, max(0, len(row_tokens) - window_size + 1)):
            candidate = " ".join(row_tokens[start : start + window_size])
            best_ratio = max(best_ratio, SequenceMatcher(None, target_clean, candidate).ratio())
    if best_ratio >= 0.88:
        return 60
    return 0


def find_player_rows(tables: list[pd.DataFrame], player_name: object, team: object = "") -> list[tuple[pd.Series, str]]:
    possible_rows: list[tuple[int, pd.Series, str]] = []
    for table in tables:
        for _, row in table.iterrows():
            text = row_text(row)
            score = row_name_score(player_name, text, team)
            if score:
                possible_rows.append((score, row, text))
    possible_rows.sort(key=lambda item: item[0], reverse=True)
    return [(row, text) for _, row, text in possible_rows]


def find_player_row(tables: list[pd.DataFrame], player_name: object, team: object = "") -> tuple[pd.Series, str] | None:
    rows = find_player_rows(tables, player_name, team)
    return rows[0] if rows else None


def raw_row_dict(row: pd.Series) -> dict[str, object]:
    out: dict[str, object] = {}
    for column, value in row.items():
        key = str(column).strip()
        if not key or key.lower().startswith("unnamed"):
            continue
        out[key] = value
    return out


def presto_total_like_row(row: pd.Series) -> bool:
    keys = {str(column).strip().lower() for column in row.index}
    total_keys = {"min", "fg", "3pt", "ft", "pts", "off", "def", "reb", "pf", "ast", "to", "stl", "blk"}
    per_game_keys = {key for key in keys if key.endswith("/g") or key.endswith("/40")}
    sidearm_total_keys = {
        key
        for key in keys
        if any(
            marker in key
            for marker in [
                "minutes tot",
                "scoring pts",
                "rebounds tot",
                "pf pf",
                "ast ast",
                "to to",
                "stl stl",
                "blk blk",
            ]
        )
    }
    return (bool(keys & total_keys) or bool(sidearm_total_keys)) and not bool(per_game_keys)


def parse_statcrew_numeric_row(row: pd.Series) -> dict[str, object]:
    """Parse old StatCrew static tables with numeric column indexes.

    Example row shape:
    no, player, GP, GS, MIN, MPG, FGM, FGA, FG%, 3FG, 3FGA, 3FG%, ...
    """
    values = list(row.tolist())
    if len(values) < 27:
        return {}
    # The first two cells are usually jersey number and player name.
    if number(values[2]) is None or number(values[4]) is None:
        return {}
    out = {
        "GP": number(values[2]),
        "GS": number(values[3]),
        "MIN": number(values[4]),
        "MPG": number(values[5]),
        "FGM": number(values[6]),
        "FGA": number(values[7]),
        "FG%": number(values[8]),
        "3PTM": number(values[9]),
        "3PTA": number(values[10]),
        "3PT%": number(values[11]),
        "FTM": number(values[12]),
        "FTA": number(values[13]),
        "FT%": number(values[14]),
        "ORB": number(values[15]),
        "DRB": number(values[16]),
        "TOT RB": number(values[17]),
        "RPG": number(values[18]),
        "PF": number(values[19]),
        "AST": number(values[21]),
        "TO": number(values[22]),
        "BLK": number(values[23]),
        "STL": number(values[24]),
        "PTS": number(values[25]),
        "PPG": number(values[26]),
    }
    return {key: value for key, value in out.items() if value is not None}


def parse_player_from_page(player_name: object, html_text: str, team: object = "") -> tuple[dict[str, object], str, dict[str, object]]:
    page_type = classify_page(html_text)
    tables = table_rows_from_html(html_text)
    if not tables:
        embedded_count = len(extract_embedded_json_objects(html_text))
        raise ValueError(f"{page_type}; parsed 0 HTML tables; embedded_json_candidates={embedded_count}")
    matches = find_player_rows(tables, player_name, team)
    if not matches:
        raise ValueError(f"{page_type}; parsed {len(tables)} HTML tables but no matching player row found")
    parse_errors: list[str] = []
    total_candidates: list[tuple[dict[str, object], dict[str, object], str]] = []
    merged_fallback_stats: dict[str, object] = {}
    merged_fallback_raw: dict[str, object] = {}
    fallback_texts: list[str] = []
    for row, text in matches:
        stats = parse_school_row(row)
        if not stats or not any(number(stats.get(column)) is not None for column in ["GP", "MIN", "MPG", "PTS", "AST"]):
            stats = parse_statcrew_numeric_row(row)
        if stats and any(number(stats.get(column)) is not None for column in ["GP", "MIN", "MPG", "PTS", "AST"]):
            if presto_total_like_row(row):
                total_candidates.append((stats, raw_row_dict(row), text[:220]))
            else:
                merged_fallback_stats.update(stats)
                merged_fallback_raw.update(raw_row_dict(row))
                fallback_texts.append(text[:220])
            continue
        parse_errors.append(text[:250])

    if total_candidates:
        # Some player pages include split rows after the overall row. Keep the
        # total/category rows from the largest GP/minutes group so a 1-game
        # split cannot overwrite the season total.
        def total_score(candidate: tuple[dict[str, object], dict[str, object], str]) -> tuple[float, float]:
            stats, _, _ = candidate
            return (number(stats.get("GP")) or 0.0, number(stats.get("MIN")) or 0.0)

        max_gp, max_min = max(total_score(candidate) for candidate in total_candidates)
        selected_total_candidates = [
            candidate
            for candidate in total_candidates
            if (number(candidate[0].get("GP")) or 0.0) == max_gp
            and (not max_min or (number(candidate[0].get("MIN")) or 0.0) == max_min)
        ]
        if not selected_total_candidates:
            selected_total_candidates = [
                candidate for candidate in total_candidates if (number(candidate[0].get("GP")) or 0.0) == max_gp
            ]
        merged_total_stats: dict[str, object] = {}
        merged_total_raw: dict[str, object] = {}
        total_texts: list[str] = []
        for stats, raw, text in selected_total_candidates:
            for key, value in stats.items():
                if key not in merged_total_stats or number(merged_total_stats.get(key)) is None:
                    merged_total_stats[key] = value
            for key, value in raw.items():
                if key not in merged_total_raw or pd.isna(merged_total_raw.get(key)):
                    merged_total_raw[key] = value
            total_texts.append(text)
        return derive_extra_stats(merged_total_stats), " || ".join(total_texts)[:500], merged_total_raw
    if merged_fallback_stats:
        return derive_extra_stats(merged_fallback_stats), " || ".join(fallback_texts)[:500], merged_fallback_raw
    raise ValueError(f"{page_type}; matching row found, but no parseable school stat columns: {parse_errors[0] if parse_errors else ''}")


def existing_verified(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def write_queue(candidates: pd.DataFrame, args: argparse.Namespace, domain_lookup: dict[str, str], overrides: dict[tuple[str, str], str]) -> None:
    rows = []
    for row in candidates.to_dict("records"):
        urls = candidate_urls(row.get("Team"), args.season, domain_lookup, overrides)
        rows.append(
            {
                "Player Name": row.get("Player Name", ""),
                "display_name": display_name(row.get("Player Name", "")),
                "Team": row.get("Team", ""),
                "Conference": row.get("Conference", ""),
                "season": args.season,
                "domain_found": bool(urls),
                "candidate_urls": " | ".join(urls),
            }
        )
    args.queue_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.queue_output, index=False)
    print(f"Wrote queue preview to {args.queue_output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_CURRENT_D2)
    parser.add_argument("--suspicious-input", type=Path, default=DEFAULT_SUSPICIOUS)
    parser.add_argument("--team-directory", type=Path, default=DEFAULT_TEAM_DIRECTORY)
    parser.add_argument("--url-overrides", type=Path, default=DEFAULT_URL_OVERRIDES)
    parser.add_argument("--name-aliases", type=Path, default=DEFAULT_NAME_ALIASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--queue-output", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--mode", choices=["suspicious", "all"], default="suspicious")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--sleep", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--write-queue-only", action="store_true")
    parser.add_argument("--names", nargs="*", default=[])
    args = parser.parse_args()

    global NAME_ALIASES
    NAME_ALIASES = load_name_aliases(args.name_aliases)

    candidates = load_candidates(args)
    domain_lookup = load_domain_lookup(args.team_directory)
    overrides = load_url_overrides(args.url_overrides)
    write_queue(candidates, args, domain_lookup, overrides)
    if args.write_queue_only:
        return 0

    verified_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for index, row in enumerate(candidates.to_dict("records"), start=1):
        player_name = row.get("Player Name", "")
        team = row.get("Team", "")
        conference = row.get("Conference", "")
        print(f"[{index}/{len(candidates)}] {display_name(player_name)} - {team}", flush=True)
        urls = candidate_urls(team, args.season, domain_lookup, overrides)
        if not urls:
            missing_rows.append(
                {
                    "Player Name": player_name,
                    "Team": team,
                    "Conference": conference,
                    "season": args.season,
                    "reason": "no school domain or URL override found",
                    "candidate_urls": "",
                }
            )
            print("  MISS no school domain or URL override found", flush=True)
            continue

        parsed = None
        errors: list[str] = []
        for url in urls:
            try:
                html_text = fetch_url(url, args.cache_dir, args.sleep, args.refresh_cache)
                page_texts = [html_text]
                for embedded_url in discover_embedded_stat_urls(url, html_text):
                    try:
                        page_texts.append(fetch_url(embedded_url, args.cache_dir, args.sleep, args.refresh_cache))
                    except (urllib.error.URLError, TimeoutError) as error:
                        errors.append(f"{embedded_url}: {error}")
                stats, matched_text, raw = parse_player_from_page(player_name, "\n".join(page_texts), team)
                parsed = (url, stats, matched_text, raw)
                break
            except (urllib.error.URLError, TimeoutError, ValueError, ImportError) as error:
                errors.append(f"{url}: {error}")
                print(f"  candidate miss: {error}", flush=True)

        if not parsed:
            missing_rows.append(
                {
                    "Player Name": player_name,
                    "Team": team,
                    "Conference": conference,
                    "season": args.season,
                    "reason": " ; ".join(errors)[:1500],
                    "candidate_urls": " | ".join(urls),
                }
            )
            print("  MISS no parseable official school row", flush=True)
            continue

        source_url, stats, matched_text, raw = parsed
        verified_rows.append(
            {
                "Player Name": player_name,
                "Team": team,
                "Conference": conference,
                "source_url": source_url,
                "source_method": "official_school_stats_page",
                "row_match_text": matched_text,
                **stats,
            }
        )
        raw_rows.append(
            {
                "Player Name": player_name,
                "Team": team,
                "Conference": conference,
                "source_url": source_url,
                "source_method": "official_school_stats_page",
                "row_match_text": matched_text,
                "raw_row_json": json.dumps(raw, default=str, sort_keys=True),
                **{f"raw_{column}": value for column, value in raw.items()},
            }
        )
        print(f"  OK {source_url}", flush=True)

    output = pd.DataFrame(verified_rows)
    if args.append and args.output.exists():
        output = pd.concat([existing_verified(args.output), output], ignore_index=True)
        output = output.drop_duplicates(subset=["Player Name", "Team"], keep="last")
    raw_output = pd.DataFrame(raw_rows)
    if args.append and args.raw_output.exists():
        raw_output = pd.concat([existing_verified(args.raw_output), raw_output], ignore_index=True)
        raw_output = raw_output.drop_duplicates(subset=["Player Name", "Team"], keep="last")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if output.empty:
        pd.DataFrame(columns=STAT_OUTPUT_COLUMNS).to_csv(args.output, index=False)
    else:
        for column in STAT_OUTPUT_COLUMNS:
            if column not in output.columns:
                output[column] = pd.NA
        output[STAT_OUTPUT_COLUMNS].to_csv(args.output, index=False)

    if raw_output.empty:
        pd.DataFrame(columns=["Player Name", "Team", "Conference", "source_url", "source_method", "row_match_text", "raw_row_json"]).to_csv(
            args.raw_output, index=False
        )
    else:
        raw_output.to_csv(args.raw_output, index=False)

    pd.DataFrame(missing_rows).to_csv(args.missing_output, index=False)
    print(f"Wrote {len(output)} school-verified rows to {args.output}")
    print(f"Wrote {len(raw_output)} raw matched school rows to {args.raw_output}")
    print(f"Wrote {len(missing_rows)} missing rows to {args.missing_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
