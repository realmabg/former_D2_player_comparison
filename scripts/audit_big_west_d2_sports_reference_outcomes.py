#!/usr/bin/env python3
"""Audit D2 transfer Big West outcomes against Sports Reference profiles/pages."""

from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import pandas as pd


DATASET_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
OUTPUT_PATH = Path("data/big_west_d2_sports_reference_outcome_audit.csv")
MISMATCH_PATH = Path("data/big_west_d2_sports_reference_outcome_confirmed_mismatches.csv")
UNVERIFIED_PATH = Path("data/big_west_d2_sports_reference_outcome_unverified.csv")
PROFILE_CACHE_DIRS = [
    Path("data/cache/sports_reference_d2_outcome_audit"),
    Path("data/cache/sports_reference_roster_diff_profiles"),
    Path("data/cache/sports_reference_d1_profile_audit"),
]
BIG_WEST_SCHOOL_CACHE = Path("data/cache/sports_reference_big_west_schools")
ROSTER_DIFF_AUDIT_PATH = Path("data/big_west_sports_reference_roster_diff_audit.csv")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

TEAM_ALIASES = {
    "cal st fullerton": "cal state fullerton",
    "cal st northridge": "cal state northridge",
    "california san diego": "uc san diego",
    "california santa barbara": "uc santa barbara",
    "california riverside": "uc riverside",
    "long beach st": "long beach state",
    "ucsb": "uc santa barbara",
}

PROFILE_OVERRIDES = {
    ("chris mitchell", "uc santa barbara", "2024-25"): "https://www.sports-reference.com/cbb/players/chris-mitchell-4.html",
}


def normalize(value: object) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()
    return TEAM_ALIASES.get(text, text)


def without_suffixes(name: str) -> str:
    tokens = [
        token
        for token in normalize(name).split()
        if token not in {"jr", "sr", "ii", "iii", "iv", "v"}
    ]
    return " ".join(tokens)


def cache_name(url: str) -> str:
    return quote(url, safe="").replace("%", "_")[:180] + ".html"


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def page_html(path: Path) -> str:
    if not path.exists() or path.suffix == ".json":
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def url_slug(url: str) -> str:
    return Path(urlparse(str(url)).path).name.removesuffix(".html")


def profile_cache_path(url: str) -> Path | None:
    slug = url_slug(url)
    candidates = []
    for cache_dir in PROFILE_CACHE_DIRS:
        candidates.append(cache_dir / f"{slug}.html")
        if slug.endswith("-1"):
            candidates.append(cache_dir / f"{slug[:-2]}.html")
    for path in candidates:
        if path.exists() and path.stat().st_size > 500:
            return path
    return None


def get_profile_html(url: str) -> tuple[str, str]:
    existing = profile_cache_path(url)
    if existing:
        return page_html(existing), str(existing)
    PROFILE_CACHE_DIRS[0].mkdir(parents=True, exist_ok=True)
    path = PROFILE_CACHE_DIRS[0] / f"{url_slug(url)}.html"
    html = fetch(url)
    path.write_text(html, encoding="utf-8")
    time.sleep(1.0)
    return html, str(path)


def school_cache_path(url: str) -> Path | None:
    match = re.search(r"/schools/([^/]+)/men/(\d{4})\.html", str(url))
    if not match:
        return None
    school, year = match.groups()
    candidates = [
        BIG_WEST_SCHOOL_CACHE / f"{school}_{year}.html",
        BIG_WEST_SCHOOL_CACHE / f"{school}_{year}.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def roster_diff_profile_rows() -> list[dict[str, str]]:
    if not ROSTER_DIFF_AUDIT_PATH.exists():
        return []
    audit = pd.read_csv(ROSTER_DIFF_AUDIT_PATH)
    rows = []
    for _, row in audit.iterrows():
        url = str(row.get("sports_reference_player_url", "")).strip()
        if not url or url.lower() == "nan":
            continue
        rows.append(
            {
                "player": normalize(row.get("player_name", "")),
                "player_without_suffixes": without_suffixes(row.get("player_name", "")),
                "destination": normalize(row.get("destination_school", "")),
                "season": str(row.get("first_big_west_season", "")).strip(),
                "url": url,
            }
        )
    return rows


def find_roster_diff_profile_url(
    row: pd.Series, roster_diff_profiles: list[dict[str, str]]
) -> str:
    wanted = normalize(row.get("player_name", ""))
    wanted_without_suffixes = without_suffixes(row.get("player_name", ""))
    destination = normalize(row.get("destination_school", ""))
    season = str(row.get("first_big_west_season", "")).strip()
    candidates = [
        profile
        for profile in roster_diff_profiles
        if profile["destination"] == destination and profile["season"] == season
    ]
    for profile in candidates:
        if profile["player"] == wanted or profile["player_without_suffixes"] == wanted_without_suffixes:
            return profile["url"]
    wanted_last = wanted_without_suffixes.split()[-1] if wanted_without_suffixes.split() else ""
    last_name_matches = [
        profile
        for profile in candidates
        if wanted_last and profile["player_without_suffixes"].split()[-1:] == [wanted_last]
    ]
    if len(last_name_matches) == 1:
        return last_name_matches[0]["url"]
    return ""


def find_profile_from_school_page(row: pd.Series, roster_diff_profiles: list[dict[str, str]]) -> str:
    outcome_url = str(row.get("outcome_url", ""))
    if "/players/" in outcome_url:
        return outcome_url
    key = (
        normalize(row.get("player_name", "")),
        normalize(row.get("destination_school", "")),
        str(row.get("first_big_west_season", "")).strip(),
    )
    if key in PROFILE_OVERRIDES:
        return PROFILE_OVERRIDES[key]
    roster_diff_url = find_roster_diff_profile_url(row, roster_diff_profiles)
    if roster_diff_url:
        return roster_diff_url
    path = school_cache_path(outcome_url)
    html = page_html(path) if path else ""
    if not html:
        return ""
    wanted = normalize(row["player_name"])
    last = wanted.split()[-1] if wanted.split() else wanted
    for href, text in re.findall(r'<a[^>]+href="([^"]*/cbb/players/[^"]+)"[^>]*>(.*?)</a>', html, flags=re.S):
        clean_text = re.sub(r"<.*?>", "", text)
        norm = normalize(clean_text)
        if norm == wanted or (len(last) >= 4 and last in norm):
            return f"https://www.sports-reference.com{href}" if href.startswith("/") else href
    return ""


def parse_tables(html: str) -> list[pd.DataFrame]:
    comment_tables = "\n".join(
        comment for comment in re.findall(r"<!--(.*?)-->", html, flags=re.S) if "<table" in comment
    )
    try:
        return pd.read_html(StringIO(f"{html}\n{comment_tables}"), flavor="lxml")
    except ValueError:
        return []


def number(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        text = str(value).strip().replace("%", "")
        if text in {"", "-", "--"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def season_row(tables: list[pd.DataFrame], season: str, team: str) -> dict[str, object]:
    expected_team = normalize(team)
    for table in tables:
        if not {"Season", "Team"}.issubset(set(map(str, table.columns))):
            continue
        for _, row in table.iterrows():
            if str(row.get("Season", "")).strip() != season:
                continue
            team_value = str(row.get("Team", "")).strip()
            if normalize(team_value) != expected_team:
                continue
            return {
                "found": True,
                "team": team_value,
                "games": number(row.get("G")),
                "mpg": number(row.get("MP")),
                "ppg": number(row.get("PTS")),
                "rpg": number(row.get("TRB")),
                "apg": number(row.get("AST")),
            }
    return {"found": False, "team": "", "games": None, "mpg": None, "ppg": None, "rpg": None, "apg": None}


def approx_match(parsed: float | None, expected: object, tol: float) -> str:
    exp = number(expected)
    if parsed is None or exp is None:
        return ""
    return "TRUE" if abs(parsed - exp) <= tol else "FALSE"


def main() -> int:
    data = pd.read_csv(DATASET_PATH)
    d2 = data[data["source_level"].eq("D2")].copy()
    roster_diff_profiles = roster_diff_profile_rows()
    rows = []
    for _, row in d2.iterrows():
        status = "ok"
        notes = []
        profile_url = find_profile_from_school_page(row, roster_diff_profiles)
        html = ""
        cache_path = ""
        parsed = {"found": False, "team": "", "games": None, "mpg": None, "ppg": None, "rpg": None, "apg": None}

        if not profile_url:
            status = "review"
            notes.append("sports_reference_player_profile_not_found_from_outcome_url")
        else:
            try:
                html, cache_path = get_profile_html(profile_url)
                parsed = season_row(parse_tables(html), str(row["first_big_west_season"]), str(row["destination_school"]))
                if not parsed["found"]:
                    status = "mismatch"
                    notes.append("destination_season_team_not_found_on_profile")
            except (HTTPError, URLError, TimeoutError) as error:
                status = "review"
                notes.append(f"fetch_failed:{error}")

        checks = {
            "games": approx_match(parsed["games"], row["big_west_games"], 0.1),
            "mpg": approx_match(parsed["mpg"], row["big_west_mpg"], 0.15),
            "ppg": approx_match(parsed["ppg"], row["big_west_ppg"], 0.15),
            "rpg": approx_match(parsed["rpg"], row["big_west_rpg"], 0.15),
            "apg": approx_match(parsed["apg"], row["big_west_apg"], 0.15),
        }
        for stat, match in checks.items():
            if match == "FALSE":
                status = "mismatch"
                notes.append(f"{stat}_differs")

        rows.append(
            {
                "status": status,
                "player_name": row["player_name"],
                "destination_school": row["destination_school"],
                "first_big_west_season": row["first_big_west_season"],
                "profile_url": profile_url,
                "cache_path": cache_path,
                "profile_team": parsed["team"],
                "dataset_games": row["big_west_games"],
                "parsed_games": parsed["games"],
                "games_match": checks["games"],
                "dataset_mpg": row["big_west_mpg"],
                "parsed_mpg": parsed["mpg"],
                "mpg_match": checks["mpg"],
                "dataset_ppg": row["big_west_ppg"],
                "parsed_ppg": parsed["ppg"],
                "ppg_match": checks["ppg"],
                "dataset_rpg": row["big_west_rpg"],
                "parsed_rpg": parsed["rpg"],
                "rpg_match": checks["rpg"],
                "dataset_apg": row["big_west_apg"],
                "parsed_apg": parsed["apg"],
                "apg_match": checks["apg"],
                "outcome_url": row["outcome_url"],
                "notes": ";".join(notes),
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    mismatches = [row for row in rows if row["status"] == "mismatch"]
    unverified = [row for row in rows if row["status"] == "review"]
    for path, subset in [(MISMATCH_PATH, mismatches), (UNVERIFIED_PATH, unverified)]:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(subset)
    print(json.dumps({
        "d2_rows_checked": len(rows),
        "ok": sum(row["status"] == "ok" for row in rows),
        "confirmed_mismatches": len(mismatches),
        "unverified": len(unverified),
        "audit_path": str(OUTPUT_PATH),
        "mismatch_path": str(MISMATCH_PATH),
        "unverified_path": str(UNVERIFIED_PATH),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
