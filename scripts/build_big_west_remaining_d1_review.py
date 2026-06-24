#!/usr/bin/env python3
"""Classify remaining D1 source-stat misses for review."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from build_big_west_transfer_source_stats import cached_source_school_page, safe_slug
from scrape_phase1_d1_outcomes import parse_table_rows

WORK_QUEUE_PATH = Path("data/big_west_source_stats_work_queue.csv")
OUTPUT_PATH = Path("data/big_west_remaining_d1_review.csv")
REVIEW_NEEDED_PATH = Path("data/big_west_remaining_d1_review_needed.csv")
VC_CACHE_DIR = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/verbalcommits")

OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "priority",
    "source_school",
    "source_school_slug",
    "destination_school",
    "destination_school_slug",
    "expected_source_season",
    "first_big_west_season",
    "has_big_west_outcome",
    "local_cache_status",
    "source_page_status",
    "source_page_url",
    "source_milestones",
    "destination_milestones",
    "source_in_vc_attended",
    "vc_redshirt_at_source_season",
    "classification",
    "recommended_action",
    "needs_user_review",
    "notes",
]

SOURCE_EVENT_TYPES = {
    "COMMITMENT",
    "ENROLLMENT",
    "SIGNING",
    "TRANSFER",
    "WALK_ON",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def season_start(season: str) -> int:
    return int(season.split("-", 1)[0])


def load_profile(slug: str) -> dict:
    path = VC_CACHE_DIR / f"players__{slug}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def milestone_date(milestone: dict) -> str:
    return (milestone.get("milestoneDate") or milestone.get("vcTargetDate") or "")[:10]


def milestone_summary(milestones: list[dict]) -> str:
    parts = []
    for milestone in sorted(milestones, key=milestone_date):
        data = milestone.get("data") or {}
        flags = []
        if data.get("expectedRedshirtFlag") == "TRUE":
            flags.append("expectedRedshirt")
        if data.get("formerWalkOn") == "TRUE":
            flags.append("formerWalkOn")
        suffix = f" ({', '.join(flags)})" if flags else ""
        parts.append(
            f"{milestone_date(milestone)} {milestone.get('milestoneType','')} "
            f"{milestone.get('schoolName','')}{suffix}".strip()
        )
    return " | ".join(parts)


def school_milestones(profile: dict, school_name: str) -> list[dict]:
    target = normalize(school_name)
    return [
        milestone
        for milestone in profile.get("milestones", [])
        if normalize(milestone.get("schoolName", "")) == target
    ]


def source_attended(profile: dict, school_name: str) -> bool:
    target = normalize(school_name)
    return any(
        normalize(school.get("name", "")) == target
        for school in (profile.get("data") or {}).get("allSchoolsAttended", [])
    )


def has_redshirt_in_source_season(milestones: list[dict], expected_season: str) -> bool:
    start = season_start(expected_season)
    for milestone in milestones:
        date = milestone_date(milestone)
        if not date:
            continue
        year = int(date[:4])
        if milestone.get("milestoneType") == "REDSHIRT" and year in {start, start + 1}:
            return True
        data = milestone.get("data") or {}
        if data.get("expectedRedshirtFlag") == "TRUE" and year in {start, start + 1}:
            return True
    return False


def source_page_evidence(row: dict[str, str]) -> tuple[str, str, bool]:
    cached_page = cached_source_school_page(row["source_school_slug"], row["expected_source_season"])
    if not cached_page:
        return "not_cached", "", False

    path, source_url = cached_page
    rows = parse_table_rows(path.read_text(encoding="utf-8"), "players_per_game")
    target = normalize(row["player_name"]).replace(" ", "")
    has_player = any(normalize(stat.get("name_display", "")).replace(" ", "") == target for stat in rows)
    return "cached_player_found" if has_player else "cached_no_player_row", source_url, has_player


def classify(row: dict[str, str]) -> dict[str, str]:
    profile = load_profile(row["player_slug"])
    source_milestones = school_milestones(profile, row["source_school"])
    destination_milestones = school_milestones(profile, row["destination_school"])
    attended = source_attended(profile, row["source_school"])
    redshirt = has_redshirt_in_source_season(source_milestones, row["expected_source_season"])
    page_status, source_url, has_player = source_page_evidence(row)
    event_types = {milestone.get("milestoneType", "") for milestone in source_milestones}
    has_source_event = bool(event_types & SOURCE_EVENT_TYPES)
    offer_only = bool(source_milestones) and not has_source_event

    if row["priority"] == "5":
        classification = "future_transfer_not_current_model"
        recommended_action = "defer_until_2026_27_outcomes_exist"
        needs_user_review = "FALSE"
        notes = "Future Big West season; exclude from current training set."
    elif row["source_school"] == "Princeton" and row["expected_source_season"] == "2020-21":
        classification = "canceled_source_season"
        recommended_action = "mark_no_source_stats"
        needs_user_review = "FALSE"
        notes = "Princeton/Ivy League did not play 2020-21; no source stat row expected."
    elif redshirt:
        classification = "likely_redshirt_no_source_stats"
        recommended_action = "mark_no_source_stats"
        needs_user_review = "FALSE"
        notes = "VC has redshirt/expected-redshirt evidence during the expected source season."
    elif has_player:
        classification = "parser_miss"
        recommended_action = "rerun_source_builder_or_patch_name_match"
        needs_user_review = "FALSE"
        notes = "Cached source page appears to contain the player."
    elif offer_only:
        classification = "source_school_mismatch_or_offer_only"
        recommended_action = "human_confirm_source_school"
        needs_user_review = "TRUE"
        notes = "VC has only offer-type evidence for the listed source school."
    elif has_source_event or attended:
        classification = "likely_no_source_stats_at_listed_school"
        recommended_action = "mark_no_source_stats_or_confirm_redshirt"
        needs_user_review = "FALSE"
        notes = "Listed source school is supported by VC, but Sports Reference school page has no player row."
    elif not profile:
        classification = "missing_vc_profile"
        recommended_action = "human_confirm_source_school"
        needs_user_review = "TRUE"
        notes = "No cached VC profile was found for this player slug."
    else:
        classification = "source_school_not_supported_by_vc_profile"
        recommended_action = "human_confirm_source_school"
        needs_user_review = "TRUE"
        notes = "Cached VC profile does not support the listed source school."

    return {
        "player_name": row["player_name"],
        "player_slug": row["player_slug"],
        "priority": row["priority"],
        "source_school": row["source_school"],
        "source_school_slug": safe_slug(row["source_school_slug"]),
        "destination_school": row["destination_school"],
        "destination_school_slug": row["destination_school_slug"],
        "expected_source_season": row["expected_source_season"],
        "first_big_west_season": row["first_big_west_season"],
        "has_big_west_outcome": row["has_big_west_outcome"],
        "local_cache_status": row["local_cache_status"],
        "source_page_status": page_status,
        "source_page_url": source_url,
        "source_milestones": milestone_summary(source_milestones),
        "destination_milestones": milestone_summary(destination_milestones),
        "source_in_vc_attended": "TRUE" if attended else "FALSE",
        "vc_redshirt_at_source_season": "TRUE" if redshirt else "FALSE",
        "classification": classification,
        "recommended_action": recommended_action,
        "needs_user_review": needs_user_review,
        "notes": notes,
    }


def main() -> int:
    with WORK_QUEUE_PATH.open(newline="", encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if row["source_level"] == "D1"]

    output_rows = [classify(row) for row in rows]
    review_rows = [row for row in output_rows if row["needs_user_review"] == "TRUE"]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    with REVIEW_NEEDED_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Wrote {len(output_rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(review_rows)} rows to {REVIEW_NEEDED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
