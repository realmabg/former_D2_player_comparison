# BPR Miss Review

This file reviews the largest out-of-fold BPR misses from the D2-available model. Tags are heuristic starting points, not final labels.

## Files

- `bpr_largest_miss_review.csv`: sorted player-level miss review with suggested tags
- `bpr_miss_tag_summary.csv`: aggregate tag counts

## Most Common Tags

| Tag | Rows | Mean Abs Error |
|---|---:|---:|
| low_source_minutes | 76 | 1.67 |
| over_predicted_translation | 36 | 3.47 |
| under_predicted_breakout | 33 | 3.34 |
| real_prior_role_underweighted | 19 | 3.34 |
| negative_outcome_overpredicted | 18 | 3.82 |
| power_drop_breakout | 8 | 3.33 |
| star_outcome_missed | 6 | 4.73 |
| large_jump_up_overvalued | 5 | 3.75 |
| scorer_overvalued | 3 | 3.49 |
| d2_to_d1_translation_miss | 2 | 3.95 |

## Feature Ideas From Misses

- `low_source_minutes`: add multi-year trend/context because one-year box score undersells bench players who later broke out.
- `power_drop_breakout`: conference-strength delta helps, but high-major bench-to-mid-major role expansion may need class/age and minutes trend.
- `d2_to_d1_translation_miss`: lower-division scoring volume needs stronger adjustment by conference/team quality and position archetype.
- `scorer_overvalued`: source PPG/per-40 alone can overrate players without efficiency, assists, rebounds, or defensive indicators.
