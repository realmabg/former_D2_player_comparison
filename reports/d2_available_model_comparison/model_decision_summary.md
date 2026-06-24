# Model Decision Summary

## Current Recommendation

Use **EvanMiya BPR** as the primary target for the D2 transfer board.

Why:

- BPR has the strongest out-of-fold signal among the tested targets.
- BPR is stable when filtering to target-conference players with at least 10 MPG.
- BPM improves with the 10 MPG filter, which suggests BPM is more sensitive to low-minute noise.
- PORPAG is useful as a secondary reference, but it did not beat BPR on correlation or R2.

## Evaluation Views

Keep both evaluation views:

- `reports/d2_available_model_comparison/`: all valid rows.
- `reports/d2_available_model_comparison_min_mpg_10/`: only target-conference seasons with at least 10 MPG.

The 10 MPG view should be treated as a robustness check, not the only truth. It removes tiny-role noise, but it also changes the population we are evaluating.

## Best Current BPR Results

All valid BPR rows:

- Rows: 379
- Best model: `histgb_lr_0.03_leaves_4_l2_1.0`
- CV MAE: 1.481
- CV R2: 0.271
- CV Pearson: 0.521
- CV Spearman: 0.513

Target MPG >= 10:

- Rows: 378
- Best model: `xgb_lr_0.03_depth_3_lambda_8.0`
- CV MAE: 1.483
- CV R2: 0.282
- CV Pearson: 0.531
- CV Spearman: 0.518

Interpretation: the BPR model is not being propped up by low-minute rows. The filtered and unfiltered results are essentially the same.

## Biggest Miss Review

Review files:

- `reports/d2_available_model_comparison/bpr_miss_review/bpr_largest_miss_review.csv`
- `reports/d2_available_model_comparison/bpr_miss_review/bpr_miss_tag_summary.csv`
- `reports/d2_available_model_comparison/bpr_miss_review/bpr_miss_review_summary.md`

Most common miss tags:

- `low_source_minutes`: 76 rows
- `over_predicted_translation`: 36 rows
- `under_predicted_breakout`: 33 rows
- `real_prior_role_underweighted`: 19 rows
- `negative_outcome_overpredicted`: 18 rows

## Feature Work Worth Doing Next

The next gains are more likely to come from features than more hyperparameter tuning.

Good next features:

- `years_played_before_transfer`: proxy for class/age using available season history.
- `source_minutes_trend`: whether the player's role was growing, flat, or shrinking.
- `source_team_massey_power`: team-level quality, if collected by the user.
- `height_bucket` and `position_bucket`: coarse archetypes from profile height/position.
- `conference_power_delta`: already included; keep it.
- `source_to_destination_team_power_delta`: better version of jump size once team Massey power exists.
- `source_games` and missing-season/injury flags: already partially represented by games, but explicit flags would help if reliable.

## Do Not Add As Source Features For Current D2 Projection

- Source EvanMiya ratings.
- Source BartTorvik advanced ratings.
- Any other D1-only source stat not available for D2 candidates.

Those can be kept in the all-stats master file for analysis, but not in the D2-available training feature set.
