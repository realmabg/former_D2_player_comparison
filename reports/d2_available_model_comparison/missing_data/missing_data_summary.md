# Modeling Missing Data Summary

This summarizes remaining gaps after separating raw/intermediate/all-stats/training artifacts.

## Training Feature Coverage

| Column | Kind | Non-null | Missing | Coverage |
|---|---|---:|---:|---:|
| height_in | feature | 502 | 0 | 100.0% |
| weight_lbs | feature | 502 | 0 | 100.0% |
| position | feature | 502 | 0 | 100.0% |
| position_bucket | feature | 502 | 0 | 100.0% |
| height_bucket | feature | 502 | 0 | 100.0% |
| source_role_bucket | feature | 502 | 0 | 100.0% |
| source_games | feature | 502 | 0 | 100.0% |
| source_mpg | feature | 502 | 0 | 100.0% |
| source_ppg | feature | 502 | 0 | 100.0% |
| source_rpg | feature | 502 | 0 | 100.0% |
| source_apg | feature | 502 | 0 | 100.0% |
| source_conf_power | feature | 502 | 0 | 100.0% |
| destination_conf_power | feature | 502 | 0 | 100.0% |
| conf_power_delta | feature | 502 | 0 | 100.0% |
| source_team_power | feature | 501 | 1 | 99.8% |
| destination_team_power | feature | 502 | 0 | 100.0% |
| team_power_delta | feature | 501 | 1 | 99.8% |
| seasons_played_before_transfer | feature | 469 | 33 | 93.4% |
| source_class | feature | 502 | 0 | 100.0% |
| big_west_bpr | target | 379 | 123 | 75.5% |
| big_west_obpr | target | 379 | 123 | 75.5% |
| big_west_dbpr | target | 379 | 123 | 75.5% |
| big_west_bpm | target | 502 | 0 | 100.0% |
| target_porpag | target | 486 | 16 | 96.8% |
| target_barttorvik_bpm | target | 485 | 17 | 96.6% |

## Missing Source/Outcome Files

| Source | Rows | Meaning |
|---|---:|---|
| barttorvik_outcome_missing | 16 | Rows that did not match a local Bart/Torvik outcome row, so PORPAG/Bart BPM are missing. |
| evanmiya_target_missing | 281 | Rows without an EvanMiya target BPR match. These rows cannot train BPR but can still train BPM/PORPAG if available. |
| massey_conference_unmatched | 0 | Conference power gaps. Should be zero for current model features. |
| wcc_d2_source_missing | 0 | WCC D2 source rows missing source stats. |
| mwc_d1_outcome_missing | 2 | MWC D1 transfer rows where target outcome was not found. |
| a10_d1_outcome_missing | 1 | A10 D1 transfer rows where target outcome was not found. |
| aac_d1_outcome_missing | 1 | AAC D1 transfer rows where target outcome was not found. |
| mvc_d1_outcome_missing | 4 | MVC D1 transfer rows where target outcome was not found. |

## Practical Read

- No player is missing core identity, position, height, weight, source games, source minutes, source PPG/RPG/APG, or destination conference strength in the current training table.
- Conference-power feature gaps: 0 rows.
- Source team-power gaps: 1 rows. Destination team power is complete.
- Class/seasons-played-before-transfer is still unknown for 33 rows; these mostly come from older rows sourced from Sports Reference school-season pages rather than player-profile source tables.
- BPR target coverage is 379 of 502 rows because EvanMiya target matching is incomplete. This only affects BPR training rows.
- PORPAG coverage is 486 of 502 rows after the Bart/Torvik merge.
- The model feature set excludes D1-only source features that are not available for current D2 projection candidates.
