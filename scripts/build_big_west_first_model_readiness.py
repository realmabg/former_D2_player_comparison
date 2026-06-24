#!/usr/bin/env python3
"""Write first-model D1/D2 readiness, exclusion, and manual-check files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MODELING_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
FINDINGS_PATH = Path("data/big_west_historical_transfer_findings.csv")
SUMMARY_PATH = Path("data/big_west_first_model_readiness_summary.csv")
EXCLUSIONS_PATH = Path("data/big_west_first_model_exclusions.csv")
MANUAL_CHECK_PATH = Path("data/big_west_first_model_manual_check.csv")

FIRST_MODEL_LEVELS = {"D1", "D2"}

EXCLUDE_ACTIONS = {
    "exclude_out_of_first_model_scope",
    "exclude_or_mark_no_source_stats",
    "exclude_or_mark_no_big_west_stats",
}

MANUAL_ACTIONS = {
    "confirm_no_big_west_stats_or_find_alternate_official_page",
    "manual_lookup",
    "manual_parse_official_school_outcome_row",
}


def main() -> int:
    modeling = pd.read_csv(MODELING_PATH)
    findings = pd.read_csv(FINDINGS_PATH)
    findings = findings[findings["source_level"].isin(FIRST_MODEL_LEVELS)].copy()

    exclusions = findings[findings["next_action"].isin(EXCLUDE_ACTIONS)].copy()
    manual = findings[findings["next_action"].isin(MANUAL_ACTIONS)].copy()

    manual["manual_question"] = manual["next_action"].map(
        {
            "confirm_no_big_west_stats_or_find_alternate_official_page": (
                "Confirm this player had no recorded Big West stats, or provide alternate outcome stats."
            ),
            "manual_lookup": "Confirm source/outcome status manually.",
            "manual_parse_official_school_outcome_row": (
                "Official page had name text but no parseable cumulative row; provide stats or confirm no stats."
            ),
        }
    )

    summary_rows = [
        {
            "metric": "model_ready_rows",
            "value": int(len(modeling[modeling["source_level"].isin(FIRST_MODEL_LEVELS)])),
        },
        {
            "metric": "model_ready_d1_rows",
            "value": int((modeling["source_level"] == "D1").sum()),
        },
        {
            "metric": "model_ready_d2_rows",
            "value": int((modeling["source_level"] == "D2").sum()),
        },
        {
            "metric": "confirmed_exclusion_rows",
            "value": int(len(exclusions)),
        },
        {
            "metric": "manual_check_rows",
            "value": int(len(manual)),
        },
    ]
    for action, count in findings["next_action"].value_counts().sort_index().items():
        summary_rows.append({"metric": f"next_action:{action}", "value": int(count)})

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    exclusions.to_csv(EXCLUSIONS_PATH, index=False)
    manual.to_csv(MANUAL_CHECK_PATH, index=False)

    print(f"Wrote {len(summary)} summary rows to {SUMMARY_PATH}")
    print(f"Wrote {len(exclusions)} exclusion rows to {EXCLUSIONS_PATH}")
    print(f"Wrote {len(manual)} manual-check rows to {MANUAL_CHECK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
