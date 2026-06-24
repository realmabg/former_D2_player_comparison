# D2-Available Model Comparison

This report intentionally excludes source-side features that current D2 players cannot have, including source EvanMiya, BartTorvik, or other D1-only advanced ratings.

## Setup

- Dataset: `data/modeling/training/d2_available_training.csv`
- Rows available: 502
- Minimum target MPG filter: 0
- Bart/PORPAG target exclusions applied: 1
- Candidate model configurations per target: 156
- Validation: season-holdout GroupKFold using `first_big_west_season`
- Selection objective: lowest cross-validated MAE
- Features: D2-available box/per-40 stats, position, source level/conference, source Massey power, destination Massey power, and conference power delta

## Best Models

| Target | Rows | Best model | Family | CV MAE | CV RMSE | CV R2 | Pearson | Spearman | MAE gain vs baseline | Top-decile lift |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| bpm | 502 | elastic_alpha_0.3_l1_0.65 | elastic_net | 2.636 | 4.333 | 0.160 | 0.400 | 0.537 | 0.492 | 3.580 |
| bpm_percentile | 502 | elastic_alpha_0.3_l1_0.65 | elastic_net | 19.703 | 24.058 | 0.305 | 0.553 | 0.554 | 5.390 | 28.427 |
| bpr | 379 | gbr_depth_2_lr_0.03_leaf_5 | gradient_boosting | 1.294 | 1.629 | 0.457 | 0.677 | 0.674 | 0.463 | 2.253 |
| porpag | 499 | elastic_alpha_0.1_l1_0.35 | elastic_net | 0.917 | 1.139 | 0.171 | 0.414 | 0.407 | 0.098 | 1.136 |

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
