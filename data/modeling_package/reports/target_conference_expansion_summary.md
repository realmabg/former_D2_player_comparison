# Target-Conference Expansion Summary

Added the requested conferences in this order:

1. Mountain West
2. Atlantic 10
3. American
4. Missouri Valley

The same Sports Reference roster-diff process used for WCC was generalized and reused:

- fetch target-conference school rosters by season
- compare each roster to the previous season
- check each new player's Sports Reference profile for prior school history
- classify prior source level
- parse D1 source-season stats from the profile
- parse first target-conference outcome stats from the same profile
- write model-ready D1 transfer rows
- write manual work queues for D2, JUCO, no-stats, and ambiguous rows

## Rows Added So Far

| Conference | D1 model rows | Target BPR rows |
|---|---:|---:|
| Mountain West | 145 | 106 |
| Atlantic 10 | 60 | 44 |
| American | 10 | 6 |
| Missouri Valley | 9 | 8 |

The full target-conference modeling dataset is now 502 rows. The expanded BPR model used 379 rows with target EvanMiya BPR.

## BPR Model Comparison

| Run | Rows used | Best model | CV MAE | CV RMSE | CV R2 | CV Corr | Baseline MAE |
|---|---:|---|---:|---:|---:|---:|---:|
| Big West + WCC | 215 | ridge_alpha_10 | 1.361 | 1.769 | 0.366 | 0.612 | 1.744 |
| Expanded | 379 | ridge_alpha_100 | 1.342 | 1.688 | 0.417 | 0.646 | 1.756 |

Adding these conferences improved the BPR model on season-holdout validation, but this version included source EvanMiya features that current D2 players do not have. It is useful as an analysis model, not as the production D2 projection model.

## D2-Available Projection Model

For the website projections, the model was rebuilt using only features that exist for D2 players:

- height and position
- source games, MPG, and minutes share
- source shooting rates
- source per-40 points, rebounds, assists, steals, blocks, turnovers
- source conference Massey power
- destination conference Massey power
- source-to-destination conference power delta

| Run | Rows used | Best model | CV MAE | CV R2 | CV Corr |
|---|---:|---|---:|---:|---:|
| Expanded with source EvanMiya | 379 | ridge_alpha_100 | 1.342 | 0.417 | 0.646 |
| Expanded D2-available only | 379 | hist_gradient_boosting_more_l2 | 1.475 | 0.280 | 0.529 |

The D2-available model is weaker, but it is the fair model for scoring current D2 players.

## Remaining Work Queues

- Mountain West has 56 non-D1/manual source-stat rows.
- Atlantic 10 has 9 non-D1/manual source-stat rows from the cached profiles, with more profiles still unfetched.
- American and Missouri Valley are roster/audit-ready but still need more profile fetching to get fuller coverage.

## Key Outputs

- Expanded comparison: `data/target_conference_bpr_expansion_comparison.csv`
- D2-available comparison: `data/target_conference_bpr_d2_available_comparison.csv`
- Expanded predictions: `data/target_conference_model_bpr_expanded_predictions_bpr_season_holdout_per40_core.csv`
- Expanded leaderboard: `data/target_conference_model_bpr_expanded_leaderboard_bpr_season_holdout_per40_core.csv`
- Expanded metrics: `data/target_conference_model_bpr_expanded_metrics_bpr_season_holdout_per40_core.json`
- D2-available website data: `data/projection_dashboard_data.json`
