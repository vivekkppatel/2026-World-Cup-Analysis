# Data Cleaning with SQL — A Walkthrough of *This* Project

This guide explains, in plain language, **how the messy raw data in this project was cleaned using SQL** (plus a little Python at the edges). Every technique here is one you'll use in any analyst job — the World Cup is just the example. Read it top-to-bottom and you'll understand both *what* was dirty and *the SQL pattern that fixed it*.

> **Mental model:** raw data arrives dirty from many places. Cleaning = making it (1) **consistent** (one spelling per thing), (2) **correct** (no duplicates, no wrong values), (3) **shaped** for analysis (one tidy row per observation). SQL is the tool because the data lives in a database and SQL is *declarative* — you describe the result you want, the engine figures out how.

---

## 0. The mess we started with

Four sources feed this project, and they disagreed with each other:

| Source | What it gives | How it was dirty |
|---|---|---|
| openfootball (JSON) | 2026 fixtures | Team names like `"USA"`, knockout slots as codes `"2A"`, `"W73"` |
| football-data.org (API) | Live scores, standings | `"Czechia"`, `"Bosnia-Herzegovina"` |
| StatsBomb (events) | Historical player stats | `"Center Back"` positions, no xA column |
| Kaggle (CSV) | Player form, FIFA ranks | **Mojibake**: `"Mbapp?"`, `"Cura?ao"`, `"T?rkiye"` |

The same country could appear as **four different strings**. If you don't fix that, "France" and "France " and "Frankreich" become four bars on a chart. This is the single most common real-world data problem: **entity resolution** (a.k.a. "the same thing spelled differently").

---

## 1. Entity resolution — one canonical name per team

**Problem:** `USA`, `United States`, `Czechia`, `Czech Republic` are the same teams under different names.

**Pattern:** a *canonical mapping* applied at every ingest point. In this project that's [`data/transform/team_aliases.py`](../data/transform/team_aliases.py) (Python, because it runs during ingestion), but the SQL equivalent is a **lookup/mapping table + JOIN**:

```sql
-- The SQL way: a mapping table
CREATE TABLE team_aliases (raw_name TEXT PRIMARY KEY, canonical TEXT);
INSERT INTO team_aliases VALUES
  ('USA', 'United States'),
  ('Czechia', 'Czech Republic'),
  ('Bosnia-Herzegovina', 'Bosnia & Herzegovina');

-- Apply it: COALESCE keeps the original name when there's no alias
SELECT COALESCE(a.canonical, raw.team) AS team
FROM raw_import raw
LEFT JOIN team_aliases a ON a.raw_name = raw.team;
```

**Why `LEFT JOIN` + `COALESCE`:** a `LEFT JOIN` keeps every raw row even if there's no alias; `COALESCE(x, y)` returns the first non-NULL, so known aliases get rewritten and everything else passes through unchanged. **This two-line idiom is the workhorse of name-cleaning.**

**Takeaway skill:** when two datasets won't join, the cause is almost always inconsistent keys. Build a mapping table, don't hand-edit rows.

---

## 2. Deduplication — collapsing rows that mean the same thing

**Problem:** because of the spelling differences, the `teams` table briefly held **59 rows for 48 teams** — duplicates like `United States` *and* `USA`.

**Pattern:** delete the duplicates, keep one, then add a `UNIQUE` constraint so it can't happen again. From [`database/migrations.py`](../database/migrations.py):

```sql
-- Keep the lowest id per name, delete the rest
DELETE FROM teams a USING teams b
WHERE a.id > b.id AND a.name = b.name;

-- Lock it down so re-runs can't reintroduce duplicates
CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_name ON teams (name);
```

**The general dedup pattern** (when "newest wins" or you want the best row, not just any):

```sql
DELETE FROM t
WHERE id NOT IN (
  SELECT DISTINCT ON (natural_key) id
  FROM t
  ORDER BY natural_key, updated_at DESC   -- keep the most recent per key
);
```

`DISTINCT ON (natural_key) ... ORDER BY natural_key, updated_at DESC` is PostgreSQL's "give me the freshest row per group" — memorize it.

**Takeaway skill:** dedup is two steps — *remove* existing dupes, then *prevent* future ones with a constraint. Doing only the first is a bug waiting to recur.

---

## 3. Idempotent upserts — loading data you can run twice safely

**Problem:** the loaders run repeatedly (every refresh). A naive `INSERT` would either crash on the second run or pile up duplicates.

**Pattern:** `INSERT ... ON CONFLICT ... DO UPDATE` (an "upsert" — insert-or-update). From [`scripts/refresh_live.py`](../scripts/refresh_live.py):

```sql
INSERT INTO matches (fifa_match_num, home_score, away_score, status, winner)
VALUES (:num, :hs, :as, :status, :winner)
ON CONFLICT (fifa_match_num) DO UPDATE SET
    home_score = EXCLUDED.home_score,
    away_score = EXCLUDED.away_score,
    status     = EXCLUDED.status,
    winner     = EXCLUDED.winner,
    updated_at = NOW();
```

`EXCLUDED` is the row you *tried* to insert; on a key collision you copy its values onto the existing row. The key (`fifa_match_num`) is the **natural identity** of a match — same match number, same row, always.

**Takeaway skill:** every load script should be *idempotent* — running it twice gives the same result as running it once. Upserts are how you get there.

---

## 4. NULL vs. zero — they are not the same, and conflating them lies

**Problem:** WC 2010/2014 come from a source with **goals but no xG**. If you store xG as `0`, the data says "these players had zero expected goals," which is false — you just *don't know*. That would drag every historical average toward zero.

**Pattern:** store the unknown as `NULL`, and guard every calculation:

```sql
-- NULLIF avoids divide-by-zero; NULL minutes → NULL per-90 (honest "no data")
ROUND(SUM(goals) * 90.0 / NULLIF(SUM(minutes_played), 0), 3) AS goals_p90
```

- `NULLIF(x, 0)` → returns `NULL` when `x` is 0, so `something / NULLIF(0)` is `NULL` (no crash) instead of a divide-by-zero error.
- Aggregates (`SUM`, `AVG`) **skip NULLs automatically**, so an unknown xG doesn't pollute the average — it's simply not counted.

**Takeaway skill:** `0` means "measured, and it was zero." `NULL` means "not measured." Keep them distinct or your averages will lie.

---

## 5. The analytical view — the clean contract on top of messy tables

**Problem:** BI tools (and your future self) shouldn't have to know the raw table quirks. They need clean, ready-to-chart shapes.

**Pattern:** a `VIEW` — a saved query that looks like a table. This is the **single most important idea** for analyst work: *the view is the clean layer; the raw tables can stay messy underneath.* From [`database/views.sql`](../database/views.sql):

```sql
CREATE OR REPLACE VIEW v_player_stats AS
SELECT
    p.name AS player, t.name AS team, m.tournament_label,
    SUM(s.goals)                                              AS goals,
    ROUND(SUM(s.xg), 2)                                       AS xg,
    ROUND(SUM(s.goals)*90.0 / NULLIF(SUM(s.minutes_played),0), 3) AS goals_p90
FROM player_match_stats s
JOIN players p ON p.id = s.player_id
JOIN matches m ON m.id = s.match_id
LEFT JOIN teams t ON t.id = s.team_id
GROUP BY p.id, p.name, t.name, m.tournament_label;
```

Three cleaning techniques live in this one view:
1. **JOINs** stitch IDs back to human-readable names (`player_id` → `"Lionel Messi"`).
2. **`GROUP BY` + `SUM`** rolls per-match rows up to one tidy row per player-per-tournament.
3. **`NULLIF`** keeps the per-90 math safe.

Connect Tableau/Power BI to `v_player_stats`, never to `player_match_stats`. When you fix a bug in the raw data, the view updates for free and no dashboard breaks.

**Takeaway skill:** build a **clean view layer** between raw tables and BI. It's the difference between a maintainable project and a fragile one.

---

## 6. Window functions — ranking without losing detail

**Problem:** you want each team's *rank within its group* (1st, 2nd, 3rd, 4th) but still want every team's row. A plain `GROUP BY` would collapse the rows; you'd lose the teams.

**Pattern:** a **window function** — it computes across a group *without* collapsing rows. From `v_group_standings`:

```sql
RANK() OVER (
    PARTITION BY group_name              -- restart ranking per group
    ORDER BY points DESC, goal_diff DESC, goals_for DESC
) AS position
```

`OVER (PARTITION BY ... ORDER BY ...)` is the heart of analytics SQL:
- `PARTITION BY group_name` → "rank within each group separately."
- `ORDER BY points DESC, ...` → the tiebreaker chain (points, then goal difference, then goals for — real football rules).
- Every team keeps its row; it just gains a `position` column.

Other window functions worth knowing: `ROW_NUMBER()` (unique 1,2,3…), `DENSE_RANK()` (no gaps after ties), `LAG()/LEAD()` (previous/next row — great for "goals vs last match"), `SUM() OVER (...)` (running totals).

**Takeaway skill:** when you hear "rank / running total / compare to previous row / top-N per group," reach for a **window function**, not a self-join.

---

## 7. Resolving placeholders with `COALESCE`

**Problem:** knockout fixtures exist before the teams are known — the slot is a code like `2A` ("Group A runner-up") or `W73` ("winner of match 73"). The bracket must show *something* useful in both states.

**Pattern:** `COALESCE` to fall back through a priority order:

```sql
COALESCE(t.name, m.home_placeholder, 'TBD') AS home_team
```

"Use the real team name **if** it's resolved; otherwise the placeholder code; otherwise `TBD`." One column, three levels of graceful degradation.

**Takeaway skill:** `COALESCE(a, b, c)` is your "first non-NULL wins" tool for fallbacks and default values everywhere.

---

## 8. Putting it together — the cleaning pipeline

```
Raw sources (4)                Cleaning step                       Clean output
─────────────                  ─────────────                       ────────────
openfootball / API     →  canonicalize names (mapping + COALESCE)  →
StatsBomb / Kaggle     →  dedup + UNIQUE constraint                →   teams, matches,
                       →  idempotent upsert (ON CONFLICT)          →   players,
                       →  NULL for unknown (not 0)                 →   player_match_stats
                                                                        │
                                                          GROUP BY + JOIN + window fns
                                                                        ▼
                                                              v_*  analytical VIEWS
                                                                        │
                                                                        ▼
                                                          Tableau / Power BI / notebooks
```

**The order matters:** resolve identities → dedup → load idempotently → expose clean views. Each step assumes the previous one is done.

---

## 9. Practice queries (run these in psql to learn by doing)

Connect: `& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d worldcup2026`

```sql
-- (a) GROUP BY + aggregation: goals per tournament
SELECT tournament_label, COUNT(*) AS players, SUM(goals) AS total_goals
FROM v_player_stats GROUP BY tournament_label ORDER BY total_goals DESC;

-- (b) Window function: each team's rank within its group
SELECT group_name, team, points,
       RANK() OVER (PARTITION BY group_name ORDER BY points DESC) AS pos
FROM v_group_standings ORDER BY group_name, pos;

-- (c) Self-comparison with a derived column: who outscored their xG most?
SELECT player, team, goals, xg, ROUND(goals - xg, 2) AS over_performance
FROM v_player_stats
WHERE tournament_label = 'WC 2022' AND minutes >= 270
ORDER BY over_performance DESC LIMIT 10;

-- (d) Filtering + NULL awareness: tournaments that actually have xG data
SELECT tournament_label, COUNT(*) FILTER (WHERE xg IS NOT NULL) AS rows_with_xg
FROM v_player_stats GROUP BY tournament_label ORDER BY 1;
```

Query (c) is the one to internalize: it computes a **derived metric** (`goals - xg`) that didn't exist in any source — that's the leap from *reporting data* to *analysis*.

---

## What to remember (the 8 transferable skills)

1. **Entity resolution** — mapping table + `LEFT JOIN` + `COALESCE`.
2. **Deduplication** — delete dupes *and* add a `UNIQUE` constraint.
3. **Idempotent upserts** — `INSERT ... ON CONFLICT ... DO UPDATE`.
4. **NULL ≠ 0** — `NULL` for unknown, guard math with `NULLIF`.
5. **View layer** — clean `v_*` views between raw tables and BI.
6. **Window functions** — rank/running-total/compare without collapsing rows.
7. **`COALESCE` fallbacks** — graceful defaults and placeholder handling.
8. **Tidy shape** — `GROUP BY` to one row per observation before charting.

Next: [`docs/BI_SETUP.md`](BI_SETUP.md) takes these clean views into Tableau & Power BI, and [`notebooks/02_eda_worked.ipynb`](../notebooks/02_eda_worked.ipynb) explores them with Python.
