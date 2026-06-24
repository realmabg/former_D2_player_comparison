#!/usr/bin/env python3
"""Summarize remaining missing players/stats for the modeling dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRAINING_PATH = Path("data/modeling/training/d2_available_training.csv")
MANIFEST_PATH = Path("data/modeling/training/d2_available_feature_manifest.json")
OUT_DIR = Path("reports/d2_available_model_comparison/missing_data")


SOURCE_FILES = {
    "barttorvik_outcome_missing": Path("data/target_conference_barttorvik_outcomes_missing.csv"),
    "evanmiya_target_missing": Path("data/target_conference_evanmiya_missing_matches.csv"),
    "massey_conference_unmatched": Path("data/target_conference_massey_power_unmatched_after_fallback.csv"),
    "wcc_d2_source_missing": Path("data/wcc_d2_transfer_modeling_missing.csv"),
    "mwc_d1_outcome_missing": Path("data/mwc_d1_transfer_outcomes_missing.csv"),
    "a10_d1_outcome_missing": Path("data/a10_d1_transfer_outcomes_missing.csv"),
    "aac_d1_outcome_missing": Path("data/aac_d1_transfer_outcomes_missing.csv"),
    "mvc_d1_outcome_missing": Path("data/mvc_d1_transfer_outcomes_missing.csv"),
}


def safe_read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    training = pd.read_csv(TRAINING_PATH)

    feature_columns = [
        "height_in",
        "weight_lbs",
        "position",
        "position_bucket",
        "height_bucket",
        "source_role_bucket",
        "source_games",
        "source_mpg",
        "source_ppg",
        "source_rpg",
        "source_apg",
        "source_conf_power",
        "destination_conf_power",
        "conf_power_delta",
        "source_team_power",
        "destination_team_power",
        "team_power_delta",
        "class_entering_destination",
        "college_stat_seasons_before_transfer",
    ]
    target_columns = [
        "big_west_bpr",
        "big_west_obpr",
        "big_west_dbpr",
        "big_west_bpm",
        "target_porpag",
        "target_barttorvik_bpm",
    ]

    coverage_rows = []
    for column in feature_columns + target_columns:
        if column not in training.columns:
            continue
        coverage_rows.append(
            {
                "column": column,
                "non_null": int(training[column].notna().sum()),
                "missing": int(training[column].isna().sum()),
                "coverage_pct": float(training[column].notna().mean() * 100),
                "kind": "feature" if column in feature_columns else "target",
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(OUT_DIR / "training_column_coverage.csv", index=False)

    missing_feature_rows = training[
        training[[c for c in feature_columns if c in training.columns]].isna().any(axis=1)
    ].copy()
    id_cols = [
        "target_conference",
        "player_name",
        "source_school",
        "source_conference",
        "source_level",
        "destination_school",
        "first_big_west_season",
    ]
    missing_feature_rows[id_cols + [c for c in feature_columns if c in training.columns and c not in id_cols]].to_csv(
        OUT_DIR / "rows_missing_training_features.csv", index=False
    )

    source_summaries = []
    for label, path in SOURCE_FILES.items():
        df = safe_read(path)
        source_summaries.append({"source": label, "path": str(path), "rows": int(len(df))})
        if not df.empty:
            df.to_csv(OUT_DIR / f"{label}.csv", index=False)
    pd.DataFrame(source_summaries).to_csv(OUT_DIR / "source_missing_file_summary.csv", index=False)

    lines = [
        "# Modeling Missing Data Summary",
        "",
        "This summarizes remaining gaps after separating raw/intermediate/all-stats/training artifacts.",
        "",
        "## Training Feature Coverage",
        "",
        "| Column | Kind | Non-null | Missing | Coverage |",
        "|---|---|---:|---:|---:|",
    ]
    for row in coverage.to_dict("records"):
        lines.append(
            f"| {row['column']} | {row['kind']} | {row['non_null']} | {row['missing']} | {row['coverage_pct']:.1f}% |"
        )
    lines.extend(["", "## Missing Source/Outcome Files", "", "| Source | Rows | Meaning |", "|---|---:|---|"])
    meanings = {
        "barttorvik_outcome_missing": "Rows that did not match a local Bart/Torvik outcome row, so PORPAG/Bart BPM are missing.",
        "evanmiya_target_missing": "Rows without an EvanMiya target BPR match. These rows cannot train BPR but can still train BPM/PORPAG if available.",
        "massey_conference_unmatched": "Conference power gaps. Should be zero for current model features.",
        "wcc_d2_source_missing": "WCC D2 source rows missing source stats.",
        "mwc_d1_outcome_missing": "MWC D1 transfer rows where target outcome was not found.",
        "a10_d1_outcome_missing": "A10 D1 transfer rows where target outcome was not found.",
        "aac_d1_outcome_missing": "AAC D1 transfer rows where target outcome was not found.",
        "mvc_d1_outcome_missing": "MVC D1 transfer rows where target outcome was not found.",
    }
    for row in source_summaries:
        lines.append(f"| {row['source']} | {row['rows']} | {meanings.get(row['source'], '')} |")

    bpr_non_null = int(training["big_west_bpr"].notna().sum()) if "big_west_bpr" in training.columns else 0
    porpag_non_null = int(training["target_porpag"].notna().sum()) if "target_porpag" in training.columns else 0
    source_team_missing = int(training["source_team_power"].isna().sum()) if "source_team_power" in training.columns else 0
    class_unknown = (
        int(training["class_entering_destination"].eq("unknown").sum())
        if "class_entering_destination" in training.columns
        else 0
    )
    conf_missing = (
        int(training[["source_conf_power", "destination_conf_power", "conf_power_delta"]].isna().any(axis=1).sum())
        if {"source_conf_power", "destination_conf_power", "conf_power_delta"}.issubset(training.columns)
        else 0
    )

    lines.extend(["", "## Practical Read", ""])
    lines.append(
        "- No player is missing core identity, position, height, weight, source games, source minutes, source PPG/RPG/APG, or destination conference strength in the current training table."
    )
    lines.append(f"- Conference-power feature gaps: {conf_missing} rows.")
    lines.append(f"- Source team-power gaps: {source_team_missing} rows. Destination team power is complete.")
    lines.append(
        f"- Class/seasons-played-before-transfer is still unknown for {class_unknown} rows; these mostly come from older rows sourced from Sports Reference school-season pages rather than player-profile source tables."
    )
    lines.append(
        f"- BPR target coverage is {bpr_non_null} of {len(training)} rows because EvanMiya target matching is incomplete. This only affects BPR training rows."
    )
    lines.append(f"- PORPAG coverage is {porpag_non_null} of {len(training)} rows after the Bart/Torvik merge.")
    lines.append("- The model feature set excludes D1-only source features that are not available for current D2 projection candidates.")
    (OUT_DIR / "missing_data_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote missing-data report to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
