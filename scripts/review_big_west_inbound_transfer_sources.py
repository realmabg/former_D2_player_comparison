#!/usr/bin/env python3
"""Review unresolved Big West inbound-transfer candidates with Sports Reference."""

from __future__ import annotations

import csv
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus

from scrape_phase1_d1_outcomes import parse_table_rows

VC_CACHE_DIR = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/verbalcommits")
INPUT_PATH = Path("data/big_west_inbound_transfers_needs_review.csv")
OUTPUT_PATH = Path("data/big_west_inbound_transfers_review_findings.csv")
SR_CACHE_DIR = Path("data/cache/sports_reference_review")
SPORTS_REFERENCE_SEARCH = "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}"
USER_AGENT = "Mozilla/5.0 big-west-transfer-review"

DESTINATION_NAMES = {
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

OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "destination_school",
    "destination_school_slug",
    "target_event_date",
    "sports_reference_url",
    "sports_reference_rows",
    "finding",
    "recommended_action",
    "resolved_source_school",
    "resolved_source_level",
    "resolved_source_conference",
    "notes",
]


def parse_vc_date(value: str | None) -> str:
    return (value or "")[:10]


def start_year_from_season(season: str) -> int:
    match = re.match(r"^(\d{4})-\d{2}$", season or "")
    return int(match.group(1)) if match else 9999


def season_from_date(value: str) -> str:
    year = int(value[:4])
    return f"{year}-{str(year + 1)[-2:]}"


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(value).lower()).strip()


def cache_name(slug: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", slug)
    return f"{safe}.html"


def canonical_url(page_html: str, final_url: str) -> str:
    match = re.search(r'<link rel="canonical" href="([^"]+/cbb/players/[^"]+)"', page_html)
    return html.unescape(match.group(1)).strip() if match else final_url


def sports_reference_page(player_name: str, player_slug: str) -> tuple[str, str]:
    SR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    html_path = SR_CACHE_DIR / cache_name(player_slug)
    meta_path = SR_CACHE_DIR / f"{html_path.stem}.json"
    if html_path.exists() and meta_path.exists():
        return html_path.read_text(encoding="utf-8"), json.loads(meta_path.read_text()).get("url", "")

    request = urllib.request.Request(
        SPORTS_REFERENCE_SEARCH.format(query=quote_plus(player_name)),
        headers={"User-Agent": USER_AGENT},
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        page_html = response.read().decode("utf-8", errors="replace")
        final_url = response.geturl()
    url = canonical_url(page_html, final_url)
    html_path.write_text(page_html, encoding="utf-8")
    meta_path.write_text(json.dumps({"url": url, "final_url": final_url}, indent=2), encoding="utf-8")
    time.sleep(3.0)
    return page_html, url


def load_profile(player_slug: str) -> dict:
    return json.loads((VC_CACHE_DIR / f"players__{player_slug}.json").read_text(encoding="utf-8"))


def attended_school(profile: dict, school_name: str) -> tuple[str, str]:
    target = normalize(school_name)
    for school in (profile.get("data") or {}).get("allSchoolsAttended", []):
        if normalize(school.get("name", "")) == target:
            return school.get("competitiveLevel", ""), school.get("conferenceName", "")
    return "", ""


def summarize_rows(rows: list[dict[str, str]]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f"{row.get('year_id','')} {row.get('team_name_abbr','')} "
            f"{row.get('games','')}g {row.get('mp_per_g','')}mpg {row.get('pts_per_g','')}ppg"
        )
    return " | ".join(parts)


def review_row(row: dict[str, str]) -> dict[str, str]:
    player_name = row["player_name"]
    player_slug = row["player_slug"]
    destination_slug = row["destination_school_slug"]
    destination_school = DESTINATION_NAMES.get(destination_slug, destination_slug)
    target_season = season_from_date(row["target_event_date"])
    target_start = start_year_from_season(target_season)
    profile = load_profile(player_slug)

    try:
        page_html, sr_url = sports_reference_page(player_name, player_slug)
        sr_rows = parse_table_rows(page_html, "players_per_game")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        sr_url = ""
        sr_rows = []
        sr_error = str(error)
    else:
        sr_error = ""

    prior_rows = [
        sr_row
        for sr_row in sr_rows
        if start_year_from_season(sr_row.get("year_id", "")) < target_start
    ]
    destination_rows = [
        sr_row
        for sr_row in sr_rows
        if normalize(sr_row.get("team_name_abbr", "")) == normalize(destination_school)
    ]
    later_rows = [
        sr_row
        for sr_row in sr_rows
        if start_year_from_season(sr_row.get("year_id", "")) > target_start
    ]

    if prior_rows:
        source = prior_rows[-1]
        level, conference = attended_school(profile, source.get("team_name_abbr", ""))
        return {
            "player_name": player_name,
            "player_slug": player_slug,
            "destination_school": destination_school,
            "destination_school_slug": destination_slug,
            "target_event_date": row["target_event_date"],
            "sports_reference_url": sr_url,
            "sports_reference_rows": summarize_rows(sr_rows),
            "finding": "prior_college_stats_found",
            "recommended_action": "include_or_resolve_source",
            "resolved_source_school": source.get("team_name_abbr", ""),
            "resolved_source_level": level or "D1",
            "resolved_source_conference": conference or source.get("conf_abbr", ""),
            "notes": f"Sports Reference has prior row before {target_season}.",
        }

    if destination_rows and later_rows and not prior_rows:
        return {
            "player_name": player_name,
            "player_slug": player_slug,
            "destination_school": destination_school,
            "destination_school_slug": destination_slug,
            "target_event_date": row["target_event_date"],
            "sports_reference_url": sr_url,
            "sports_reference_rows": summarize_rows(sr_rows),
            "finding": "big_west_first_then_transferred_out",
            "recommended_action": "exclude_not_inbound_transfer",
            "resolved_source_school": "",
            "resolved_source_level": "",
            "resolved_source_conference": "",
            "notes": f"First college row is {destination_school}; later rows are outbound transfer history.",
        }

    if destination_rows and not prior_rows:
        return {
            "player_name": player_name,
            "player_slug": player_slug,
            "destination_school": destination_school,
            "destination_school_slug": destination_slug,
            "target_event_date": row["target_event_date"],
            "sports_reference_url": sr_url,
            "sports_reference_rows": summarize_rows(sr_rows),
            "finding": "big_west_first_no_prior_stats",
            "recommended_action": "exclude_not_inbound_transfer",
            "resolved_source_school": "",
            "resolved_source_level": "",
            "resolved_source_conference": "",
            "notes": f"No Sports Reference row before {target_season}.",
        }

    if later_rows and not sr_rows:
        finding = "sports_reference_not_found"
    elif later_rows:
        finding = "later_stats_only"
    else:
        finding = "unresolved"

    return {
        "player_name": player_name,
        "player_slug": player_slug,
        "destination_school": destination_school,
        "destination_school_slug": destination_slug,
        "target_event_date": row["target_event_date"],
        "sports_reference_url": sr_url,
        "sports_reference_rows": summarize_rows(sr_rows),
        "finding": finding,
        "recommended_action": "manual_review",
        "resolved_source_school": "",
        "resolved_source_level": "",
        "resolved_source_conference": "",
        "notes": sr_error or f"No prior/destination Sports Reference row resolved for {target_season}.",
    }


def main() -> int:
    with INPUT_PATH.open(newline="") as file:
        input_rows = list(csv.DictReader(file))
    findings = [review_row(row) for row in input_rows]
    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(findings)
    print(f"Wrote {len(findings)} review findings to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
