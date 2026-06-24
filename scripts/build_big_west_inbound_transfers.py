#!/usr/bin/env python3
"""Build all cached inbound Big West transfers for the D2-transfer timeframe."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VC_CACHE_DIR = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/verbalcommits")
PHASE1_TRANSFERS_PATH = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/phase1_transfers.csv")
OUTPUT_PATH = Path("data/big_west_inbound_transfers.csv")
MISSING_PATH = Path("data/big_west_inbound_transfers_missing.csv")

DESTINATION_MILESTONES = {"COMMITMENT", "SIGNING", "ENROLLMENT"}
SOURCE_MILESTONES = {"TRANSFER", "ENROLLMENT"}
COLLEGE_LEVELS = {"D1", "D2", "D3", "NAIA", "JUCO"}

REVIEWED_NON_TRANSFERS = {
    ("abass-bodija", "uc-riverside"): (
        "Played at UC Riverside in 2024-25, then Fordham in 2025-26; "
        "no prior college source before UCR, so exclude as inbound Big West transfer."
    ),
    ("zion-sensley", "uc-santa-barbara"): (
        "Decommitted from Saint Mary's; did not attend before UC Santa Barbara, "
        "so exclude as an inbound Big West transfer."
    ),
    ("scotty-belnap", "hawaii"): (
        "Committed to Utah Tech, then completed a two-year mission in Argentina "
        "before Hawaii; did not attend Utah Tech, so exclude as an inbound Big West transfer."
    ),
}

OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "destination_school",
    "destination_school_slug",
    "destination_conference",
    "destination_level",
    "source_school",
    "source_school_slug",
    "source_conference",
    "source_level",
    "transfer_year",
    "first_big_west_season",
    "commit_date",
    "signed_date",
    "enrolled_date",
    "target_event_type",
    "target_event_date",
    "source_event_type",
    "source_event_date",
    "pathway_type",
    "position",
    "height",
    "weight",
    "class",
    "hs_grad_year",
    "juco_flag",
    "redshirt_flag",
    "model_training_window",
    "phase1_d2_transfer_match",
    "phase1_model_training_eligible",
    "phase1_review_status",
    "source_url",
]

MISSING_COLUMNS = [
    "player_slug",
    "destination_school_slug",
    "target_event_type",
    "target_event_date",
    "reason",
]


def parse_vc_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_date(value: str | None) -> str:
    parsed = parse_vc_date(value)
    return parsed.date().isoformat() if parsed else ""


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def season_from_start_year(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"


def timeframe() -> tuple[int, int]:
    with PHASE1_TRANSFERS_PATH.open(newline="") as file:
        years = [int(row["transfer_year"]) for row in csv.DictReader(file) if row["transfer_year"].isdigit()]
    return min(years), max(years)


def phase1_lookup() -> dict[tuple[str, str], dict[str, str]]:
    with PHASE1_TRANSFERS_PATH.open(newline="") as file:
        return {
            (row["player_slug"], row["d1_school_slug"]): row
            for row in csv.DictReader(file)
        }


def load_profile(player_slug: str) -> dict[str, Any] | None:
    path = VC_CACHE_DIR / f"players__{player_slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def big_west_school_slugs() -> list[str]:
    slugs = []
    for path in sorted(VC_CACHE_DIR.glob("schools__activity__*.json")):
        slug = path.stem.replace("schools__activity__", "")
        if slug:
            slugs.append(slug)
    return slugs


def activity_player_slugs(school_slug: str) -> list[str]:
    path = VC_CACHE_DIR / f"schools__activity__{school_slug}.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    slugs = []
    for item in items:
        milestone = item.get("milestone") or {}
        if milestone.get("milestoneType") not in DESTINATION_MILESTONES:
            continue
        player_slug = milestone.get("playerSlug")
        if player_slug and player_slug not in seen:
            seen.add(player_slug)
            slugs.append(player_slug)
    return slugs


def destination_events(profile: dict[str, Any], school_slug: str) -> list[dict[str, Any]]:
    events = []
    for milestone in profile.get("milestones", []):
        if milestone.get("schoolSlug") != school_slug:
            continue
        if milestone.get("conferenceSlug") != "big-west":
            continue
        if milestone.get("competitiveLevel") != "D1":
            continue
        if milestone.get("milestoneType") in DESTINATION_MILESTONES:
            events.append(milestone)
    return sorted(events, key=lambda item: parse_vc_date(item.get("milestoneDate")) or datetime.max.replace(tzinfo=timezone.utc))


def prior_source(profile: dict[str, Any], target: dict[str, Any], target_date: datetime) -> dict[str, Any] | None:
    target_school_slug = target.get("schoolSlug")
    candidates = []
    for milestone in profile.get("milestones", []):
        if milestone.get("schoolSlug") == target_school_slug:
            continue
        if milestone.get("competitiveLevel") not in COLLEGE_LEVELS:
            continue
        if milestone.get("milestoneType") not in SOURCE_MILESTONES:
            continue
        event_date = parse_vc_date(milestone.get("milestoneDate"))
        if event_date and event_date <= target_date:
            candidates.append((event_date, milestone))

    if candidates:
        latest = max(candidates, key=lambda item: item[0])[1]
        external_name = (latest.get("data") or {}).get("toExternalSchoolName")
        if external_name:
            for school in (profile.get("data") or {}).get("allSchoolsAttended", []):
                if normalize(school.get("name", "")) == normalize(str(external_name)):
                    return {
                        "milestoneType": "ALL_SCHOOLS_ATTENDED_EXTERNAL",
                        "milestoneDate": latest.get("milestoneDate", ""),
                        "schoolSlug": school.get("slug", ""),
                        "schoolName": school.get("name", ""),
                        "conferenceSlug": school.get("conferenceSlug", ""),
                        "conferenceName": school.get("conferenceName", ""),
                        "competitiveLevel": school.get("competitiveLevel", ""),
                        "data": {},
                    }
        return latest

    schools = []
    for school in (profile.get("data") or {}).get("allSchoolsAttended", []):
        if school.get("slug") == target_school_slug:
            continue
        if school.get("competitiveLevel") in COLLEGE_LEVELS:
            schools.append(school)

    if len(schools) == 1:
        school = schools[0]
        return {
            "milestoneType": "ALL_SCHOOLS_ATTENDED",
            "milestoneDate": "",
            "schoolSlug": school.get("slug", ""),
            "schoolName": school.get("name", ""),
            "conferenceSlug": school.get("conferenceSlug", ""),
            "conferenceName": school.get("conferenceName", ""),
            "competitiveLevel": school.get("competitiveLevel", ""),
            "data": {},
        }
    return None


def has_prior_college_hint(profile: dict[str, Any], target: dict[str, Any], target_date: datetime) -> bool:
    target_school_slug = target.get("schoolSlug")
    for milestone in profile.get("milestones", []):
        if milestone.get("schoolSlug") == target_school_slug:
            continue
        if milestone.get("competitiveLevel") in COLLEGE_LEVELS:
            event_date = parse_vc_date(milestone.get("milestoneDate"))
            if milestone.get("milestoneType") in SOURCE_MILESTONES and event_date and event_date <= target_date:
                return True
    return False


def event_dates(events: list[dict[str, Any]]) -> dict[str, str]:
    dates: dict[str, str] = {}
    for event in events:
        dates[event.get("milestoneType", "")] = fmt_date(event.get("milestoneDate"))
    return dates


def transfer_year(source: dict[str, Any], target_date: datetime) -> int:
    value = (source.get("data") or {}).get("transferYear")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return target_date.year


def pathway_type(source_level: str, destination_level: str, juco_flag: str) -> str:
    if source_level == "D2" and destination_level == "D1":
        return "d2_big_west"
    if source_level == "D1" and destination_level == "D1":
        return "d1_big_west"
    if source_level == "JUCO" or juco_flag == "TRUE":
        return "juco_big_west"
    if source_level:
        return f"{source_level.lower()}_big_west"
    return "unknown_big_west"


def build_row(
    profile: dict[str, Any],
    school_slug: str,
    min_year: int,
    max_year: int,
    phase1_by_player_school: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    events = destination_events(profile, school_slug)
    by_year_school: dict[tuple[int, str], list[dict[str, Any]]] = {}

    for target_event in events:
        if (profile.get("slug", ""), school_slug) in REVIEWED_NON_TRANSFERS:
            continue
        target_date = parse_vc_date(target_event.get("milestoneDate"))
        if not target_date:
            continue
        source = prior_source(profile, target_event, target_date)
        if not source:
            if has_prior_college_hint(profile, target_event, target_date):
                missing.append(
                    {
                        "player_slug": profile.get("slug", ""),
                        "destination_school_slug": school_slug,
                        "target_event_type": target_event.get("milestoneType", ""),
                        "target_event_date": fmt_date(target_event.get("milestoneDate")),
                        "reason": "Prior college source hinted but not resolved",
                    }
                )
            continue
        year = transfer_year(source, target_date)
        by_year_school.setdefault((year, school_slug), []).append(target_event)

    for (year, _), year_events in by_year_school.items():
        if year < min_year or year > max_year:
            continue
        year_events = sorted(year_events, key=lambda item: parse_vc_date(item.get("milestoneDate")) or datetime.max.replace(tzinfo=timezone.utc))
        target_event = next((event for event in year_events if event.get("milestoneType") == "COMMITMENT"), year_events[0])
        target_date = parse_vc_date(target_event.get("milestoneDate"))
        if not target_date:
            continue
        source = prior_source(profile, target_event, target_date)
        if not source:
            continue
        dates = event_dates(year_events)
        player_data = profile.get("data") or {}
        source_level = source.get("competitiveLevel", "")
        destination_level = target_event.get("competitiveLevel", "")
        juco_flag = str(player_data.get("jucoFlag") or "")
        phase1 = phase1_by_player_school.get((profile.get("slug", ""), school_slug), {})
        rows.append(
            {
                "player_name": profile.get("fullName") or f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                "player_slug": profile.get("slug", ""),
                "destination_school": target_event.get("schoolName", ""),
                "destination_school_slug": target_event.get("schoolSlug", ""),
                "destination_conference": target_event.get("conferenceName", ""),
                "destination_level": destination_level,
                "source_school": source.get("schoolName", ""),
                "source_school_slug": source.get("schoolSlug", ""),
                "source_conference": source.get("conferenceName", ""),
                "source_level": source_level,
                "transfer_year": str(year),
                "first_big_west_season": season_from_start_year(year),
                "commit_date": dates.get("COMMITMENT", ""),
                "signed_date": dates.get("SIGNING", ""),
                "enrolled_date": dates.get("ENROLLMENT", ""),
                "target_event_type": target_event.get("milestoneType", ""),
                "target_event_date": fmt_date(target_event.get("milestoneDate")),
                "source_event_type": source.get("milestoneType", ""),
                "source_event_date": fmt_date(source.get("milestoneDate")),
                "pathway_type": pathway_type(source_level, destination_level, juco_flag),
                "position": profile.get("position", ""),
                "height": str(profile.get("heightInches") or 0),
                "weight": str(profile.get("weightLbs") or 0),
                "class": profile.get("eligibilityYear", ""),
                "hs_grad_year": str(profile.get("hsGradYear") or 0),
                "juco_flag": juco_flag,
                "redshirt_flag": str(player_data.get("redshirtFlag") or ""),
                "model_training_window": "FALSE" if year >= 2026 else "TRUE",
                "phase1_d2_transfer_match": "TRUE" if phase1 else "FALSE",
                "phase1_model_training_eligible": phase1.get("model_training_eligible", ""),
                "phase1_review_status": phase1.get("review_status", ""),
                "source_url": f"https://www.verbalcommits.com/players/{profile.get('slug', '')}",
            }
        )

    return rows, missing


def main() -> int:
    min_year, max_year = timeframe()
    phase1_by_player_school = phase1_lookup()
    rows: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []

    for school_slug in big_west_school_slugs():
        for player_slug in activity_player_slugs(school_slug):
            profile = load_profile(player_slug)
            if not profile:
                missing.append(
                    {
                        "player_slug": player_slug,
                        "destination_school_slug": school_slug,
                        "target_event_type": "",
                        "target_event_date": "",
                        "reason": "Player profile missing from cache",
                    }
                )
                continue
            player_rows, player_missing = build_row(
                profile,
                school_slug,
                min_year,
                max_year,
                phase1_by_player_school,
            )
            rows.extend(player_rows)
            missing.extend(player_missing)

    deduped = {}
    for row in sorted(rows, key=lambda item: (item["player_slug"], item["destination_school_slug"], item["transfer_year"])):
        key = (row["player_slug"], row["destination_school_slug"])
        deduped.setdefault(key, row)
    rows = sorted(
        deduped.values(),
        key=lambda row: (row["transfer_year"], row["destination_school"], row["player_name"]),
    )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MISSING_COLUMNS)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Timeframe: {min_year}-{max_year}")
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} misses to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
