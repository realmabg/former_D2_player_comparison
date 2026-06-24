# D2-Available Model Comparison

This report intentionally excludes source-side features that current D2 players cannot have, including source EvanMiya, BartTorvik, or other D1-only advanced ratings.

## Setup

- Dataset: `data/modeling/training/d2_available_training.csv`
- Rows available: 426
- Minimum target MPG filter: 10
- Bart/PORPAG target exclusions applied: 0
- Candidate model configurations per target: 156
- Validation: season-holdout GroupKFold using `first_big_west_season`
- Selection objective: lowest cross-validated MAE
- Features: D2-available box/per-40 stats, position, source level/conference, source Massey power, destination Massey power, and conference power delta

## Best Models

| Target | Rows | Best model | Family | CV MAE | CV RMSE | CV R2 | Pearson | Spearman | MAE gain vs baseline | Top-decile lift |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| bpm | 426 | xgb_lr_0.03_depth_2_lambda_8.0 | xgboost | 1.949 | 2.505 | 0.384 | 0.620 | 0.616 | 0.608 | 3.791 |
| bpm_percentile | 426 | lgbm_lr_0.06_leaves_4_lambda_12.0 | lightgbm | 18.146 | 22.808 | 0.376 | 0.617 | 0.615 | 6.908 | 33.372 |
| bpr | 378 | gbr_depth_1_lr_0.06_leaf_10 | gradient_boosting | 1.291 | 1.631 | 0.457 | 0.677 | 0.670 | 0.469 | 2.318 |
| porpag | 426 | gbr_depth_1_lr_0.06_leaf_5 | gradient_boosting | 0.911 | 1.132 | 0.117 | 0.351 | 0.323 | 0.052 | 0.791 |

## Interpretation

- `CV MAE` is the average absolute miss in the target stat using out-of-fold predictions.
- `CV R2` measures variance explained out of fold; values near zero mean little improvement over a mean predictor.
- `Pearson` measures linear correlation between predicted and actual values.
- `Spearman` measures ranking quality.
- `Top-decile lift` measures whether the players ranked in the top 10% by the model actually beat the average outcome.

## Outputs

- `leaderboard.csv`: all tuned configurations and metrics
- `top20_by_target.csv`: best 20 configurations for each target
- `best_models_summary.csv`: one-line summary of the best model per target
- `best_cv_predictions.csv`: out-of-fold predictions from each target's best model
