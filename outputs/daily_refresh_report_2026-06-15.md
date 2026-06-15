# FIFA World Cup 2026 — Daily Data Refresh Report
**Date:** 2026-06-15  
**Run type:** Automated (scheduled task)  
**User present:** No  
**Report generated:** 2026-06-15 (automated inspection)

---

## Executive Summary

| # | Area | Status | Key Finding |
|---|------|--------|-------------|
| 1 | New match data (live fixtures/scores) | 🔴 | `refresh_live.py` last run Jun 11 — **4 days stale** |
| 2 | Schema integrity (flat-file sources) | ⚠️ | Fjelstul OK; Kaggle sources missing match_id/team_id; architecture is DB-backed (by design) |
| 3 | xG anomaly detection | ⚠️ BLOCKED | No xG data exists in filesystem; StatsBomb never materialized |
| 4 | Pipeline health | ⚠️ | `refresh_form.py` ran Jun 14 (✅); `refresh_live.py` stale since Jun 11 (🔴) |

**Primary action needed:** Run `python scripts/refresh_live.py` — live fixture data is 4 days stale during active tournament play.

---

## Delta from Jun 12 Report

| Item | Jun 12 | Jun 15 | Change |
|------|--------|--------|--------|
| `refresh_live.py` staleness | ~1 day | **4 days** | 🔴 Worsened |
| `refresh_form.py` staleness | Unknown | **1 day (ran Jun 14)** | ✅ Improved |
| `match_predictor.pkl` age | 0 days (just trained) | **3 days** | ⚠️ Aging |
| New commits | — | **0 commits since Jun 12** | — |
| xG data | Not present | Not present | No change |
| DB architecture clarity | Unclear | Confirmed: all pipeline → PostgreSQL | Resolved |

---

## 1. New Match Data Availability 🔴

### `refresh_live.py` — PRIMARY CONCERN
- **Last modified / last run:** Jun 11 23:46 (**4 days ago**)
- **Sources covered:** openfootball/worldcup.json (104 WC 2026 fixtures, no API key) + football-data.org standings (requires `FOOTBALL_DATA_API_KEY`)
- **Write target:** PostgreSQL via SQLAlchemy upserts (safe to re-run — idempotent)
- **Impact:** Fixture results and standings in the DB may be 4 matches behind if games have been played Jun 12–15

**Required action:** `python scripts/refresh_live.py`  
This script is safe to run at any time (all writes are upserts). There is no risk of data corruption.

### `refresh_form.py` — OK
- **Last modified / last run:** Jun 14 04:49 (**1 day ago** — within acceptable window)
- **Sources covered:** API-Football (last 20 matches per WC 2026 team, ~49 requests)
- **Write target:** PostgreSQL `team_recent_form` table with competition-weighted + recency-decayed form scores + Elo delta
- **Budget note:** API-Football free tier = 100 req/day; this script consumes ~49. Do not double-run in same UTC day.
- **Status:** ✅ Healthy

### Other scripts — Not recently run
| Script | Last Modified | Status |
|--------|---------------|--------|
| `load_fjelstul_history.py` | Jun 11 | Historical only — OK if fjelstul CSVs unchanged |
| `load_kaggle_data.py` | Jun 11 | Kaggle data is static — no staleness concern |
| `load_statsbomb_history.py` | Jun 11 | **Never successfully run** — no output materialized |
| `train_model.py` | Jun 12 | Model trained Jun 12; re-train if feature data updated |
| `run_bracket_sim.py` | Jun 12 | Depends on up-to-date fixture results in DB |

---

## 2. Schema Integrity ⚠️

### Architecture note (resolved since Jun 12)
The pipeline is **fully PostgreSQL-backed**. Ingestion scripts write to the DB via SQLAlchemy — no intermediate CSV/Parquet outputs are expected. The `outputs/` directory being empty of data files is **correct by design**, not a bug.

Schema is defined in `database/schema.sql` (Jun 11) and extended via `database/views.sql` (Jun 12). Migrations managed by `database/migrations.py` (Jun 11).

### Flat-file source schema check

**Fjelstul dataset** (`data/external/fjelstul/`) — ✅ PASS
| Required field | Present in | Notes |
|----------------|-----------|-------|
| `match_id` | `matches.csv` | Column `match_id` ✅ |
| `team_id` | `team_appearances.csv` | Column `team_id` ✅ |
| `timestamp` | `matches.csv` | `match_date` + `match_time` ✅ |
| `xG` | — | ⚠️ Expected absent — match-level file, no tracking data |
| `player_id` | `squads.csv` | ✅ |

No null/type issues detected in prior inspection. Historical dataset, not updated.

**Kaggle dataset** (`data/external/kaggle/`) — ⚠️ STRUCTURAL GAPS (known, unchanged)

`wc_all_matches.csv`:
- ❌ No `match_id` (uses string team names only — join requires fuzzy matching)
- ❌ No `team_id` (same — no numeric FK)
- ⚠️ `timestamp`: date present but no time
- ❌ No `xG` column
- ❌ No `player_id` (match-level aggregates only)

`fifa_world_cup_2026_golden_dataset.csv`:
- ❌ Missing all 5 required fields (match_id, team_id, timestamp, xG, player_id)
- Aggregated tournament statistics only — not joinable to the event model

**Recommendation:** Kaggle files should be treated as supplemental reference data only, not joined to the main event pipeline without an explicit ID-resolution step. This is unchanged from Jun 12.

---

## 3. xG Anomaly Detection ⚠️ BLOCKED

**Status: BLOCKED — no xG data materialized anywhere in the repository.**

- `data/ingest/statsbomb_loader.py` exists and has been compiled (`.pyc` present in `__pycache__`) but has never been run against a data source to produce output.
- No `xG` column exists in any flat file (Fjelstul and Kaggle are match-level aggregates).
- xG data, if it exists, would be in PostgreSQL — but no DB connection is available during this automated inspection.

**Anomaly thresholds to enforce once xG data is available:**

| Anomaly | Threshold | Action |
|---------|-----------|--------|
| Team xG per match | > 4.0 | 🔴 Flag for manual review |
| Player xG | exactly 0.000 | ⚠️ Possible tracking failure / imputation artifact |
| Any xG value | < 0 | 🔴 Data error — negative xG is physically impossible |

**Recommendation:** Run `scripts/load_statsbomb_history.py` and verify that StatsBomb event data for WC 2022 (or earlier tournaments) loads cleanly into the DB. This will enable xG anomaly checks in future automated runs.

---

## 4. Pipeline Status Summary ⚠️

### Script execution recency
| Script | Last Run | Staleness | Status |
|--------|----------|-----------|--------|
| `refresh_form.py` | Jun 14 04:49 | ~1 day | ✅ OK |
| `refresh_live.py` | Jun 11 23:46 | **4 days** | 🔴 Stale |
| `train_model.py` | Jun 12 05:15 | 3 days | ⚠️ Model aging |
| `load_statsbomb_history.py` | Never run | — | ⚠️ xG blocked |
| `seed_db.py` | Jun 8 | 7 days | ✅ Seed data only |

### Model artifact
- **`models/match_predictor.pkl`** — 1.7 KB, trained Jun 12
- ⚠️ **1.7 KB is suspiciously small** for a production Poisson/Elo blend model (flagged in Jun 12 report, still unresolved)
  - Possible causes: model serializes only parameters (not training data), feature list is minimal, or the `.pkl` is a stub/placeholder
  - `train_model.py` is 7.6 KB and references Poisson scoreline + ML blend — the output should be larger
  - **Recommendation:** Inspect `train_model.py` output section and run a prediction sanity check against known match results before relying on this artifact in production

### Git status
- **Last commit:** `e1135ff` (deployment artifacts — Dockerfile, render.yaml, vercel, guide) — no date shown but all scripts modified Jun 11–12
- **Commits since Jun 12:** 0
- No new code changes, pipeline updates, or schema migrations since the Jun 12 deployment commit

### No log files found
- `find . -name "*.log"` returned no results
- Pipeline scripts do not appear to write execution logs to disk
- **Recommendation:** Add `logging.basicConfig(filename=f'logs/refresh_{datetime.date.today()}.log', ...)` to `refresh_live.py` and `refresh_form.py` so automated runs are auditable without reading the DB

---

## Action Items (Priority Order)

| Priority | Action | Script/Command | Notes |
|----------|--------|----------------|-------|
| 🔴 P0 | Refresh live fixture/scores data | `python scripts/refresh_live.py` | Safe to run anytime; all upserts; takes ~30s |
| ⚠️ P1 | Investigate `match_predictor.pkl` size (1.7 KB) | Review `train_model.py` output; run `predict_wc2026.py` manually | Potential model integrity issue |
| ⚠️ P2 | Run StatsBomb loader to enable xG checks | `python scripts/load_statsbomb_history.py` | Required to unblock xG anomaly detection |
| ⚠️ P3 | Add execution logging to pipeline scripts | Edit `refresh_live.py`, `refresh_form.py` | Enables automated run auditing without DB access |
| ℹ️ P4 | Re-train model after live data refresh | `python scripts/train_model.py` | Run after P0 to update model on fresh features |

---

## Appendix: Key File Timestamps

```
scripts/refresh_form.py          Jun 14 04:49  (most recent execution)
scripts/refresh_live.py          Jun 11 23:46  ← 4 days stale
scripts/run_bracket_sim.py       Jun 12 05:18
scripts/predict_wc2026.py        Jun 12 05:18
scripts/train_model.py           Jun 12 05:15
models/match_predictor.pkl       Jun 12 05:15  (1.7 KB — suspicious)
database/views.sql               Jun 12 05:52
database/migrations.py           Jun 11 23:50
database/schema.sql              Jun 11 23:48
data/ingest/statsbomb_loader.py  Jun 11 (never run)
outputs/daily_refresh_report_2026-06-12.md  Jun 12 16:37
```

---

*Report auto-generated by scheduled task `fifa-daily-data-refresh-check`. No code changes made. Read-only inspection only.*
