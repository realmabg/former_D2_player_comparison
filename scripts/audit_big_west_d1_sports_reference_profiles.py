#!/usr/bin/env python3
"""Audit D1-to-Big-West rows against cached Sports Reference player profiles."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


DATASET_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
OUTPUT_PATH = Path("data/big_west_d1_sports_reference_profile_audit.csv")
MISMATCH_PATH = Path("data/big_west_d1_sports_reference_profile_confirmed_mismatches.csv")
UNVERIFIED_PATH = Path("data/big_west_d1_sports_reference_profile_unverified.csv")

CACHE_DIRS = [
    Path("data/cache/sports_reference_d1_profile_audit"),
    Path("data/cache/sports_reference_review"),
    Path("data/cache/sports_reference_roster_diff_profiles"),
]
SCHOOL_CACHE_DIR = Path("data/cache/sports_reference_source_schools")
ROSTER_DIFF_AUDIT_PATHS = [
    Path("data/big_west_sports_reference_roster_diff_audit.csv"),
    Path("data/wcc_sports_reference_roster_diff_audit.csv"),
]


TEAM_ALIASES = {
    "alcorn st": "alcorn state",
    "cal": "california",
    "cal baptist": "california baptist",
    "cal st bakersfield": "cal state bakersfield",
    "cal st fullerton": "cal state fullerton",
    "cal st northridge": "cal state northridge",
    "central ark": "central arkansas",
    "brigham young": "byu",
    "byu": "byu",
    "coastal caro": "coastal carolina",
    "cal state bakersfield": "cal state bakersfield",
    "cal state fullerton": "cal state fullerton",
    "cal state northridge": "cal state northridge",
    "california baptist": "california baptist",
    "california irvine": "uc irvine",
    "california riverside": "uc riverside",
    "california san diego": "uc san diego",
    "california santa barbara": "uc santa barbara",
    "boise st": "boise state",
    "colorado st": "colorado state",
    "eastern ill": "eastern illinois",
    "eastern wash": "eastern washington",
    "fdu": "fairleigh dickinson",
    "fresno st": "fresno state",
    "gcu": "grand canyon",
    "grand canyon": "grand canyon",
    "indiana st": "indiana state",
    "long beach st": "long beach state",
    "loyola il": "loyola chicago",
    "montana st": "montana state",
    "murray st": "murray state",
    "norfolk st": "norfolk state",
    "oregon st": "oregon state",
    "portland st": "portland state",
    "sacramento st": "sacramento state",
    "saint mary s ca": "saint mary s",
    "saint marys ca": "saint mary s",
    "san diego st": "san diego state",
    "south carolina st": "south carolina state",
    "south fla": "south florida",
    "southern u": "southern",
    "st mary s ca": "saint mary s",
    "tennessee st": "tennessee state",
    "tamucc": "texas a m corpus christi",
    "texas a m corpus christi": "texas a m corpus christi",
    "texas a mcorpus christi": "texas a m corpus christi",
    "texas st": "texas state",
    "unc": "north carolina",
    "ucsb": "uc santa barbara",
    "uconn": "connecticut",
    "uc davis": "uc davis",
    "uc irvine": "uc irvine",
    "uc riverside": "uc riverside",
    "uc san diego": "uc san diego",
    "uc santa barbara": "uc santa barbara",
    "utah st": "utah state",
    "washington st": "washington state",
    "wichita st": "wichita state",
}

PLAYER_ALIASES = {
    "aleks szymczyk": {"aleksander szymczyk"},
    "ben griscti": {"benjamin griscti"},
    "carl daughtery": {"carl daugherty"},
    "dre bullock": {"quandre bullock"},
    "isa silva": {"isael silva"},
    "john square": {"john mikey square"},
    "josh o garro": {"joshua o garro"},
    "kieves turner": {"deuce turner"},
    "marqui worthy": {"marqui worthy jr"},
    "marqui worthy jr": {"marqui worthy"},
    "ronald jessamy": {"ron jessamy"},
    "carl daughtery jr": {"carl daugherty"},
    "john square jr": {"john mikey square"},
    "shay johnson": {"demarshay johnson"},
    "shay johnson jr": {"demarshay johnson"},
    "tj wainwright": {"t j wainwright"},
}

PLAYER_PROFILE_OVERRIDES = {
    "a j george": "https://www.sports-reference.com/cbb/players/aj-george-1.html",
    "aj george": "https://www.sports-reference.com/cbb/players/aj-george-1.html",
    "j p moorman ii": "https://www.sports-reference.com/cbb/players/jp-moorman-1.html",
    "j p moorman": "https://www.sports-reference.com/cbb/players/jp-moorman-1.html",
}


def normalize(value: object) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()
    return TEAM_ALIASES.get(text, text)


def season_to_year(season: str) -> str:
    start = str(season).split("-", 1)[0]
    return str(int(start) + 1)


def school_cache_path(url: str) -> Path | None:
    match = re.search(r"/schools/([^/]+)/men/(\d{4})\.html", str(url))
    if not match:
        return None
    school, year = match.groups()
    for suffix in [".html", ".json"]:
        path = SCHOOL_CACHE_DIR / f"{school}_{year}{suffix}"
        if path.exists():
            return path
    return None


def url_slug(url: str) -> str:
    name = Path(urlparse(url).path).name
    return name.removesuffix(".html")


def profile_cache_path(profile_url: str) -> Path | None:
    slug = url_slug(profile_url)
    candidates = []
    for cache_dir in CACHE_DIRS:
        candidates.append(cache_dir / f"{slug}.html")
        if slug.endswith("-1"):
            candidates.append(cache_dir / f"{slug[:-2]}.html")
    for path in candidates:
        if path.exists():
            return path
    return None


def profile_url_from_roster_diff_audits(row: pd.Series) -> str:
    wanted = normalize(row["player_name"])
    wanted_names = {wanted, *PLAYER_ALIASES.get(wanted, set())}
    destination = normalize(row["destination_school"])
    source = normalize(row["source_school"])
    candidates = []
    for path in ROSTER_DIFF_AUDIT_PATHS:
        if not path.exists():
            continue
        audit = pd.read_csv(path)
        for _, audit_row in audit.iterrows():
            url = str(audit_row.get("sports_reference_player_url", ""))
            if "/cbb/players/" not in url:
                continue
            player_values = {
                normalize(audit_row.get("player_name", "")),
                normalize(audit_row.get("player_key", "")),
            }
            if not (player_values & wanted_names):
                continue
            audit_destination = normalize(audit_row.get("destination_school", ""))
            audit_prior = normalize(audit_row.get("profile_prior_school", ""))
            if audit_destination in {destination, source} or audit_prior in {destination, source}:
                candidates.append(url)
    unique = sorted(set(candidates))
    return unique[0] if len(unique) == 1 else ""


def page_html(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix == ".json":
        return ""
    return text


def tables_from_html(path: Path) -> list[pd.DataFrame]:
    html = page_html(path)
    if not html:
        return []
    # Sports Reference sometimes hides tables inside HTML comments.
    comment_tables = "\n".join(
        comment for comment in re.findall(r"<!--(.*?)-->", html, flags=re.S) if "<table" in comment
    )
    html = f"{html}\n{comment_tables}"
    try:
        return pd.read_html(StringIO(html))
    except ValueError:
        return []


def find_profile_url_from_school_page(row: pd.Series) -> str:
    source_url = str(row.get("source_url", ""))
    if "/players/" in source_url:
        return source_url
    wanted = normalize(row["player_name"])
    if wanted in PLAYER_PROFILE_OVERRIDES:
        return PLAYER_PROFILE_OVERRIDES[wanted]

    for url_column in ["source_url", "outcome_url"]:
        cache_path = school_cache_path(str(row.get(url_column, "")))
        if not cache_path or cache_path.suffix != ".html":
            continue
        html = page_html(cache_path)
        if not html:
            continue
        wanted_names = {wanted, *PLAYER_ALIASES.get(wanted, set())}
        player_links = []
        for href, text in re.findall(r'<a[^>]+href="([^"]*/cbb/players/[^"]+)"[^>]*>(.*?)</a>', html, flags=re.S):
            clean_text = re.sub(r"<.*?>", "", text)
            norm = normalize(clean_text)
            player_links.append((href, norm))
            if norm in wanted_names:
                if href.startswith("/"):
                    return f"https://www.sports-reference.com{href}"
                return href
        wanted_parts = wanted.split()
        last_name = wanted_parts[-1] if wanted_parts else ""
        if len(last_name) >= 4:
            last_matches = [
                href
                for href, norm in player_links
                if norm.split() and norm.split()[-1] == last_name
            ]
            if len(set(last_matches)) == 1:
                href = last_matches[0]
                if href.startswith("/"):
                    return f"https://www.sports-reference.com{href}"
                return href
    return profile_url_from_roster_diff_audits(row)


def profile_rows(profile_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for table in tables_from_html(profile_path):
        if not {"Season", "Team"}.issubset(set(map(str, table.columns))):
            continue
        for _, table_row in table.iterrows():
            season = str(table_row.get("Season", "")).strip()
            team = str(table_row.get("Team", "")).strip()
            if not re.match(r"^\d{4}-\d{2}$", season) or not team or team.lower() == "career":
                continue
            rows.append({"season": season, "team": team, "team_norm": normalize(team)})
    # Deduplicate because per-game/totals tables repeat seasons.
    deduped = []
    seen = set()
    for row in rows:
        key = (row["season"], row["team_norm"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def matching_team(rows: list[dict[str, str]], season: str, team: str) -> tuple[bool, str]:
    expected = normalize(team)
    teams = [row["team"] for row in rows if row["season"] == season]
    norms = [normalize(team_value) for team_value in teams]
    return expected in norms, "; ".join(teams)


def main() -> int:
    data = pd.read_csv(DATASET_PATH)
    d1 = data[data["source_level"].eq("D1")].copy()
    audit_rows = []

    for _, row in d1.iterrows():
        profile_url = find_profile_url_from_school_page(row)
        profile_path = profile_cache_path(profile_url) if profile_url else None
        status = "ok"
        notes = []
        source_profile_team = ""
        destination_profile_team = ""
        source_match = ""
        destination_match = ""

        if not profile_url:
            status = "review"
            notes.append("no_player_profile_link_found_in_cached_school_pages")
        elif not profile_path:
            status = "review"
            notes.append("player_profile_not_cached")
        else:
            rows = profile_rows(profile_path)
            if not rows:
                status = "review"
                notes.append("cached_profile_has_no_parseable_season_rows")
            else:
                source_ok, source_profile_team = matching_team(rows, str(row["source_season"]), str(row["source_school"]))
                dest_ok, destination_profile_team = matching_team(
                    rows,
                    str(row["first_big_west_season"]),
                    str(row["destination_school"]),
                )
                source_match = "TRUE" if source_ok else "FALSE"
                destination_match = "TRUE" if dest_ok else "FALSE"
                if not source_ok:
                    status = "mismatch"
                    notes.append("source_school_or_source_season_not_on_profile")
                if not dest_ok:
                    status = "mismatch"
                    notes.append("destination_school_or_big_west_season_not_on_profile")

        audit_rows.append(
            {
                "status": status,
                "player_name": row["player_name"],
                "source_school_dataset": row["source_school"],
                "source_season_dataset": row["source_season"],
                "source_profile_team_same_season": source_profile_team,
                "source_match": source_match,
                "destination_school_dataset": row["destination_school"],
                "first_big_west_season_dataset": row["first_big_west_season"],
                "destination_profile_team_same_season": destination_profile_team,
                "destination_match": destination_match,
                "profile_url": profile_url,
                "profile_cache_path": str(profile_path or ""),
                "source_url": row["source_url"],
                "outcome_url": row["outcome_url"],
                "notes": ";".join(notes),
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)

    mismatches = [row for row in audit_rows if row["status"] == "mismatch"]
    unverified = [row for row in audit_rows if row["status"] == "review"]
    with MISMATCH_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(mismatches)
    with UNVERIFIED_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(unverified)

    print(json.dumps({
        "d1_rows_checked": len(audit_rows),
        "ok": sum(row["status"] == "ok" for row in audit_rows),
        "confirmed_mismatches": len(mismatches),
        "unverified": len(unverified),
        "audit_path": str(OUTPUT_PATH),
        "mismatch_path": str(MISMATCH_PATH),
        "unverified_path": str(UNVERIFIED_PATH),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
