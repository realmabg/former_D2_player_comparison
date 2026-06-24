#!/usr/bin/env python3
"""Summarize evidence for completed-season Big West modeling gaps."""

from __future__ import annotations

import csv
from pathlib import Path

HISTORICAL_NEEDED_PATH = Path("data/big_west_historical_transfer_rows_needed.csv")
SOURCE_STATS_PATH = Path("data/big_west_transfer_source_stats.csv")
OUTCOMES_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
SCHOOL_OUTCOMES_PATH = Path("data/big_west_transfer_school_outcomes.csv")
SR_OUTCOMES_MISSING_PATH = Path("data/big_west_transfer_d1_outcomes_missing.csv")
SCHOOL_OUTCOMES_MISSING_PATH = Path("data/big_west_transfer_school_outcomes_missing.csv")
D1_REVIEW_PATH = Path("data/big_west_remaining_d1_review.csv")
OUTPUT_PATH = Path("data/big_west_historical_transfer_findings.csv")

MANUAL_OUTCOME_OVERRIDES = {
    ("juan-munoz", "Hawaii", "2021-22"): {
        "outcome_status": "confirmed_injury_no_big_west_stats",
        "outcome_evidence": "User confirmed Juan Munoz was injured in 2021-22 and 2022-23.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("logan-mclaughlin", "Cal Poly", "2022-23"): {
        "outcome_status": "confirmed_out_of_scope_juco_path",
        "outcome_evidence": (
            "User confirmed Logan McLaughlin played at JUCO in 2022-23 and was injured in 2023-24."
        ),
        "next_action": "exclude_out_of_first_model_scope",
    },
    ("pablo-tamba", "UC Davis", "2022-23"): {
        "outcome_status": "confirmed_out_of_scope_juco_path",
        "outcome_evidence": "User confirmed Pablo Tamba was at JUCO in 2022-23.",
        "next_action": "exclude_out_of_first_model_scope",
    },
    ("austin-johnson2", "Long Beach State", "2023-24"): {
        "outcome_status": "confirmed_dnp_no_big_west_stats",
        "outcome_evidence": "User confirmed Austin Johnson DNP in 2023-24.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("marsalis-roberson", "UC Davis", "2023-24"): {
        "outcome_status": "confirmed_injury_dnp_no_big_west_stats",
        "outcome_evidence": "User confirmed Marsalis Roberson was injured/DNP in 2023-24.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("pj-fuller", "Cal State Northridge", "2023-24"): {
        "outcome_status": "confirmed_dnp_no_big_west_stats",
        "outcome_evidence": "User confirmed P.J. Fuller II DNP in 2023-24.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("quincy-mcgriff", "Cal State Northridge", "2023-24"): {
        "outcome_status": "confirmed_dnp_no_big_west_stats",
        "outcome_evidence": "User confirmed Quincy McGriff was at JUCO in 2021-22 and DNP in 2023-24.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("devin-tillis", "UC Irvine", "2021-22"): {
        "outcome_status": "confirmed_redshirt_no_big_west_stats",
        "outcome_evidence": "User confirmed Devin Tillis redshirted in 2021-22.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("quinton-webb", "Cal State Northridge", "2025-26"): {
        "outcome_status": "confirmed_redshirt_no_big_west_stats",
        "outcome_evidence": "User confirmed Quinton Webb redshirted in 2025-26.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("grant-gondrezick", "Long Beach State", "2025-26"): {
        "outcome_status": "confirmed_dnp_no_big_west_stats",
        "outcome_evidence": (
            "User confirmed Grant Gondrezick II DNP in 2023-24 and 2025-26; "
            "Sports Reference URL provided for source stats."
        ),
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("tanner-cuff", "Hawaii", "2025-26"): {
        "outcome_status": "confirmed_injury_dnp_no_big_west_stats",
        "outcome_evidence": (
            "User confirmed Tanner Cuff played at Evansville in 2023-24 and 2024-25, "
            "had D2 seasons before Evansville, and had an ACL injury/DNP in 2025-26."
        ),
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("tyson-dunn", "UC San Diego", "2025-26"): {
        "outcome_status": "confirmed_injury_dnp_no_big_west_stats",
        "outcome_evidence": "User confirmed Tyson Dunn was in Canada from 2021-24 and injury/DNP in 2025-26.",
        "next_action": "exclude_or_mark_no_big_west_stats",
    },
    ("isaiah-moses", "UC Riverside", "2022-23"): {
        "outcome_status": "confirmed_out_of_scope_juco_path",
        "outcome_evidence": (
            "User confirmed Isaiah Moses redshirted in 2021-22 and was at JUCO in 2022-23."
        ),
        "next_action": "exclude_out_of_first_model_scope",
    },
}

MANUAL_SOURCE_OVERRIDES = {
    ("guzmn-vasili", "Cal Poly", "2024-25"): {
        "source_status": "confirmed_redshirt_no_source_stats",
        "source_evidence": "Known D2 redshirt/no-stat source case.",
        "next_action": "exclude_or_mark_no_source_stats",
    },
    ("logan-mclaughlin", "Cal Poly", "2022-23"): {
        "source_status": "confirmed_out_of_scope_juco_path",
        "source_evidence": "User confirmed the listed pathway should run through JUCO in 2022-23.",
        "next_action": "exclude_out_of_first_model_scope",
    },
    ("pablo-tamba", "UC Davis", "2022-23"): {
        "source_status": "confirmed_out_of_scope_juco_path",
        "source_evidence": "User confirmed Pablo Tamba was at JUCO in 2022-23.",
        "next_action": "exclude_out_of_first_model_scope",
    },
    ("isaiah-moses", "UC Riverside", "2022-23"): {
        "source_status": "confirmed_out_of_scope_juco_path",
        "source_evidence": "User confirmed Isaiah Moses redshirted in 2021-22 and was at JUCO in 2022-23.",
        "next_action": "exclude_out_of_first_model_scope",
    },
}


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school"], row["first_big_west_season"])


def slug_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school_slug"], row["first_big_west_season"])


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> int:
    historical = read_rows(HISTORICAL_NEEDED_PATH)
    source_rows = {slug_key(row): row for row in read_rows(SOURCE_STATS_PATH)}
    sr_outcomes = {slug_key(row): row for row in read_rows(OUTCOMES_PATH)}
    school_outcomes = {slug_key(row): row for row in read_rows(SCHOOL_OUTCOMES_PATH)}
    sr_missing = {slug_key(row): row for row in read_rows(SR_OUTCOMES_MISSING_PATH)}
    school_missing = {slug_key(row): row for row in read_rows(SCHOOL_OUTCOMES_MISSING_PATH)}
    d1_review = {slug_key(row): row for row in read_rows(D1_REVIEW_PATH)}

    rows = []
    for row in historical:
        destination_slug = row.get("destination_school_slug", "")
        if not destination_slug:
            # historical gap report intentionally omits slug; recover from matching by public columns.
            destination_slug = ""
        row_key = (
            row["player_slug"],
            row.get("destination_school_slug", ""),
            row["first_big_west_season"],
        )
        # Fall back to destination-name keys for the gap-report rows.
        source_match = next(
            (
                source
                for source_key, source in source_rows.items()
                if source["player_slug"] == row["player_slug"]
                and source["destination_school"] == row["destination_school"]
                and source["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )
        sr_outcome = next(
            (
                outcome
                for outcome_key, outcome in sr_outcomes.items()
                if outcome["player_slug"] == row["player_slug"]
                and outcome["destination_school"] == row["destination_school"]
                and outcome["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )
        school_outcome = next(
            (
                outcome
                for outcome_key, outcome in school_outcomes.items()
                if outcome["player_slug"] == row["player_slug"]
                and outcome["destination_school"] == row["destination_school"]
                and outcome["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )
        sr_miss = next(
            (
                miss
                for miss_key, miss in sr_missing.items()
                if miss["player_slug"] == row["player_slug"]
                and miss["destination_school"] == row["destination_school"]
                and miss["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )
        school_miss = next(
            (
                miss
                for miss_key, miss in school_missing.items()
                if miss["player_slug"] == row["player_slug"]
                and miss["destination_school"] == row["destination_school"]
                and miss["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )
        review = next(
            (
                item
                for item in d1_review.values()
                if item["player_slug"] == row["player_slug"]
                and item["destination_school"] == row["destination_school"]
                and item["first_big_west_season"] == row["first_big_west_season"]
            ),
            None,
        )

        if source_match:
            source_status = "found"
            source_evidence = source_match.get("source_url", "")
        elif review:
            source_status = review["classification"]
            source_evidence = review["notes"]
        elif row["source_level"] == "JUCO":
            source_status = "needs_juco_school_or_realgm_lookup"
            source_evidence = row.get("recommended_next_step", "")
        elif row["source_level"] == "D2":
            source_status = "needs_d2_school_lookup_or_no-stat_confirmation"
            source_evidence = row.get("recommended_next_step", "")
        else:
            source_status = "needs_source_lookup"
            source_evidence = row.get("recommended_next_step", "")

        source_override = MANUAL_SOURCE_OVERRIDES.get(
            (row["player_slug"], row["destination_school"], row["first_big_west_season"])
        )
        if source_override:
            source_status = source_override["source_status"]
            source_evidence = source_override["source_evidence"]

        if sr_outcome:
            outcome_status = "found_sports_reference"
            outcome_evidence = sr_outcome.get("source_url", "")
        elif school_outcome:
            outcome_status = "found_official_school_page"
            outcome_evidence = school_outcome.get("source_url", "")
        elif school_miss:
            outcome_status = f"official_school_missing: {school_miss.get('reason', '')}"
            outcome_evidence = school_miss.get("source_url", "")
        elif sr_miss:
            outcome_status = f"sports_reference_missing: {sr_miss.get('reason', '')}"
            outcome_evidence = sr_miss.get("sports_reference_url", "")
        else:
            outcome_status = "not_required_or_not_checked"
            outcome_evidence = ""

        override = MANUAL_OUTCOME_OVERRIDES.get(
            (row["player_slug"], row["destination_school"], row["first_big_west_season"])
        )
        if override:
            outcome_status = override["outcome_status"]
            outcome_evidence = override["outcome_evidence"]
            next_action = override["next_action"]
        elif source_status == "found" and outcome_status.startswith("found"):
            next_action = "ready_after_rebuild"
        elif source_status in {
            "canceled_source_season",
            "confirmed_redshirt_no_source_stats",
            "likely_no_source_stats_at_listed_school",
            "likely_redshirt_no_source_stats",
        } and outcome_status.startswith("found"):
            next_action = "exclude_or_mark_no_source_stats"
        elif "Found name text but not parseable" in outcome_status:
            next_action = "manual_parse_official_school_outcome_row"
        elif "Could not find player row" in outcome_status:
            next_action = "confirm_no_big_west_stats_or_find_alternate_official_page"
        elif row["source_level"] == "JUCO":
            next_action = "manual_juco_source_stats_then_massey_check"
        else:
            next_action = "manual_lookup"

        rows.append(
            {
                "player_name": row["player_name"],
                "source_school": row["source_school"],
                "source_level": row["source_level"],
                "destination_school": row["destination_school"],
                "first_big_west_season": row["first_big_west_season"],
                "expected_source_season": row.get("expected_source_season", ""),
                "collection_bucket": row["collection_bucket"],
                "source_status": source_status,
                "source_evidence": source_evidence,
                "outcome_status": outcome_status,
                "outcome_evidence": outcome_evidence,
                "next_action": next_action,
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
