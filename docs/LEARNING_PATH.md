# Learning Path — Data Analysis via the World Cup Project

Every module uses **this repo's data**, ends with something you can put in the
dashboard or talk about in an interview, and builds on the previous one.
Work through them in order. Module 2 (the EDA notebook) is the core.

**How to use this:** don't read passively. Open `notebooks/01_eda_worldcup.ipynb`,
write the code yourself, get it wrong, fix it. The struggle is the learning.

---

## Module 0 — The EDA Mindset (30 min read, lifetime habit)

EDA is **not** "make charts." It's structured skepticism: you interrogate a
dataset until you trust it enough to build on it. The loop:

```
ask a question → look at raw rows → quantify → visualize → interpret → new question
```

Three rules that separate analysts from chart-makers:

1. **Look at raw rows first.** Before any aggregate, `df.head(20)`. You'll catch
   wrong dtypes, weird encodings, duplicate rows that no summary stat reveals.
2. **Every chart answers a stated question.** If you can't say what question a
   plot answers, delete it.
3. **Hunt for what's wrong, not what's pretty.** This repo had three real data
   bugs (shootout xG inflation, a mislabeled "pass accuracy" metric, a stage
   field that broke training). All three were findable in 10 minutes of honest
   EDA. That's the skill interviews test.

Quant-finance bridge: EDA is due diligence. Nobody prices a security off a
dataset they haven't validated; same rule for features feeding a model.

---

## Module 1 — Pandas Core (1–2 days)

The 20% of pandas that does 80% of analyst work:

| Skill | The repo example to study |
|---|---|
| Boolean filtering | `events[events["type"] == "Shot"]` in `statsbomb_loader.py` |
| `groupby` + agg | `get_player_tournament_stats` — sum stats per player |
| `merge` + suffixes | `build_features` in `match_predictor.py` — home/away join |
| Derived columns | per-90 rates: `grouped[col] / (minutes / 90)` |
| Missingness | `.fillna()`, `.dropna(subset=...)`, and *when each is right* |

**Exercise:** without looking at the loader, recompute top-10 WC 2022 scorers
from raw events yourself. Then diff your numbers against the loader's. If they
disagree, find out why (hint: shootouts, own goals).

**Resource:** *Python for Data Analysis*, 3rd ed. (Wes McKinney) — free at
wesmckinney.com/book. Chapters 5, 8, 10 only.

---

## Module 2 — The EDA Notebook (2–3 days) ← START HERE

Work through `notebooks/01_eda_worldcup.ipynb`. It's structured as guided
discovery: worked examples first, then TODO cells where you drive. You will:

- Profile the raw StatsBomb events table (shape, dtypes, missingness)
- Fit a Poisson distribution to goals — the canonical football model
- Quantify the xG ↔ goals relationship (and why it breaks per-match)
- **Re-discover two real bugs** this codebase shipped with (sections 4a/4b)
- Build per-90 normalization from scratch and see why raw totals lie

Deliverable: a markdown cell with your five strongest findings, written so a
non-technical reader gets it. That becomes dashboard copy and interview ammo.

---

## Module 3 — Statistics You Actually Need (2–3 days)

Not a stats course — the four concepts this project runs on:

1. **Poisson processes.** Goals are rare events in fixed time → goal counts are
   ~Poisson(λ). This is why football is upset-prone (variance ≈ mean is huge
   when λ≈1.3) and why one match tells you almost nothing.
2. **Regression to the mean.** Teams that beat their xG in the group stage
   usually fall back in knockouts. Finance analog: outperformance rarely
   persists; don't chase last quarter's winner.
3. **Small-sample discipline.** A World Cup is 4–7 matches per team. Every
   per-team stat you show needs the implicit caveat "n=5". Notebook section 6
   makes this concrete.
4. **Correlation ≠ causation ≠ prediction.** Passes correlate with winning —
   does possession cause wins, or do winning teams pass more? You can't tell
   from this data. Say so out loud in interviews; it's a senior move.

**Resource:** *Seeing Theory* (seeing-theory.brown.edu) for intuition;
StatsBomb's "What is xG?" articles for the domain.

---

## Module 4 — SQL (2–3 days, after the DB is seeded)

Pandas and SQL are the same algebra in different clothes. Once `seed_db.py`
has run, do every one of these **in `psql` first, then replicate in pandas**:

1. Top scorer per group → `JOIN` + `GROUP BY` + `ROW_NUMBER() OVER (PARTITION BY ...)`
2. Running tournament goals per team by matchday → window `SUM() OVER (ORDER BY ...)`
3. Teams overperforming xG → `HAVING SUM(goals) > SUM(xg)`
4. Matches where the loser had more shots → self-join on `matches`

Window functions (#1, #2) are the single highest-yield SQL interview topic for
analyst roles. The schema in `database/schema.sql` is your playground.

**Resource:** mode.com/sql-tutorial (intermediate + window functions sections).

---

## Module 5 — Visualization Criticism (1 day)

You learn viz fastest by fixing bad charts. This repo ships one:

**Exercise:** open the Player Stats page radar chart. Plot Mbappé. Notice the
shape is all "Pressures/90" — because the radar plots *raw* per-90 values on a
shared axis, and pressures (~15/90) dwarf goals (~0.8/90). Fix
`player_radar()` in `app/utils/charts.py` to normalize each axis to a
percentile rank across the dataset. Before/after screenshot = portfolio gold.

Principles to internalize while you do it: shared axes need shared scales;
zero-baseline for bars; color encodes meaning, not decoration; every chart
title states the takeaway, not the variable names.

---

## Module 6 — Model Evaluation (2 days, ties into the odds feature)

Accuracy is the *weakest* way to judge a probability model. Learn the real
toolkit, in this order:

1. **Baselines first.** What's the accuracy of always predicting "home win"?
   Of predicting by FIFA ranking alone? Your model must beat the dumb baseline
   or it's decoration.
2. **Temporal split.** Train on WC 2018, test on WC 2022. Random k-fold leaks
   future information — interviewers *will* ask about this.
3. **Log loss & Brier score.** They punish confident wrongness; accuracy
   doesn't. A model saying 51% and one saying 99% on a wrong pick look the
   same to accuracy.
4. **Calibration curves.** Of all matches you called 60%, did ~60% happen?
   This is THE bridge to the betting-odds feature: bookmaker odds are
   ruthlessly calibrated; plotting your model against de-vigged market
   probabilities is exactly how trading desks benchmark pricing models.

**Exercise:** add `scripts/evaluate_model.py` — temporal split, all four
checks above. The output number ("X% accuracy, Brier Y vs market Z on held-out
2022") replaces the placeholder in your resume bullet.

---

## Module 7 — Communicating Findings (ongoing)

The analyst's product is the sentence, not the chart. For every analysis:
**finding → so what → recommendation**, in that order, no jargon. Practice
target: rewrite your five notebook findings as three bullets a hiring manager
skims in 10 seconds.

---

## Suggested sequencing against the tournament

| When | What |
|---|---|
| Now (group stage starts) | Modules 0–2 — EDA notebook on historical data |
| This week | Modules 3–4 — stats + SQL once DB is live |
| Week 2 | Modules 5–6 — fix the radar, build evaluation script |
| Knockouts | Module 7 — publish findings while matches are live |
