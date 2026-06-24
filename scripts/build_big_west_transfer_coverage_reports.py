#!/usr/bin/env python3
"""Build coverage reports for Big West inbound transfer modeling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
MODELING_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
MISSING_PATH = Path("data/big_west_transfer_modeling_dataset_missing.csv")
WORK_QUEUE_PATH = Path("data/big_west_source_stats_work_queue.csv")
FINDINGS_PATH = Path("data/big_west_historical_transfer_findings.csv")
CACHE_STATUS_PATH = Path("data/big_west_d1_source_school_cache_status.csv")

MISSING_D1_SOURCE_OUTPUT = Path("data/big_west_missing_d1_source_stats_needed.csv")
INCOMING_TEAM_YEAR_OUTPUT = Path("data/big_west_incoming_by_year_team_summary.csv")


def key_cols() -> list[str]:
    return ["player_slug", "destination_school_slug", "first_big_west_season"]


def missing_key_cols() -> list[str]:
    return ["player_slug", "destination_school", "first_big_west_season"]


def previous_season(season: str) -> str:
    start = int(str(season).split("-", 1)[0])
    return f"{start - 1}-{str(start)[-2:]}"


def read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_missing_d1_source_report() -> pd.DataFrame:
    transfers = pd.read_csv(TRANSFERS_PATH)
    missing = pd.read_csv(MISSING_PATH)
    work_queue = read_optional(WORK_QUEUE_PATH)
    findings = read_optional(FINDINGS_PATH)
    cache_status = read_optional(CACHE_STATUS_PATH)

    rows = missing[
        (missing["source_level"] == "D1")
        & (missing["reason"] == "missing_source_stats")
        & (missing["first_big_west_season"] != "2026-27")
    ].copy()

    rows = rows.merge(
        transfers[
            missing_key_cols()
            + [
                "destination_school_slug",
                "source_school_slug",
                "source_conference",
                "pathway_type",
                "position",
                "height",
                "weight",
                "class",
                "source_url",
            ]
        ],
        on=missing_key_cols(),
        how="left",
    )
    rows["expected_source_season"] = rows["first_big_west_season"].map(previous_season)

    if not work_queue.empty:
        queue_cols = [
            "player_slug",
            "destination_school",
            "first_big_west_season",
            "local_cache_status",
            "recommended_next_step",
            "current_missing_reason",
        ]
        rows = rows.merge(work_queue[queue_cols], on=missing_key_cols(), how="left")

    if not findings.empty:
        finding_cols = [
            "player_name",
            "source_school",
            "destination_school",
            "first_big_west_season",
            "collection_bucket",
            "source_status",
            "source_evidence",
            "outcome_status",
            "outcome_evidence",
            "next_action",
        ]
        rows = rows.merge(
            findings[finding_cols],
            on=["player_name", "source_school", "destination_school", "first_big_west_season"],
            how="left",
        )

    if not cache_status.empty:
        status_cols = [
            "source_school_slug",
            "expected_source_season",
            "sports_reference_url",
            "cache_path",
            "matched_count",
            "matched_players",
            "missing_players",
            "status",
        ]
        rows = rows.merge(cache_status[status_cols], on=["source_school_slug", "expected_source_season"], how="left")

    output_cols = [
        "player_name",
        "player_slug",
        "source_school",
        "source_school_slug",
        "source_conference",
        "destination_school",
        "destination_school_slug",
        "first_big_west_season",
        "expected_source_season",
        "position",
        "height",
        "weight",
        "class",
        "local_cache_status",
        "recommended_next_step",
        "current_missing_reason",
        "source_status",
        "source_evidence",
        "next_action",
        "sports_reference_url",
        "cache_path",
        "status",
        "matched_count",
        "matched_players",
        "missing_players",
        "outcome_status",
        "outcome_evidence",
        "source_url",
    ]
    existing_cols = [col for col in output_cols if col in rows.columns]
    rows = rows[existing_cols].sort_values(["first_big_west_season", "destination_school", "player_name"])
    rows.to_csv(MISSING_D1_SOURCE_OUTPUT, index=False)
    return rows


def build_incoming_team_year_summary() -> pd.DataFrame:
    transfers = pd.read_csv(TRANSFERS_PATH)
    modeling = pd.read_csv(MODELING_PATH)
    missing = pd.read_csv(MISSING_PATH)

    transfers["_transfer_row"] = 1
    pivot = (
        transfers.pivot_table(
            index=["first_big_west_season", "destination_school"],
            columns="source_level",
            values="_transfer_row",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for level in ["D1", "D2", "JUCO", "NAIA"]:
        if level not in pivot.columns:
            pivot[level] = 0
    pivot["total_inbound"] = pivot[["D1", "D2", "JUCO", "NAIA"]].sum(axis=1)

    playable = (
        modeling.groupby(["first_big_west_season", "destination_school", "source_level"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for level in ["D1", "D2"]:
        if level not in playable.columns:
            playable[level] = 0
    playable = playable.rename(columns={"D1": "model_ready_d1", "D2": "model_ready_d2"})
    playable["model_ready_playable_total"] = playable[["model_ready_d1", "model_ready_d2"]].sum(axis=1)

    missing_counts = (
        missing.groupby(["first_big_west_season", "destination_school", "source_level", "reason"])
        .size()
        .reset_index(name="count")
    )
    if missing_counts.empty:
        missing_wide = pd.DataFrame(columns=["first_big_west_season", "destination_school"])
    else:
        missing_counts["missing_bucket"] = (
            "missing_"
            + missing_counts["source_level"].str.lower()
            + "_"
            + missing_counts["reason"].str.replace(";", "_and_", regex=False)
        )
        missing_wide = (
            missing_counts.pivot_table(
                index=["first_big_west_season", "destination_school"],
                columns="missing_bucket",
                values="count",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )

    summary = pivot.merge(playable, on=["first_big_west_season", "destination_school"], how="left")
    summary = summary.merge(missing_wide, on=["first_big_west_season", "destination_school"], how="left")
    count_cols = [col for col in summary.columns if col not in {"first_big_west_season", "destination_school"}]
    summary[count_cols] = summary[count_cols].fillna(0).astype(int)

    leading_cols = [
        "first_big_west_season",
        "destination_school",
        "total_inbound",
        "D1",
        "D2",
        "JUCO",
        "NAIA",
        "model_ready_playable_total",
        "model_ready_d1",
        "model_ready_d2",
    ]
    other_cols = sorted(col for col in summary.columns if col not in leading_cols)
    summary = summary[leading_cols + other_cols].sort_values(["first_big_west_season", "destination_school"])
    summary.to_csv(INCOMING_TEAM_YEAR_OUTPUT, index=False)
    return summary


def main() -> int:
    missing_d1 = build_missing_d1_source_report()
    summary = build_incoming_team_year_summary()
    print(f"Wrote {len(missing_d1)} rows to {MISSING_D1_SOURCE_OUTPUT}")
    print(f"Wrote {len(summary)} rows to {INCOMING_TEAM_YEAR_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
