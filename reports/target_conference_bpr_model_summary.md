# Target-Conference BPR Model Summary

Built a first model for predicting EvanMiya BPR in the player's first playable target-conference season.

## Dataset

- Source file: `data/target_conference_transfer_modeling_bpr_schema.csv`
- Total transfer rows: 278
- Rows with target EvanMiya BPR: 215
- Rows with pre-transfer source EvanMiya BPR: 142
- Rows used in best full-sample BPR run: 215
- Source-level mix in best full-sample BPR run: 189 D1, 26 D2

The target is `big_west_bpr`, mapped from `target_evanmiya_bpr`. Despite the legacy `big_west_*` column naming, this dataset includes both Big West and WCC target-conference rows.

## Best Run

Validation: season holdout  
Feature set: per-40 core box stats + source/destination Massey power + source-side EvanMiya features  
Best model: `ridge_alpha_10`

| Run | Rows | Best model | CV MAE | CV RMSE | CV R2 | CV Corr | Baseline MAE |
|---|---:|---|---:|---:|---:|---:|---:|
| with source EvanMiya, all BPR rows | 215 | ridge_alpha_10 | 1.361 | 1.769 | 0.366 | 0.612 | 1.744 |
| with source EvanMiya, min 10 target MPG | 214 | ridge_alpha_10 | 1.366 | 1.774 | 0.366 | 0.612 | 1.748 |
| no source EvanMiya, all BPR rows | 215 | gradient_boosting_many_tiny | 1.486 | 1.941 | 0.237 | 0.488 | 1.744 |
| no source EvanMiya, min 10 target MPG | 214 | gradient_boosting_shallow | 1.502 | 1.951 | 0.232 | 0.484 | 1.748 |

## Read

This is a meaningful improvement over the mean baseline. Source EvanMiya ratings help: the full source-EvanMiya model cuts MAE by about 0.38 BPR points versus baseline, compared with about 0.26 without source EvanMiya.

The min-10-MPG filter only removed one row, so it did not materially change the result.

## Main Outputs

- Comparison: `data/target_conference_bpr_model_comparison.csv`
- Predictions: `data/target_conference_model_bpr_predictions_bpr_season_holdout_per40_core.csv`
- Leaderboard: `data/target_conference_model_bpr_leaderboard_bpr_season_holdout_per40_core.csv`
- Feature importance: `data/target_conference_model_bpr_feature_importance_bpr_season_holdout_per40_core.csv`
- Metrics: `data/target_conference_model_bpr_metrics_bpr_season_holdout_per40_core.json`
