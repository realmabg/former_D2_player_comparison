# Current D2 RealGM Verification Workflow

Use this when the bulk current-D2 file has suspicious event stats, or when you
want RealGM as a second source for current D2 player rows.

## Why This Exists

The current dashboard starts from `d2_data_cleaned.csv`, which has broad
coverage but includes some corrupted event stats. The RealGM script searches
for each player, checks candidate player profiles, matches the stat row to the
current D2 school, and writes verified stat overrides.

The script defaults to `--fetcher chrome` because RealGM often returns `403
Forbidden` to plain Python requests.

The dashboard builder automatically reads:

- `data/current_d2_realgm_verified_stats.csv`
- `data/current_d2_verified_stats.csv`

If both files contain the same player/team, `data/current_d2_verified_stats.csv`
wins because it is intended for manual or school-page verified rows.

## Recommended Run

Start with the suspicious rows only:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py

.venv/bin/python scripts/fetch_current_d2_realgm_stats.py \
  --mode suspicious \
  --fetcher chrome \
  --sleep 5 \
  --append
```

Then rebuild the dashboard data:

```bash
.venv/bin/python scripts/build_projection_dashboard_data.py
```

## Small Test Run

Use this before a long run:

```bash
.venv/bin/python scripts/fetch_current_d2_realgm_stats.py \
  --mode suspicious \
  --fetcher chrome \
  --limit 10 \
  --sleep 5
```

## Specific Players Only

```bash
.venv/bin/python scripts/fetch_current_d2_realgm_stats.py \
  --names "Kolby Watson" "Kolby Horace" \
  --fetcher chrome \
  --sleep 5 \
  --append
```

## Full 4,303-Player Run

Only do this if you are okay with a long run and possible RealGM rate limiting:

```bash
.venv/bin/python scripts/fetch_current_d2_realgm_stats.py \
  --mode all \
  --fetcher chrome \
  --sleep 5 \
  --append
```

Outputs:

- `data/current_d2_realgm_verified_stats.csv`
- `data/current_d2_realgm_missing.csv`
- cached search/profile HTML under `data/cache/current_d2_realgm/`

## Notes

RealGM may not have every D2 player, and some names are ambiguous. The script
requires both a reasonable player-name match and a current-school match before
writing an override. Rows it cannot confidently match go to
`data/current_d2_realgm_missing.csv`.
