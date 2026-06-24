# Big West Per-40 Impact Optuna Tuning

This study tunes the main model only: `impact_score` target, `per40_core` features, and season-holdout cross-validation.
No held-out test set is used or inspected in this workflow; the objective is cross-validation MAE.

## Summary

- Study name: `big_west_impact_per40_season_holdout`
- Storage: `data/optuna_big_west_impact_per40.sqlite3`
- Trials before run: `0`
- Trials after run: `1000`
- Complete trials: `1000`
- Best CV MAE: `18.3562`
- Baseline CV MAE: `22.3173`
- Improvement vs baseline: `3.9612`
- Best model family: `elastic_net`
- Best CV R2: `0.1865`
- Best CV Corr: `0.4443`
- Convergence note: `best CV MAE changed by less than 0.05 over the last 100 complete trials`

## Interpretation

The expanded search did improve the model relative to the constant baseline, but it did not materially improve on the best model we already had from the scripted grid. The prior `impact_score + per40_core + season_holdout` run was about `18.3958` MAE; Optuna found `18.3562`, a gain of only about `0.04` impact-score MAE.

That means the model is probably close to its current ceiling with this dataset and target definition. More hyperparameter tuning is unlikely to create a big jump unless the training data, target, or feature quality changes.

The best model remained `ElasticNet`, not Random Forest, LightGBM, XGBoost, or another tree model. That is a useful signal: with only `145` usable rows, the more flexible models are not finding a stable nonlinear pattern that survives season-holdout validation. The linear regularized model is still the most reliable choice right now.

R2 and correlation are still modest (`0.1865` R2, `0.4443` correlation), so this should be treated as a useful ranking/projection aid rather than a precise stat predictor. It is beating baseline, but it is not yet a "trust blindly" model.

## Validation Discipline

This run optimized only season-holdout cross-validation MAE. It did not use a held-out test set during tuning. If we later create a true final test set, the correct workflow is:

1. Freeze the feature set and model/tuning process.
2. Retrain the selected model on the training seasons only.
3. Evaluate the held-out test set once.
4. Treat that result as the honest estimate of future performance.

## Top 20 Trials

| trial | cv_mae | family | params |
| --- | --- | --- | --- |
| 438 | 18.3562 | elastic_net | {"elastic_alpha": 0.12277815187136881, "elastic_l1_ratio": 0.741291035021961, "family": "elastic_net"} |
| 162 | 18.3565 | elastic_net | {"elastic_alpha": 0.11744725767982317, "elastic_l1_ratio": 0.7287175536945348, "family": "elastic_net"} |
| 839 | 18.3570 | elastic_net | {"elastic_alpha": 0.12739823059963556, "elastic_l1_ratio": 0.7822592445704888, "family": "elastic_net"} |
| 443 | 18.3571 | elastic_net | {"elastic_alpha": 0.08152200179389525, "elastic_l1_ratio": 0.5853107010027303, "family": "elastic_net"} |
| 612 | 18.3571 | elastic_net | {"elastic_alpha": 0.08302744958209164, "elastic_l1_ratio": 0.591165298233615, "family": "elastic_net"} |
| 482 | 18.3571 | elastic_net | {"elastic_alpha": 0.11655546642072584, "elastic_l1_ratio": 0.7181625148697056, "family": "elastic_net"} |
| 193 | 18.3572 | elastic_net | {"elastic_alpha": 0.08404048837935509, "elastic_l1_ratio": 0.6068555016888559, "family": "elastic_net"} |
| 236 | 18.3573 | elastic_net | {"elastic_alpha": 0.0814142899624779, "elastic_l1_ratio": 0.5811440293642036, "family": "elastic_net"} |
| 551 | 18.3573 | elastic_net | {"elastic_alpha": 0.07870167818932815, "elastic_l1_ratio": 0.5818522757901545, "family": "elastic_net"} |
| 620 | 18.3574 | elastic_net | {"elastic_alpha": 0.08385208797115878, "elastic_l1_ratio": 0.5890196233517493, "family": "elastic_net"} |
| 104 | 18.3574 | elastic_net | {"elastic_alpha": 0.08787107935162096, "elastic_l1_ratio": 0.6240971610472914, "family": "elastic_net"} |
| 202 | 18.3574 | elastic_net | {"elastic_alpha": 0.09650778955310081, "elastic_l1_ratio": 0.6592701213075178, "family": "elastic_net"} |
| 184 | 18.3574 | elastic_net | {"elastic_alpha": 0.09816665244418984, "elastic_l1_ratio": 0.6648285760694663, "family": "elastic_net"} |
| 343 | 18.3574 | elastic_net | {"elastic_alpha": 0.10155074282099563, "elastic_l1_ratio": 0.6766131645050318, "family": "elastic_net"} |
| 154 | 18.3575 | elastic_net | {"elastic_alpha": 0.07931122398772919, "elastic_l1_ratio": 0.5732765704716303, "family": "elastic_net"} |
| 119 | 18.3576 | elastic_net | {"elastic_alpha": 0.09441604191946917, "elastic_l1_ratio": 0.6556119949897112, "family": "elastic_net"} |
| 318 | 18.3576 | elastic_net | {"elastic_alpha": 0.09644697513497796, "elastic_l1_ratio": 0.6558064959253637, "family": "elastic_net"} |
| 691 | 18.3576 | elastic_net | {"elastic_alpha": 0.09255435111494129, "elastic_l1_ratio": 0.6490642764899983, "family": "elastic_net"} |
| 251 | 18.3576 | elastic_net | {"elastic_alpha": 0.07822419977809332, "elastic_l1_ratio": 0.5734655349115818, "family": "elastic_net"} |
| 787 | 18.3577 | elastic_net | {"elastic_alpha": 0.10084449272129137, "elastic_l1_ratio": 0.6709852411803273, "family": "elastic_net"} |

## Parameter Importance

| parameter | importance |
| --- | --- |
| family | 1.0000 |

## Artifacts

- `trials.csv`: all trials
- `top20_trials.csv`: top 20 completed trials
- `optimization_history.png`: trial values and best-so-far curve
- `parameter_importance.png`: Optuna parameter importance
- `best_model.pkl`: best model retrained on all available training rows
- `cv_predictions.csv`: out-of-fold predictions for the best tuned configuration
