#!/usr/bin/env python3
"""Package raw inputs, combined stats, and training artifacts for sharing."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


PACKAGE_DIR = Path("data/modeling_package")

FILES = {
    "raw/barttorvik": [
        Path("Bart data/trank_data_2020.csv"),
        Path("Bart data/trank_data_2021.csv"),
        Path("Bart data/trank_data_2022.csv"),
        Path("Bart data/trank_data_2023.csv"),
        Path("Bart data/trank_data_2024.csv"),
        Path("Bart data/trank_data_2025.csv"),
        Path("Bart data/trank_data_2026.csv"),
    ],
    "raw/massey": [
        Path("data/massey_conference_power.csv"),
        Path("data/massey_team_ratings.csv"),
        Path("data/massey_team_ratings_summary.csv"),
        Path("Massey Ratings 20-26 Uncleaned - Sheet1.csv"),
        Path("Massey Ratings 20-26 Uncleaned - Team.csv"),
    ],
    "raw/evanmiya": [
        Path("data/evanmiya_player_ratings_2020_21_to_2025_26.csv"),
    ],
    "intermediate": [
        Path("data/target_conference_transfer_modeling_dataset.csv"),
        Path("data/target_conference_transfer_modeling_big_west_schema.csv"),
        Path("data/target_conference_barttorvik_outcomes.csv"),
        Path("data/target_conference_barttorvik_outcomes_missing.csv"),
        Path("data/target_conference_evanmiya_match_summary.csv"),
        Path("data/target_conference_evanmiya_missing_matches.csv"),
        Path("data/target_conference_massey_power_unmatched_after_fallback.csv"),
    ],
    "combined": [
        Path("data/modeling/master/target_conference_all_stats.csv"),
    ],
    "training": [
        Path("data/modeling/training/d2_available_training.csv"),
        Path("data/modeling/training/d2_available_feature_manifest.json"),
        Path("data/modeling/training/source_class_backfill_input_rows.csv"),
        Path("data/modeling/training/source_class_backfill_found.csv"),
        Path("data/modeling/training/source_class_backfill_needs_review.csv"),
        Path("data/modeling/training/source_class_missing_rows.csv"),
        Path("data/modeling/training/source_team_power_missing_rows.csv"),
    ],
    "reports": [
        Path("reports/target_conference_expansion_summary.md"),
        Path("reports/target_conference_bpr_model_summary.md"),
        Path("reports/target_conference_bpr_model_summary.md"),
    ],
    "code": [
        Path("scripts/clean_massey_team_ratings.py"),
        Path("scripts/backfill_source_classes.py"),
        Path("scripts/build_target_conference_barttorvik_outcomes.py"),
        Path("scripts/build_modeling_artifacts.py"),
        Path("scripts/run_d2_available_model_comparison.py"),
    ],
}


def copy_file(source: Path, target_dir: Path) -> dict[str, str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if not source.exists():
        return {"source": str(source), "target": str(target), "status": "missing"}
    shutil.copy2(source, target)
    return {"source": str(source), "target": str(target), "status": "copied"}


def write_readme(copied: list[dict[str, str]]) -> None:
    readme = PACKAGE_DIR / "README.md"
    lines = [
        "# Transfer Modeling Package",
        "",
        "This folder separates the modeling data into source exports, matched/intermediate files, a combined all-stats table, and a D2-available training table.",
        "",
        "## Folder Layout",
        "",
        "- `raw/barttorvik/`: local BartTorvik/TRank exports by season. These contain PORPAG, BPM, OBPM, and DBPM outcome fields.",
        "- `raw/massey/`: cleaned and original Massey conference-power files.",
        "- `raw/evanmiya/`: cached EvanMiya player ratings export.",
        "- `intermediate/`: transfer rows and source-match outputs used to build the modeling schemas.",
        "- `combined/target_conference_all_stats.csv`: one combined dataset with every merged source column available. Missing values are expected, especially for D2 source players.",
        "- `training/d2_available_training.csv`: pseudo-training dataset restricted to features that should exist for current D2 projection candidates.",
        "- `training/d2_available_feature_manifest.json`: feature lists, targets, coverage counts, and exclusions.",
        "- `code/`: scripts to rebuild Bart outcomes, rebuild modeling artifacts, and run model comparisons locally.",
        "",
        "## Rebuild Order",
        "",
        "Run these locally when inputs change:",
        "",
        "```bash",
        ".venv/bin/python scripts/build_target_conference_barttorvik_outcomes.py",
        ".venv/bin/python scripts/build_modeling_artifacts.py",
        ".venv/bin/python scripts/build_shareable_modeling_package.py",
        "```",
        "",
        "For heavier model tuning, run locally to avoid network/rate-limit issues and to keep long jobs under your control:",
        "",
        "```bash",
        ".venv/bin/python scripts/run_d2_available_model_comparison.py",
        "```",
        "",
        "## PORPAG Note",
        "",
        "PORPAG comes from the BartTorvik/TRank exports. It was missing in the expanded model schema because the expanded target-conference dataset had not been merged with the local Bart outcome file yet. The current package fixes that through `target_conference_barttorvik_outcomes.csv` and the `build_modeling_artifacts.py` merge step.",
        "",
        "## Copied Files",
        "",
    ]
    for item in copied:
        lines.append(f"- `{item['target']}`: {item['status']}")
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    copied: list[dict[str, str]] = []
    for folder, paths in FILES.items():
        target_dir = PACKAGE_DIR / folder
        seen: set[Path] = set()
        for source in paths:
            if source in seen:
                continue
            seen.add(source)
            copied.append(copy_file(source, target_dir))

    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    write_readme(copied)
    (PACKAGE_DIR / "package_manifest.json").write_text(json.dumps(copied, indent=2), encoding="utf-8")

    print(f"Wrote shareable modeling package to {PACKAGE_DIR}")
    for item in copied:
        print(f"{item['status']:>7} {item['source']} -> {item['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
