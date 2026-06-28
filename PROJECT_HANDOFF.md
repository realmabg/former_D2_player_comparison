# D2 Transfer Projection Project Handoff

## Project Goal

Build a transfer projection tool for evaluating current NCAA D2 men's basketball players as potential D1/mid-major transfers, with an emphasis on UCSD/Big West-style recruiting.

The current production target is projected EvanMiya BPR after transferring. The website is a static D2 transfer board that scores current D2 players using a model trained only on features that are available for D2 players.

## Big Picture Stages

1. Data collection and validation
   - Historical transfer rows from Big West, WCC, and other target conferences.
   - Source stats before transfer.
   - Target-conference outcomes after transfer.
   - Conference/team strength from Massey.
   - EvanMiya BPR outcomes where available.
   - Current D2 player stats for website candidates.

2. Modeling
   - Compare targets such as BPR, BPM, BPM percentile, PORPAG.
   - Use only source-side features available for D2 players for the production model.
   - Compare Random Forest, Gradient Boosting, XGBoost, LightGBM, ElasticNet/Ridge, etc.
   - Use cross-validation/season holdouts, not test-set tuning.

3. Website
   - Static transfer board in `index.html`, `styles.css`, and `src/`.
   - Data source is `data/projection_dashboard_data.json`.
   - Dashboard should show projected BPR, current stats, filters, and player links.

## Current Status

The model/website pipeline exists. The current focus has been cleaning bad current-D2 stat rows because `d2_data_cleaned.csv` has corrupted event stats for some players, especially assists/turnovers/steals/blocks.

Frontend direction has also shifted from a single all-in-one static board to a lighter screening app shell. The current website is now a multi-view browser app built from `index.html`, `styles.css`, and `src/app.js`, with the primary product emphasis on:

- `Leaderboard`
- `Teams`
- a simpler `Screening Board` flow for narrowing prospects

The UI was intentionally simplified so the first screen is less overwhelming:

- navigation is now a drawer instead of a permanently visible sidebar,
- the home screen is a lighter landing page instead of a dense dashboard,
- content is split across focused views instead of putting every control and panel on one page,
- the site is being treated primarily as a screening tool, not a full research workspace.

The `Data Upload` page/route was removed.

We created a verified override system:

- Base current D2 data comes from `d2_data_cleaned.csv`.
- Verified school stats override bad base rows.
- Manual rows can be used for players whose school pages are hard to parse.
- The dashboard builder applies these overrides before scoring players.

The most recent cleanup batch fixed/verified several suspicious D2 players using official school pages or manual image rows.

## Important Files

### Raw/current D2 candidate data

- `d2_data_cleaned.csv`
  - Main current D2 player candidate file.
  - Known issue: some event stats are corrupted.

- `d2_mens_database.csv`
  - Another D2 database file; appears to share at least some of the same stat issues.

- `d2_data_cleaned copy.csv`
  - Copy of `d2_data_cleaned.csv`; not the main pipeline input.

### Current D2 stat validation

- `scripts/validate_current_d2_stats.py`
  - Checks `d2_data_cleaned.csv` for suspicious stat rows.
  - Writes `data/current_d2_suspicious_event_stats.csv`.

- `data/current_d2_suspicious_event_stats.csv`
  - Suspicious rows that may need school-page verification.

### Current D2 verified overrides

- `data/current_d2_school_verified_stats.csv`
  - Main verified current-D2 override file from official school pages and appended manual rows.
  - Dashboard builder uses this.

- `data/current_d2_school_verified_raw_rows.csv`
  - Raw matched rows behind `current_d2_school_verified_stats.csv`.
  - Useful for auditing why a stat was parsed.

- `data/current_d2_verified_stats.csv`
  - Older/manual verified override path.
  - Dashboard also reads it.

- `data/current_d2_realgm_verified_stats.csv`
  - RealGM override path.
  - RealGM fetching hit 403/headless browser issues, so school stats became the preferred route.

### School stats parsing

- `scripts/fetch_current_d2_school_stats.py`
  - Fetches official school stats pages for suspicious/current D2 rows.
  - Supports URL overrides, name aliases, caching, and appending.
  - Writes verified school stats and missing rows.

- `data/current_d2_school_stat_url_overrides.csv`
  - Manual map from team/season to official stats URL.
  - Add rows here when ChatGPT/user finds a better official page.

- `data/current_d2_school_player_name_aliases.csv`
  - Player name aliases for school-page matching.
  - Examples: `A.J. Woodard` -> `Avery Woodard`, `Matty Foor` -> `Matthew Foor`.

- `data/current_d2_school_stats_missing.csv`
  - Rows still not parsed by the school stats script.

- `data/current_d2_missing_priority_to_fix.csv`
  - Higher-priority remaining missing rows.

- `data/current_d2_missing_deferred_low_priority.csv`
  - Lower-priority rows we are not focusing on yet.

### Manual current D2 rows

- `scripts/fetch_current_d2_verified_stats.py`
  - Converts manual rows or single-source URLs into verified format.

- `scripts/append_current_d2_manual_verified_stats.py`
  - Appends manual verified rows into `data/current_d2_school_verified_stats.csv`.

- `data/current_d2_manual_verification_input.csv`
  - Manual input file for Jaron Walker.

- `data/current_d2_manual_raquavian_input.csv`
  - Manual input file for Raquavian Jones.

- `data/current_d2_manual_verified_stats.csv`
  - Output for manual Jaron-style rows.

- `data/current_d2_manual_raquavian_verified_stats.csv`
  - Output for Raquavian.

### Modeling package

- `data/modeling_package/README.md`
  - Existing modeling package explanation.

- `data/modeling_package/raw/`
  - Raw source datasets:
    - BartTorvik
    - Massey
    - EvanMiya

- `data/modeling_package/intermediate/`
  - Cleaned/matched intermediate source/outcome files.

- `data/modeling_package/combined/target_conference_all_stats.csv`
  - Combined stats dataset with many source columns; may contain NAs.

- `data/modeling_package/training/d2_available_training.csv`
  - Production-style training dataset using only features that D2 players should have.

- `data/modeling_package/training/d2_available_feature_manifest.json`
  - Feature manifest for the D2-available model.

### Model comparison

- `scripts/run_d2_available_model_comparison.py`
  - Runs model comparisons for BPR/BPM/BPM percentile/PORPAG using D2-available features.

- `reports/d2_available_model_comparison/`
  - Main model-comparison outputs.

- `reports/d2_available_model_comparison/model_decision_summary.md`
  - Summary of why BPR is the current primary target.

- `reports/d2_available_model_comparison/model_comparison_report.md`
  - Model comparison details.

- `reports/d2_available_model_comparison_min_mpg_10/`
  - Version filtered to target players with at least 10 MPG.

### Website/dashboard

- `scripts/build_projection_dashboard_data.py`
  - Rebuilds static JSON for the website.
  - Reads current D2 data and verified overrides.
  - Writes `data/projection_dashboard_data.json`.

- `data/projection_dashboard_data.json`
  - Website data file.

- `index.html`
  - Website shell for the current browser app.

- `styles.css`
  - Current app styling.

- `src/`
  - Browser app JavaScript/assets.

### Current frontend routes/views

- `Home`
  - Lighter landing page with summary cards and a short list of top prospects.

- `Screening Board`
  - Main filtering/search page for prospect triage.

- `Leaderboard`
  - Primary ranking surface with sortable table, destination context switcher, and detail panel.

- `Compare`
  - Side-by-side player comparison page.

- `Teams`
  - Conference/team-context page showing strongest fits by destination context.

- `Transfer Portal`
  - Simplified portal-watch style page using current model data.

- `Recruiting Board`
  - Tiered board view for organizing targets.

## Current Model Choice

Primary target: EvanMiya BPR.

Reason:

- It has the best overall signal among the tested target stats.
- It is easier to explain as an overall player impact metric than the custom `impact_score`.
- PORPAG remains useful as a secondary reference, but BPR is currently the production ranking target.

Important modeling principle:

The production D2 model must not train on D1-only source features that current D2 players do not have. That means no source EvanMiya, source BartTorvik advanced stats, etc. Training features should be box-score/current-D2-available features plus contextual info like source conference/team strength, destination conference strength, height/position/class if available.

## Feature Ideas Already Discussed

Keep/expand:

- Points, rebounds, assists, steals, blocks, turnovers, fouls.
- Shooting splits: FG, FGA, FG%, 3PM, 3PA, 3P%, FTM, FTA, FT%.
- Per-minute or per-40 versions.
- Games played and minutes.
- Source conference strength via Massey.
- Destination conference strength via Massey.
- Source-to-destination jump size, likely destination power minus source power.
- Source team quality once Massey team ratings are cleaned.
- Class / experience:
  - Prefer categorical class where known.
  - Also add `college_stat_seasons_before_transfer`, counting playable stat seasons across D1/D2/JUCO unless DNP/redshirt/injury.
- Height and position buckets if available.

Avoid for production D2 model:

- Source EvanMiya BPR.
- Source BartTorvik PORPAG/BPM unless available for that player before transfer and also available for current D2 candidates.

## Recent Current-D2 Cleanup Batch

Recently fixed/handled:

- Jaron Walker: manual USBasket image row.
- Raquavian Jones: manual Erskine image row.
- A.J. Woodard: matched as Avery Woodard.
- Philip Layne: matched as Phillip Layne.
- Jalen Bradberry: UDC Presto lineup.
- Louis Connor: matched as Louis Conner.
- Matty Foor: matched as Matthew Foor.
- Lorenzo Sedita: Tusculum Presto lineup.
- Cam Oates: matched as Cameran Oates.

Key commands after manual/school verification:

```bash
.venv/bin/python scripts/append_current_d2_manual_verified_stats.py \
  --manual data/current_d2_manual_verified_stats.csv

.venv/bin/python scripts/append_current_d2_manual_verified_stats.py \
  --manual data/current_d2_manual_raquavian_verified_stats.csv

.venv/bin/python scripts/fetch_current_d2_school_stats.py \
  --mode suspicious \
  --names "A.J. Woodard" "Philip Layne" "Jalen Bradberry" "Louis Connor" "Matty Foor" "Lorenzo Sedita" "Cam Oates" \
  --sleep 3 \
  --append
```

Then verify:

```bash
.venv/bin/python - <<'PY'
import pandas as pd

names = [
    "Jaron Walker",
    "Raquavian Jones",
    "A.J. Woodard",
    "Philip Layne",
    "Jalen Bradberry",
    "Louis Connor",
    "Matty Foor",
    "Lorenzo Sedita",
    "Cam Oates",
]

df = pd.read_csv("data/current_d2_school_verified_stats.csv")
out = df[df["Player Name"].isin(names)].copy()
print(out[["Player Name","Team","GP","MIN","MPG","PTS","PPG","TOT RB","RPG","PF","AST","TO","STL","BLK"]].to_string(index=False))
print(f"\nfound {len(out)} of {len(names)}")
PY
```

## Rebuild Website Data

After verified stats are accepted:

```bash
.venv/bin/python scripts/build_projection_dashboard_data.py
```

Then open/refresh `index.html`.

Optional check:

```bash
.venv/bin/python - <<'PY'
import json

names = {"Jaron Walker","Raquavian Jones","A.J. Woodard","Philip Layne","Jalen Bradberry","Louis Connor","Matty Foor","Lorenzo Sedita","Cam Oates"}

data = json.load(open("data/projection_dashboard_data.json"))
players = data.get("players", [])
for p in players:
    if p.get("name") in names:
        print(p.get("name"), p.get("team"), "verified=", p.get("verifiedCurrentStats"), "source=", p.get("verifiedSourceUrl"))
PY
```

## Recommended Next Steps

1. Finish appending the latest verified/manual rows.
2. Rebuild `data/projection_dashboard_data.json`.
3. Open the website and spot-check the fixed players.
4. Keep frontend work centered on the two highest-priority product pages:
   - `Leaderboard`
   - `Teams`
5. Continue simplifying the screening flow before expanding secondary pages.
6. Only add new frontend views/features if they clearly help roster triage.
7. Rerun current D2 validation/missing reports to see what remains:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py
.venv/bin/python scripts/fetch_current_d2_school_stats.py --mode suspicious --sleep 3
```

8. Split remaining missing rows into:
   - high-priority players worth fixing now,
   - lower-priority/deferred rows,
   - manual rows needed because the school site is protected or not parseable.

9. Once current D2 stat quality is acceptable, rerun dashboard build and model comparison if feature inputs changed enough to matter.

10. Longer-term data/model work:
   - Finish/source team Massey power matching.
   - Add reliable height/position buckets.
   - Add `college_stat_seasons_before_transfer`.
   - Add source-to-destination jump size.
   - Rerun model comparison with the improved feature set.
   - Keep BPR as primary unless another target clearly beats it on CV MAE/R2/correlation and is explainable.

## Things To Be Careful About

- Do not use current D2 features that are not available for D2 players in the production model.
- Be careful with school stat pages that split offense/ball-control/rebounding tables; parser may need category merges.
- For Presto pages, player names may appear in `Last, First` format.
- For SIDEARM pages, profile pages may be blocked/template-only; team stats pages are usually better.
- Manual rows should include PF if available.
- Do not rely on `d2_data_cleaned.csv` event stats blindly until verified or validator-cleaned.
- If running large web fetches, use sleep and small batches to avoid rate limits or blocked pages.
