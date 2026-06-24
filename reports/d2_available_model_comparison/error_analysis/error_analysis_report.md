# D2-Available Model Error Analysis

This report analyzes out-of-fold predictions from the best model for each target. `cv_error = prediction - actual`, so negative values mean the model under-predicted the player.

## Overall Error

| Target | Rows | MAE | RMSE | Mean Error | Under-predicted % |
|---|---:|---:|---:|---:|---:|
| bpm | 502 | 2.826 | 4.402 | -0.029 | 53.4% |
| bpm_percentile | 502 | 21.279 | 26.212 | 0.649 | 53.0% |
| bpr | 379 | 1.481 | 1.888 | -0.008 | 50.7% |
| porpag | 486 | 0.931 | 1.165 | 0.014 | 45.9% |

## Biggest BPR Misses

| Player | Source | Destination | Season | Actual | Pred | Error | MPG | Source Conf | Level |
|---|---|---|---|---:|---:|---:|---:|---|---|
| Jonathan Mogbo | Missouri State | San Francisco | 2023-24 | 8.46 | 1.78 | -6.68 | 24.4 | MVC | D1 |
| Brandin Podziemski | Illinois | Santa Clara | 2022-23 | 6.78 | 0.46 | -6.32 | 4.3 | Big Ten | D1 |
| Chuck Bailey | Evansville | Nevada | 2024-25 | -3.29 | 2.35 | 5.64 | 18.5 | MVC | D1 |
| Jalen Warley | Florida State | Gonzaga | 2025-26 | 6.86 | 2.05 | -4.81 | 24.1 | ACC | D1 |
| Assane Diop | Colorado | San Diego | 2025-26 | -0.93 | 3.82 | 4.75 | 15.1 | Big 12 | D1 |
| Lesown Hallums | South Carolina State | Pacific | 2023-24 | -3.42 | 1.22 | 4.64 | 26.5 | MEAC | D1 |
| Nique Clifford | Colorado | Colorado State | 2023-24 | 6.32 | 1.82 | -4.50 | 21.8 | Pac-12 | D1 |
| A.J. George | SMU | Cal State Bakersfield | 2025-26 | -3.03 | 1.36 | 4.39 | 6.5 | ACC | D1 |
| Carl Daughtery, Jr. | Central Arkansas | UC Davis | 2024-25 | -3.43 | 0.85 | 4.28 | 19.2 | ASUN | D1 |
| Emmanuel Stephen | Arizona | UNLV | 2025-26 | -2.02 | 2.26 | 4.28 | 3.0 | Big 12 | D1 |
| Isaac Johnson | Utah State | Hawaii | 2025-26 | 4.98 | 0.72 | -4.26 | 8.7 | Mountain West | D1 |
| Kaleb Brown | Missouri | Cal State Fullerton | 2024-25 | -3.21 | 0.97 | 4.18 | 6.5 | SEC | D1 |
| Isa Silva | Stanford | Long Beach State | 2023-24 | -3.56 | 0.61 | 4.17 | 12.9 | PAC 12 | D1 |
| Mor Seck | Hawaii | Fresno State | 2024-25 | -2.76 | 1.34 | 4.10 | 12.9 | Big West | D1 |
| Beril Kabamba | Spring Hill | Cal State Fullerton | 2023-24 | -3.55 | 0.48 | 4.03 | 34.8 | SIAC | D2 |

## What To Check Next

- Large negative errors are players who were better than the model expected. These may reveal missing context such as role change, injury recovery, age, or undervalued D2 production.
- Large positive errors are players the model liked too much. These may reveal low-minute source samples, poor transfer fit, or destination role limits.
- If one target conference or one season has much higher MAE, that can mean the dataset expansion added noisy rows or that season behaves differently.

## Output Files

- `enriched_cv_errors.csv`: every out-of-fold prediction joined to player/source context
- `largest_misses_by_target.csv`: top misses for every target
- `error_by_target_conference.csv`
- `error_by_source_level.csv`
- `error_by_source_conference.csv`
- `error_by_season.csv`
