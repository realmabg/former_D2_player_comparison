# Transfer Modeling Package

This folder separates the modeling data into source exports, matched/intermediate files, a combined all-stats table, and a D2-available training table.

## Folder Layout

- `raw/barttorvik/`: local BartTorvik/TRank exports by season. These contain PORPAG, BPM, OBPM, and DBPM outcome fields.
- `raw/massey/`: cleaned and original Massey conference-power files.
- `raw/evanmiya/`: cached EvanMiya player ratings export.
- `intermediate/`: transfer rows and source-match outputs used to build the modeling schemas.
- `combined/target_conference_all_stats.csv`: one combined dataset with every merged source column available. Missing values are expected, especially for D2 source players.
- `training/d2_available_training.csv`: pseudo-training dataset restricted to features that should exist for current D2 projection candidates.
- `training/d2_available_feature_manifest.json`: feature lists, targets, coverage counts, and exclusions.
- `code/`: scripts to rebuild Bart outcomes, rebuild modeling artifacts, and run model comparisons locally.

## Rebuild Order

Run these locally when inputs change:

```bash
.venv/bin/python scripts/build_target_conference_barttorvik_outcomes.py
.venv/bin/python scripts/build_modeling_artifacts.py
.venv/bin/python scripts/build_shareable_modeling_package.py
```

For heavier model tuning, run locally to avoid network/rate-limit issues and to keep long jobs under your control:

```bash
.venv/bin/python scripts/run_d2_available_model_comparison.py
```

## PORPAG Note

PORPAG comes from the BartTorvik/TRank exports. It was missing in the expanded model schema because the expanded target-conference dataset had not been merged with the local Bart outcome file yet. The current package fixes that through `target_conference_barttorvik_outcomes.csv` and the `build_modeling_artifacts.py` merge step.

## Copied Files

- `data/modeling_package/raw/barttorvik/trank_data_2020.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2021.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2022.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2023.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2024.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2025.csv`: copied
- `data/modeling_package/raw/barttorvik/trank_data_2026.csv`: copied
- `data/modeling_package/raw/massey/massey_conference_power.csv`: copied
- `data/modeling_package/raw/massey/massey_team_ratings.csv`: copied
- `data/modeling_package/raw/massey/massey_team_ratings_summary.csv`: copied
- `data/modeling_package/raw/massey/Massey Ratings 20-26 Uncleaned - Sheet1.csv`: copied
- `data/modeling_package/raw/massey/Massey Ratings 20-26 Uncleaned - Team.csv`: copied
- `data/modeling_package/raw/evanmiya/evanmiya_player_ratings_2020_21_to_2025_26.csv`: copied
- `data/modeling_package/intermediate/target_conference_transfer_modeling_dataset.csv`: copied
- `data/modeling_package/intermediate/target_conference_transfer_modeling_big_west_schema.csv`: copied
- `data/modeling_package/intermediate/target_conference_barttorvik_outcomes.csv`: copied
- `data/modeling_package/intermediate/target_conference_barttorvik_outcomes_missing.csv`: copied
- `data/modeling_package/intermediate/target_conference_evanmiya_match_summary.csv`: copied
- `data/modeling_package/intermediate/target_conference_evanmiya_missing_matches.csv`: copied
- `data/modeling_package/intermediate/target_conference_massey_power_unmatched_after_fallback.csv`: copied
- `data/modeling_package/combined/target_conference_all_stats.csv`: copied
- `data/modeling_package/training/d2_available_training.csv`: copied
- `data/modeling_package/training/d2_available_feature_manifest.json`: copied
- `data/modeling_package/training/source_class_backfill_input_rows.csv`: copied
- `data/modeling_package/training/source_class_backfill_found.csv`: copied
- `data/modeling_package/training/source_class_backfill_needs_review.csv`: copied
- `data/modeling_package/training/source_class_missing_rows.csv`: copied
- `data/modeling_package/training/source_team_power_missing_rows.csv`: copied
- `data/modeling_package/reports/target_conference_expansion_summary.md`: copied
- `data/modeling_package/reports/target_conference_bpr_model_summary.md`: copied
- `data/modeling_package/code/clean_massey_team_ratings.py`: copied
- `data/modeling_package/code/backfill_source_classes.py`: copied
- `data/modeling_package/code/build_target_conference_barttorvik_outcomes.py`: copied
- `data/modeling_package/code/build_modeling_artifacts.py`: copied
- `data/modeling_package/code/run_d2_available_model_comparison.py`: copied
