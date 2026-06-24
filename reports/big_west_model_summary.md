# Big West Transfer Model Summary

Generated on 2026-06-19 from the current files in `data/`.


## Scope

This report covers the first Big West model experiments using the current 145 model-ready D1/D2 transfer rows. JUCO rows are still excluded from this first model unless they later get matching source stats and Massey conference power.


## Overall Run Summary

| target | validation | Features | rows_used | best_model | MAE | Baseline MAE | MAE Gain | RMSE | Baseline RMSE | R2 | Baseline R2 | Corr | Baseline Corr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| impact_score | random_kfold | all | 145 | ridge_alpha_10 | 19.499 | 22.046 | 2.547 | 24.016 | 25.411 | 0.088 | -0.021 | 0.348 | -0.192 |
| bpm | random_kfold | all | 145 | elastic_net | 2.903 | 2.919 | 0.016 | 4.944 | 4.832 | -0.060 | -0.012 | 0.075 | -0.148 |
| bpm | random_kfold | common_box | 145 | elastic_net | 2.859 | 2.919 | 0.059 | 4.909 | 4.832 | -0.045 | -0.012 | 0.090 | -0.148 |
| bpm | random_kfold | per40_core | 145 | elastic_net_a1_00_l10_05 | 2.842 | 2.919 | 0.077 | 4.844 | 4.832 | -0.017 | -0.012 | 0.031 | -0.148 |
| bpm | season_holdout | all | 145 | rf_500_depth4_leaf4 | 2.868 | 2.940 | 0.072 | 4.845 | 4.822 | -0.017 | -0.008 | 0.024 | -0.098 |
| bpm | season_holdout | common_box | 145 | elastic_net | 2.855 | 2.940 | 0.085 | 4.757 | 4.822 | 0.019 | -0.008 | 0.189 | -0.098 |
| bpm | season_holdout | per40_core | 145 | ridge_alpha_100 | 2.835 | 2.940 | 0.105 | 4.752 | 4.822 | 0.021 | -0.008 | 0.151 | -0.098 |
| impact_score | random_kfold | common_box | 145 | ridge_alpha_10 | 19.150 | 22.046 | 2.896 | 23.544 | 25.411 | 0.124 | -0.021 | 0.378 | -0.192 |
| impact_score | random_kfold | per40_core | 145 | elastic_net_a0_10_l10_50 | 19.015 | 22.046 | 3.031 | 23.361 | 25.411 | 0.137 | -0.021 | 0.394 | -0.192 |
| porpag | random_kfold | all | 125 | rf_300_depth3_leaf5 | 0.976 | 0.992 | 0.015 | 1.193 | 1.206 | -0.011 | -0.033 | 0.095 | -0.244 |
| porpag | random_kfold | common_box | 125 | rf_300_depth3_leaf5 | 0.969 | 0.992 | 0.023 | 1.184 | 1.206 | 0.005 | -0.033 | 0.132 | -0.244 |
| porpag | random_kfold | per40_core | 125 | rf_800_depth6_leaf3 | 0.976 | 0.992 | 0.015 | 1.198 | 1.206 | -0.020 | -0.033 | 0.106 | -0.244 |
| porpag | season_holdout | all | 125 | rf_500_depth4_leaf4 | 0.964 | 0.982 | 0.018 | 1.181 | 1.191 | 0.010 | -0.007 | 0.127 | -0.114 |
| porpag | season_holdout | common_box | 125 | elastic_net | 0.959 | 0.982 | 0.023 | 1.188 | 1.191 | -0.002 | -0.007 | 0.149 | -0.114 |
| porpag | season_holdout | per40_core | 125 | extra_trees_800_depth_none_leaf5 | 0.956 | 0.982 | 0.026 | 1.189 | 1.191 | -0.004 | -0.007 | 0.127 | -0.114 |
| impact_score | season_holdout | all | 145 | ridge_alpha_10 | 19.536 | 22.317 | 2.781 | 23.962 | 25.606 | 0.092 | -0.037 | 0.341 | -0.199 |
| impact_score | season_holdout | common_box | 145 | ridge_alpha_10 | 18.880 | 22.317 | 3.438 | 23.268 | 25.606 | 0.144 | -0.037 | 0.395 | -0.199 |
| impact_score | season_holdout | per40_core | 145 | elastic_net_a0_05_l10_15 | 18.396 | 22.317 | 3.922 | 22.739 | 25.606 | 0.183 | -0.037 | 0.441 | -0.199 |

## Main Takeaways

- The most useful first-model target is still `impact_score`, especially under season-holdout validation.
- `impact_score` season holdout uses 145 rows, picks `ridge_alpha_10`, and improves MAE by about 3.438 over the fold-mean baseline.
- `BPM` and `PORPAG` are now fully wired as alternate targets, but their validation correlations remain low in the current 145-row dataset.
- `PORPAG` coverage is complete after the Josh Ward manual BartTorvik PRPG row; the season-holdout PORPAG run improves MAE by about 0.023.
- `BPM` season holdout improves MAE by about 0.085, but its R2 is still slightly negative, so it should be treated as exploratory.

Interpretation: the custom impact blend is currently more stable than raw BPM/PORPAG because the sample is small and the Big West role/outcome signal is noisy. The next real improvement probably comes from more historical rows, not from changing model families.


## Leaderboard: `impact_score` / `random_kfold`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| ridge_alpha_10 | ok | 19.499 | 24.016 | 0.088 | 0.348 | 15.518 |
| elastic_net | ok | 19.512 | 23.892 | 0.098 | 0.340 | 16.624 |
| lightgbm_small_leaf | ok | 20.245 | 24.627 | 0.041 | 0.282 | 7.448 |
| hist_gradient_boosting_l2 | ok | 20.763 | 24.868 | 0.022 | 0.278 | 5.629 |
| lightgbm_more_regularized | ok | 20.818 | 24.994 | 0.012 | 0.228 | 11.630 |
| gradient_boosting_shallow | ok | 20.902 | 24.988 | 0.013 | 0.214 | 13.015 |
| rf_500_depth4_leaf4 | ok | 21.169 | 24.649 | 0.039 | 0.203 | 16.329 |
| rf_300_depth3_leaf5 | ok | 21.180 | 24.744 | 0.032 | 0.197 | 16.102 |

## Leaderboard: `impact_score` / `season_holdout`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| ridge_alpha_10 | ok | 19.536 | 23.962 | 0.092 | 0.341 | 15.518 |
| elastic_net | ok | 19.604 | 24.042 | 0.086 | 0.324 | 16.624 |
| ridge_alpha_1 | ok | 20.144 | 24.580 | 0.045 | 0.364 | 13.476 |
| gradient_boosting_shallow | ok | 20.460 | 24.772 | 0.030 | 0.239 | 13.015 |
| hist_gradient_boosting_l2 | ok | 20.729 | 25.357 | -0.016 | 0.252 | 5.629 |
| rf_300_depth3_leaf5 | ok | 20.818 | 24.519 | 0.050 | 0.229 | 16.102 |
| rf_500_depth4_leaf4 | ok | 20.938 | 24.457 | 0.054 | 0.234 | 16.329 |
| lightgbm_more_regularized | ok | 21.122 | 25.118 | 0.003 | 0.216 | 11.630 |

## Leaderboard: `bpm` / `random_kfold`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| elastic_net | ok | 2.903 | 4.944 | -0.060 | 0.075 | 2.567 |
| mean_baseline | baseline | 2.919 | 4.832 | -0.012 | -0.148 | 2.919 |
| rf_500_depth4_leaf4 | ok | 2.943 | 4.964 | -0.068 | -0.125 | 2.309 |
| extra_trees_500_leaf4 | ok | 2.962 | 4.923 | -0.051 | -0.120 | 2.645 |
| rf_300_depth3_leaf5 | ok | 2.990 | 4.991 | -0.080 | -0.064 | 2.447 |
| ridge_alpha_10 | ok | 3.069 | 5.178 | -0.162 | 0.043 | 2.422 |
| lightgbm_more_regularized | ok | 3.251 | 5.166 | -0.157 | -0.010 | 1.912 |
| gradient_boosting_shallow | ok | 3.271 | 5.217 | -0.180 | -0.074 | 2.226 |

## Leaderboard: `bpm` / `season_holdout`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| rf_500_depth4_leaf4 | ok | 2.868 | 4.845 | -0.017 | 0.024 | 2.309 |
| elastic_net | ok | 2.893 | 4.824 | -0.009 | 0.153 | 2.567 |
| rf_300_depth3_leaf5 | ok | 2.923 | 4.887 | -0.036 | 0.044 | 2.447 |
| mean_baseline | baseline | 2.940 | 4.822 | -0.008 | -0.098 | 2.940 |
| extra_trees_500_leaf4 | ok | 2.964 | 4.854 | -0.021 | -0.009 | 2.645 |
| lightgbm_small_leaf | ok | 3.002 | 4.942 | -0.059 | 0.128 | 1.403 |
| ridge_alpha_10 | ok | 3.033 | 4.960 | -0.067 | 0.137 | 2.422 |
| gradient_boosting_shallow | ok | 3.051 | 5.051 | -0.106 | 0.007 | 2.226 |

## Leaderboard: `porpag` / `random_kfold`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| rf_300_depth3_leaf5 | ok | 0.976 | 1.193 | -0.011 | 0.095 | 0.760 |
| lightgbm_more_regularized | ok | 0.981 | 1.221 | -0.059 | 0.134 | 0.556 |
| rf_500_depth4_leaf4 | ok | 0.984 | 1.201 | -0.024 | 0.048 | 0.754 |
| elastic_net | ok | 0.989 | 1.215 | -0.048 | 0.050 | 0.902 |
| lightgbm_small_leaf | ok | 0.991 | 1.253 | -0.115 | 0.130 | 0.332 |
| mean_baseline | baseline | 0.992 | 1.206 | -0.033 | -0.244 | 0.992 |
| extra_trees_500_leaf4 | ok | 0.993 | 1.211 | -0.041 | -0.012 | 0.863 |
| gradient_boosting_shallow | ok | 0.999 | 1.226 | -0.067 | 0.106 | 0.624 |

## Leaderboard: `porpag` / `season_holdout`

| Model | status | MAE | RMSE | R2 | Corr | Train MAE |
| --- | --- | --- | --- | --- | --- | --- |
| rf_500_depth4_leaf4 | ok | 0.964 | 1.181 | 0.010 | 0.127 | 0.754 |
| rf_300_depth3_leaf5 | ok | 0.969 | 1.187 | -0.001 | 0.125 | 0.760 |
| extra_trees_500_leaf4 | ok | 0.970 | 1.186 | 0.002 | 0.090 | 0.863 |
| elastic_net | ok | 0.971 | 1.213 | -0.045 | 0.079 | 0.902 |
| mean_baseline | baseline | 0.982 | 1.191 | -0.007 | -0.114 | 0.982 |
| lightgbm_more_regularized | ok | 0.983 | 1.212 | -0.043 | 0.151 | 0.556 |
| gradient_boosting_shallow | ok | 0.993 | 1.203 | -0.027 | 0.154 | 0.624 |
| ridge_alpha_10 | ok | 0.994 | 1.247 | -0.104 | 0.136 | 0.769 |

## Feature Importance Notes

These are model-specific and should be read as directional, not causal. With only 125 rows, stable validation performance matters more than any single feature rank.


## Top Features: `impact_score` / `random_kfold`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_conference | 0.673 | positive | 1.574 | 88.297 |
| source_conf_power | 0.644 | positive | 3.465 | 9.712 |
| source_apg | 0.395 | positive | 2.104 | 6.775 |
| source_pts_per_40 | 0.348 | positive | 1.859 | 5.833 |
| height_in | 0.200 | positive | 1.029 | 4.918 |
| source_ts_pct | 0.200 | positive | 1.051 | 3.967 |
| source_tov_per_40 | 0.159 | positive | 0.795 | 4.665 |
| source_fg3_pct | 0.135 | positive | 0.671 | 4.224 |
| source_ast_per_40 | 0.123 | positive | 0.630 | 3.173 |
| position | 0.084 | positive | 0.261 | 8.557 |
| source_efg_pct | 0.081 | positive | 0.414 | 2.112 |
| destination_conf_power | 0.072 | positive | 0.344 | 2.651 |

## Top Features: `impact_score` / `season_holdout`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_conference | 0.673 | positive | 1.574 | 88.297 |
| source_conf_power | 0.644 | positive | 3.465 | 9.712 |
| source_apg | 0.395 | positive | 2.104 | 6.775 |
| source_pts_per_40 | 0.348 | positive | 1.859 | 5.833 |
| height_in | 0.200 | positive | 1.029 | 4.918 |
| source_ts_pct | 0.200 | positive | 1.051 | 3.967 |
| source_tov_per_40 | 0.159 | positive | 0.795 | 4.665 |
| source_fg3_pct | 0.135 | positive | 0.671 | 4.224 |
| source_ast_per_40 | 0.123 | positive | 0.630 | 3.173 |
| position | 0.084 | positive | 0.261 | 8.557 |
| source_efg_pct | 0.081 | positive | 0.414 | 2.112 |
| destination_conf_power | 0.072 | positive | 0.344 | 2.651 |

## Top Features: `bpm` / `random_kfold`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_three_rate | 0.842 | positive | 0.289 | 1.117 |
| source_apg | 0.524 | positive | 0.178 | 0.717 |
| source_conference | 0.429 | positive | 0.014 | 1.848 |
| source_conf_power | 0.285 | positive | 0.077 | 0.576 |
| source_ts_pct | 0.239 | positive | 0.072 | 0.412 |
| source_pts_per_40 | 0.207 | positive | 0.061 | 0.372 |
| height_in | 0.189 | positive | 0.052 | 0.375 |
| source_fg3_pct | 0.169 | positive | 0.036 | 0.440 |
| source_spg | 0.163 | positive | 0.046 | 0.307 |
| source_ft_pct | 0.138 | positive | 0.032 | 0.328 |
| source_per | 0.075 | positive | 0.008 | 0.272 |
| conf_power_delta | 0.057 | positive | 0.002 | 0.243 |

## Top Features: `bpm` / `season_holdout`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_three_rate | 1.000 | positive | 0.074 | 0.086 |
| source_ft_pct | 0.775 | positive | 0.047 | 0.084 |
| source_bpm | 0.724 | positive | 0.065 | 0.042 |
| conf_power_delta | 0.616 | positive | 0.050 | 0.045 |
| source_conf_power | 0.531 | positive | 0.041 | 0.043 |
| source_efg_pct | 0.479 | positive | 0.029 | 0.053 |
| source_ts_pct | 0.476 | positive | 0.042 | 0.030 |
| source_ppg | 0.467 | positive | 0.038 | 0.034 |
| source_tov_per_40 | 0.409 | positive | 0.032 | 0.032 |
| source_mpg | 0.408 | positive | 0.026 | 0.042 |
| source_reb_per_40 | 0.394 | positive | 0.033 | 0.028 |
| source_apg | 0.390 | positive | 0.032 | 0.028 |

## Top Features: `porpag` / `random_kfold`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_ppg | 1.000 | positive | 0.043 | 0.112 |
| source_games | 0.687 | positive | 0.025 | 0.096 |
| conf_power_delta | 0.630 | positive | 0.029 | 0.064 |
| source_tov_per_40 | 0.493 | positive | 0.021 | 0.055 |
| source_ft_pct | 0.443 | positive | 0.018 | 0.055 |
| source_stl_per_40 | 0.413 | positive | 0.017 | 0.051 |
| source_pts_per_40 | 0.407 | positive | 0.016 | 0.050 |
| source_apg | 0.304 | positive | 0.011 | 0.040 |
| source_mpg | 0.273 | positive | 0.011 | 0.033 |
| source_bpm | 0.268 | positive | 0.012 | 0.030 |
| source_efg_pct | 0.267 | positive | 0.008 | 0.044 |
| source_ast_per_40 | 0.265 | positive | 0.010 | 0.034 |

## Top Features: `porpag` / `season_holdout`

| feature | importance | direction | Permutation | Model Importance |
| --- | --- | --- | --- | --- |
| source_ppg | 1.000 | positive | 0.022 | 0.055 |
| source_ft_pct | 0.892 | positive | 0.019 | 0.050 |
| source_stl_per_40 | 0.845 | positive | 0.018 | 0.049 |
| source_games | 0.840 | positive | 0.016 | 0.054 |
| conf_power_delta | 0.820 | positive | 0.018 | 0.044 |
| source_minutes_share | 0.756 | positive | 0.017 | 0.042 |
| source_pts_per_40 | 0.682 | positive | 0.014 | 0.042 |
| source_tov_per_40 | 0.677 | positive | 0.014 | 0.041 |
| source_bpm | 0.648 | positive | 0.015 | 0.034 |
| source_mpg | 0.634 | positive | 0.014 | 0.036 |
| source_conf_power | 0.564 | positive | 0.011 | 0.035 |
| source_ast_per_40 | 0.559 | positive | 0.012 | 0.033 |

## How To Refresh

Run the model scripts, summarize the metrics, then rebuild this notebook:

```bash
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score --validation season_holdout
.venv/bin/python scripts/build_big_west_first_model.py --target bpm
.venv/bin/python scripts/build_big_west_first_model.py --target bpm --validation season_holdout
.venv/bin/python scripts/build_big_west_first_model.py --target porpag
.venv/bin/python scripts/build_big_west_first_model.py --target porpag --validation season_holdout
.venv/bin/python scripts/summarize_big_west_model_runs.py
.venv/bin/python scripts/build_big_west_model_report_notebook.py
```

