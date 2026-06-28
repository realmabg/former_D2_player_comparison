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
- Features: D2-available box/per-40 stats, destination school, assumed destination MPG, position, source level/conference, source Massey power, destination Massey power, and conference/team power jump.

## Best Models

| Target | Rows | Best model | Family | CV MAE | CV RMSE | CV R2 | Pearson | Spearman | MAE gain vs baseline | Top-decile lift |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| bpm | 426 | elastic_alpha_0.1_l1_0.65 | elastic_net | 1.738 | 2.250 | 0.503 | 0.710 | 0.714 | 0.819 | 4.049 |
| bpm_percentile | 426 | histgb_lr_0.06_leaves_4_l2_12.0 | hist_gradient_boosting | 16.346 | 20.517 | 0.495 | 0.704 | 0.703 | 8.708 | 34.851 |
| bpr | 378 | elastic_alpha_0.1_l1_0.35 | elastic_net | 1.104 | 1.385 | 0.608 | 0.781 | 0.780 | 0.656 | 3.067 |
| porpag | 426 | elastic_alpha_0.03_l1_0.65 | elastic_net | 0.643 | 0.828 | 0.527 | 0.726 | 0.732 | 0.320 | 1.793 |

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
