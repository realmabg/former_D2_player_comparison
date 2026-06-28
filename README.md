# Former D2 Player Comparison

A browser app for screening current NCAA Division II men's basketball players as potential Division I transfers, with an emphasis on UCSD/Big West-style recruiting.

The current website is driven by `data/projection_dashboard_data.json` and focuses on projected post-transfer EvanMiya BPR using only D2-available features.

The current frontend direction is:

- lighter landing page instead of a dense all-in-one dashboard
- drawer navigation instead of a permanently visible sidebar
- separate views for `Screening Board`, `Leaderboard`, `Compare`, `Teams`, `Transfer Portal`, and `Recruiting Board`
- product focus on `Leaderboard` and `Teams` as the highest-priority surfaces
- overall emphasis on screening and triage rather than a full research workspace

Run a local server, then open the app in a browser:

```bash
python3 -m http.server 8000
```

Then visit `http://127.0.0.1:8000/`.

## Frontend Files

- `index.html` - app shell and navigation container
- `styles.css` - UI styles and route-level layout styling
- `src/app.js` - route rendering, filtering, leaderboard, compare, and teams views

## Data / Modeling / Scripts
- `scripts/scrape_school_stats_poc.py` - proof-of-concept scraper for school cumulative-stat pages
- `scripts/scrape_phase1_school_stats.py` - batch scraper for model-eligible phase-one D2 -> D1 transfers
- `scripts/scrape_phase1_d1_outcomes.py` - first-D1-season outcome scraper, using Sports Reference player pages first and Sports Reference school-season pages as fallback
- `scripts/scrape_big_west_transfer_outcomes.py` - first-Big-West-season outcome scraper, using Sports Reference school-season pages plus existing phase-one outcome rows
- `scripts/scrape_big_west_school_outcomes.py` - first-Big-West-season outcome scraper from official Big West school stat pages
- `scripts/build_big_west_transfer_source_stats.py` - pre-transfer source-season stat builder, using verified D2 school stats and local Sports Reference caches
- `scripts/scrape_big_west_d1_source_school_stats.py` - caches Sports Reference source-school pages for priority D1 inbound-transfer source stats
- `scripts/build_big_west_remaining_d1_review.py` - classifies remaining D1 source-stat misses and writes the human-review subset
- `scripts/scrape_big_west_missing_d2_source_stats.py` - targeted scraper for D2 source rows missing from the Big West source-stat table
- `scripts/build_big_west_transfer_modeling_dataset.py` - joins source stats to first-Big-West outcomes and scores transfer impact
- `scripts/build_big_west_first_model.py` - compares first-pass Big West transfer impact models from the cleaned D1/D2 modeling dataset
- `scripts/build_big_west_modeling_gap_reports.py` - writes missing-row, Massey, and BartTorvik collection checklists for model expansion
- `scripts/scrape_massey_conference_power.py` - imports Massey conference power from saved Massey HTML/CSV files, with a best-effort live fetch mode
- `scripts/build_big_west_barttorvik_outcomes.py` - builds first-Big-West PORPAG outcomes from local BartTorvik/TRank player exports
- `scripts/build_big_west_historical_transfer_findings.py` - summarizes evidence and recommended actions for completed-season modeling gaps
- `scripts/build_big_west_first_model_readiness.py` - writes first-model D1/D2 readiness, exclusion, and manual-check files
- `scripts/build_phase1_modeling_dataset.py` - joins D2 features to D1 outcomes, scores D1 impact, and derives first-pass learned weights
- `scripts/build_big_west_inbound_transfers.py` - builds all cached inbound Big West transfers for the D2-transfer timeframe
- `scripts/build_d2_team_directory.py` - builds the D2 team/conference directory from current player data and historical transfer teams
- `scripts/scrape_d2_schedule_results.py` - scrapes D2 schedule results for teams with known athletics domains
- `data/school_stats_poc.csv` - four scraped historical D2 stat rows from school pages
- `data/phase1_school_stats.csv` - scraped school-page stat rows for phase-one transfers
- `data/phase1_school_stats_missing.csv` - phase-one rows still needing manual source resolution
- `data/phase1_d1_outcomes.csv` - first-D1-season D1 outcome rows
- `data/phase1_d1_outcomes_missing.csv` - players without a matching outcome row
- `data/big_west_transfer_d1_outcomes.csv` - first-Big-West-season outcomes for inbound transfers resolved so far
- `data/big_west_transfer_d1_outcomes_missing.csv` - inbound transfer outcomes still missing because the season has not started or the player was not found on the Sports Reference school-season page
- `data/big_west_transfer_school_outcomes.csv` - first-Big-West-season outcomes resolved from official school stat pages
- `data/big_west_transfer_school_outcomes_missing.csv` - official-school outcome rows not found, not parseable, or not yet started
- `data/big_west_transfer_source_stats.csv` - pre-transfer source-season stats resolved so far
- `data/big_west_transfer_source_stats_missing.csv` - transfer source rows still missing because they need Sports Reference fetches, new D2 school-page collection, or JUCO/NAIA support
- `data/big_west_source_stats_work_queue.csv` - prioritized no-rate-limit work queue for remaining source-stat collection
- `data/big_west_d1_source_school_cache_status.csv` - cache/match status for priority D1 source-school Sports Reference pages
- `data/big_west_remaining_d1_review.csv` - classified D1 source-stat misses with source-page and Verbal Commits evidence
- `data/big_west_remaining_d1_review_needed.csv` - small human-review subset from the remaining D1 source-stat misses
- `data/big_west_missing_d2_source_stats.csv` - supplemental D2 source rows found from the targeted missing-D2 scraper
- `data/big_west_missing_d2_source_stats_missing.csv` - remaining D2 source rows without playable source stats after the targeted pass
- `data/big_west_transfer_modeling_dataset.csv` - model-ready Big West transfer rows with both source stats and first-Big-West outcomes
- `data/big_west_transfer_modeling_dataset_missing.csv` - transfers not yet model-ready, with source/outcome missing flags
- `data/big_west_model_predictions.csv` - first-pass cross-validated Big West impact predictions
- `data/big_west_model_feature_importance.csv` - feature importance from the best trained first-pass Big West model
- `data/big_west_model_leaderboard.csv` - cross-validated leaderboard for baseline, ridge, random forest, Extra Trees, gradient boosting, and LightGBM models
- `data/big_west_model_metrics.json` - row counts, validation metrics, model metadata, and baseline comparison for the first-pass Big West model
- `data/big_west_model_learned_weights.json` - normalized feature weights derived from the first-pass Big West model
- `data/big_west_model_run_summary.csv` - compact comparison of first-model targets and validation modes
- `data/big_west_model_leaderboard_bpm.csv` - same model comparison using first-Big-West BPM as the target
- `data/big_west_model_metrics_bpm.json` - validation metrics for the BPM-target model comparison
- `data/big_west_modeling_missing_summary.csv` - grouped missing-row counts by season, source level, and missing reason
- `data/big_west_historical_transfer_rows_needed.csv` - completed-season transfer rows still missing source stats, outcome stats, or both
- `data/big_west_historical_transfer_findings.csv` - evidence/status file for completed-season modeling gaps
- `data/big_west_first_model_readiness_summary.csv` - D1/D2 first-model row counts, exclusion counts, and manual-check counts
- `data/big_west_first_model_exclusions.csv` - D1/D2 rows to exclude or mark as no-source/no-outcome-stat for the first model
- `data/big_west_first_model_manual_check.csv` - D1/D2 rows still needing human confirmation before the first model is fully clean
- `data/massey_conference_power_needed.csv` - source/destination conference-season power values needed for the transfer universe
- `data/massey_conference_power_template.csv` - fillable input template for Massey conference power
- `data/massey_conference_power.csv` - parsed Massey conference power values consumed by the modeling scripts
- `data/massey_conference_power_missing.csv` - Massey conference-season rows not found in the latest parse/fetch attempt
- `data/big_west_barttorvik_needed.csv` - model-ready rows needing BartTorvik PORPAG values
- `data/big_west_barttorvik_outcomes_template.csv` - fillable input template for BartTorvik PORPAG outcomes
- `data/big_west_barttorvik_outcomes.csv` - matched first-Big-West PORPAG rows from local BartTorvik/TRank exports
- `data/big_west_barttorvik_outcomes_missing.csv` - model-ready rows still missing a BartTorvik PORPAG match
- `data/phase1_modeling_dataset.csv` - joined D2 feature and first-year D1 outcome training table
- `data/phase1_feature_importance.csv` - feature correlations and first-pass importance scores
- `data/phase1_learned_weights.json` - normalized learned similarity weights
- `data/big_west_inbound_transfers.csv` - all cached inbound Big West transfers from 2021 through 2026
- `data/big_west_inbound_transfers_missing.csv` - inbound candidates with prior-college hints but unresolved source schools
- `data/big_west_inbound_transfers_needs_review.csv` - review queue for ambiguous inbound candidates; currently header-only because all candidates are resolved
- `data/big_west_inbound_transfers_review_findings.csv` - Sports Reference / cached-profile review findings for candidates excluded as Big-West-first players
- `data/d2_team_directory.csv` - 289-team D2 directory from the current D2 player pool
- `data/d2_schedule_results.csv` - scraped 2023-24 through 2025-26 schedule results for known-domain teams
- `data/d2_schedule_results_missing.csv` - schedule pages that could not be parsed
- `src/learnedWeights.js` - learned weights imported by older browser-prototype work
- `src/data.js`, `src/csvPlayers.js`, `src/similarity.js` - older prototype files that are no longer the main current website path

## Next Data Step

Replace the seed rows in `src/data.js` with a generated dataset that has one row per player season:

```text
player_id, player_name, season, d2_school, d1_school, position, height_in, age,
minutes_pct, usage_pct, pts_per_40, ast_per_40, tov_per_40, reb_per_40,
stl_per_40, blk_per_40, three_pa_rate, three_pct, ft_rate, ft_pct,
ts_pct, conf_strength, d1_bpm, d1_minutes_pct, outcome_tier
```

Keep the feature names aligned with `PLAYER_FEATURES` in `src/data.js`, or update that list when new features are added.

School cumulative-stat pages are viable for historical D2 stat collection. The POC scraper currently pulls:

- Aniwaniwa Tait-Jones, Hawaii Hilo 2022-23
- Hayden Gray, Azusa Pacific 2022-23
- Tyler McGhie, Southern Nazarene 2022-23
- Nordin Kapic, Lynn 2023-24

The phase-one scraper pulls the model-eligible rows from `/Users/adriankong/Desktop/D2_to_D1_pathway/data/phase1_transfers.csv` and writes 28 matched school-page rows. The scraper has explicit overrides for:

- Max Jones, Tampa 2021-22, from his Tampa player-page career stats view
- Jailen Daniel-Dalton, San Francisco State 2023-24, because he missed 2024-25 with injury
- Guzman Vasilic, Southeastern Oklahoma State 2023-24, marked missing because he redshirted and has no stat row

The D1 outcome scraper reads cached Sports Reference player pages from `/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/sports_reference`, then falls back to Sports Reference school-season pages for players missing player-page tables. It currently writes 29 matched first-D1-season rows and zero missing rows. The five school-page fallbacks are Max Jones, Joshua Ward, Rob Diaz III, De'Undrae Perteete Jr., and Emanuel Prospere II.

The modeling build joins 28 D2 stat rows to D1 outcomes. Guzman Vasilic is excluded from the modeling table because he redshirted at D2 and has no D2 stat row. The impact score is a percentile blend of D1 minutes share, BPM, win shares, and box-score production.

The Big West inbound transfer build uses cached Verbal Commits school activity/player profiles for the same 2021-2026 timeframe as the D2-to-Big-West data. It currently resolves 276 inbound transfer rows: 183 D1-to-Big-West, 50 JUCO-to-Big-West, 41 D2-to-Big-West, and 2 NAIA-to-Big-West. It excludes reviewed non-transfer false positives such as Zion Sensley, who decommitted from Saint Mary's, and Scotty Belnap, who committed to Utah Tech before a two-year mission but did not attend Utah Tech. It also carries phase-one review flags for rows that overlap the manually reviewed D2 pathway table.

The Big West review pass found zero remaining ambiguous inbound candidates. Sports Reference resolved the first review batch as players whose first college stats were already in the Big West or who had no prior college row. The remaining rate-limited rows were checked against cached Verbal Commits timelines and excluded because they had no transfer/enrollment source event before the Big West destination, only later outbound transfer history or offer history.

The first-Big-West outcome scraper currently writes 176 resolved rows from Sports Reference school-season pages and already reviewed phase-one D2 transfer outcomes. The missing file has 62 future 2026-27 rows marked `season_not_started` and 38 completed-season rows where the player was not found on the Sports Reference school-season page.

The official Big West school-page outcome scraper currently writes 142 additional outcome rows from completed seasons. The modeling build uses these as a fallback behind Sports Reference rows. The scraper now reads embedded Sidearm/NextGen Nuxt cumulative-stat payloads before falling back to HTML table/text parsing. Remaining official-page misses are mostly players not on the destination stat page, a smaller set of name-present-but-not-parseable rows, and future 2026-27 seasons.

The Big West source-stat builder currently writes 184 conservative source rows: 39 from verified/manual D2 school-page stats and 145 from local Sports Reference player/source-school caches. The Kieves Turner row is matched through the Deuce Turner Sports Reference alias. The targeted missing-D2 pass found 11 additional 2025-26 D2 source rows, including manual entries for Malcolm Bell and Jaden Tengan from user-provided school-page tables. The remaining D2 source misses are Isaiah Moses, whose relevant source path is now treated as JUCO/out-of-scope for the first model, and Guzman Vasilic, a known redshirt/no-stat case. The source-school cache pass downloaded 166 D1 source-school pages and reduced the source-stat work queue to 93 rows.

The Big West modeling dataset currently has 125 model-ready playable-outcome rows: 97 D1-to-Big-West and 28 D2-to-Big-West rows. It uses Sports Reference outcomes first and official school-page outcomes as fallback. Confirmed first-Big-West DNP/redshirt/injury no-stat rows are excluded from this stat-projection model rather than treated as zero projections, because those outcomes are often not controllable basketball-performance signals. The dataset carries height, weight, optional Massey source/destination conference power, optional conference-power delta, and optional BartTorvik PORPAG outcome columns. The D1/D2 first-model readiness file has zero manual-check rows after the latest no-stat/out-of-scope confirmations. The remaining modeling-missing file has 57 rows missing only source stats, 58 rows missing only outcome stats, and 36 rows missing both source stats and outcome stats. The completed-season historical gap file has 89 rows to chase before future 2026-27 outcomes become usable. The remaining source-stat work queue has 93 rows: 39 D1, 50 JUCO, 2 D2, and 2 NAIA.

The remaining-D1 review classifier reduced the 39 D1 source-stat misses to zero human-review rows after confirming the Zion Sensley and Scotty Belnap source assignments were false positives. The remaining D1 rows are classified as likely no-stat rows at the listed source school, redshirt/no-stat rows, future 2026-27 deferrals, or the canceled Princeton 2020-21 season.

The first-pass Big West model comparison trains on the 125 model-ready playable-outcome D1/D2 rows only: 97 D1-to-Big-West and 28 D2-to-Big-West. JUCO rows are excluded unless matching source stats and Massey conference power are available. The Massey file now fills conference-power features for every model-ready D1/D2 row. The BartTorvik export plus the Josh Ward user-provided Bart row fill PORPAG for all 125 model-ready rows. The comparison currently tests ridge, elastic net, random forest, Extra Trees, gradient boosting, histogram gradient boosting, and LightGBM regressors. The harder season-holdout impact-score run picks elastic net, with MAE of about 20.25 impact-score points, RMSE of about 24.29, R2 of about 0.11, and prediction/actual correlation of about 0.36, beating a fold-mean baseline MAE of about 22.60. BPM and PORPAG are wired as alternate targets, but both are weak as projection targets so far; PORPAG season-holdout MAE is about 0.97 versus a baseline of about 0.98, with low validation correlation.

The model script can train alternate targets:

```bash
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score --validation season_holdout
.venv/bin/python scripts/build_big_west_first_model.py --target bpm
.venv/bin/python scripts/build_big_west_first_model.py --target porpag
.venv/bin/python scripts/build_big_west_barttorvik_outcomes.py
.venv/bin/python scripts/summarize_big_west_model_runs.py
```

The PORPAG target requires `data/big_west_barttorvik_outcomes.csv`, then `scripts/build_big_west_transfer_modeling_dataset.py` must be rerun. The current modeling file has all 125 model-ready PORPAG rows filled. The Massey feature columns activate after filling `data/massey_conference_power.csv` or one of the accepted aliases with `season,conference,power`.

Massey currently presents Cloudflare/Turnstile verification to automated fetches in this environment, so the scraper supports saved files as the reliable path:

```bash
.venv/bin/python scripts/scrape_massey_conference_power.py --input path/to/massey_2024_d1.html --season 2023-24 --level D1
.venv/bin/python scripts/scrape_massey_conference_power.py --input path/to/massey_export.csv
.venv/bin/python scripts/scrape_massey_conference_power.py --fetch
```

The live `--fetch` mode writes `data/massey_conference_power_missing.csv` when Massey blocks or when a page has no parseable conference-power table.

The ML comparison dependencies are pinned in `requirements-ml.txt`. The local environment was created with Python 3.12 because the system Python 3.14 did not have compatible scientific wheels for the full stack:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python scripts/build_big_west_first_model.py
```

The strength-score data foundation now has:

- 289 D2 teams in `data/d2_team_directory.csv`
- 22 teams with known athletics domains from the current historical-transfer coverage
- 1,972 parsed schedule results across 2023-24, 2024-25, and 2025-26
- zero parser misses for the known-domain set

The remaining coverage task is resolving athletics domains or another schedule source for the other 267 D2 teams before choosing the final team/conference rating formula.
