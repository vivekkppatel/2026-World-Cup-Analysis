-- ============================================================
-- World Cup 2026 Analytics — BI Views
-- ============================================================
-- The contract between PostgreSQL and Tableau / Power BI.
-- BI tools connect to these views, never to raw tables, so the
-- underlying schema can evolve without breaking dashboards.
--
-- Apply with:  python scripts/apply_views.py
-- ============================================================

-- Recreate from scratch: CREATE OR REPLACE cannot change a view's
-- column list, and these evolve with the schema.
DROP VIEW IF EXISTS v_top_scorers CASCADE;
DROP VIEW IF EXISTS v_group_standings, v_match_results, v_upcoming_fixtures,
                    v_player_stats, v_team_match_stats, v_player_form_2026,
                    v_predictions_vs_results, v_bracket_predictions,
                    v_model_scorecard CASCADE;

-- ── 1. Group standings, computed live from match results ─────
-- Derived from the matches table rather than read from the
-- standings table, so it is always consistent with stored results
-- (the standings table is only populated once the football-data.org
-- key is configured). Tiebreakers: points, goal diff, goals for.
-- Head-to-head (FIFA criterion 4+) is not implemented.
CREATE OR REPLACE VIEW v_group_standings AS
WITH results AS (
    SELECT home_team_id AS team_id, home_score AS gf, away_score AS ga
    FROM matches
    WHERE stage = 'GROUP_STAGE' AND status = 'FINISHED'
      AND EXTRACT(YEAR FROM kickoff_utc) = 2026
      AND home_team_id IS NOT NULL AND away_team_id IS NOT NULL
    UNION ALL
    SELECT away_team_id, away_score, home_score
    FROM matches
    WHERE stage = 'GROUP_STAGE' AND status = 'FINISHED'
      AND EXTRACT(YEAR FROM kickoff_utc) = 2026
      AND home_team_id IS NOT NULL AND away_team_id IS NOT NULL
),
agg AS (
    SELECT team_id,
           COUNT(*)                              AS played,
           SUM((gf > ga)::int)                   AS won,
           SUM((gf = ga)::int)                   AS drawn,
           SUM((gf < ga)::int)                   AS lost,
           SUM(gf)                               AS goals_for,
           SUM(ga)                               AS goals_against,
           SUM((gf > ga)::int) * 3 + SUM((gf = ga)::int) AS points
    FROM results
    GROUP BY team_id
)
SELECT
    t.group_name,
    RANK() OVER (
        PARTITION BY t.group_name
        ORDER BY COALESCE(a.points, 0) DESC,
                 COALESCE(a.goals_for - a.goals_against, 0) DESC,
                 COALESCE(a.goals_for, 0) DESC,
                 t.name
    )                                  AS position,
    t.name                             AS team,
    t.tla,
    COALESCE(a.played, 0)              AS played,
    COALESCE(a.won, 0)                 AS won,
    COALESCE(a.drawn, 0)               AS drawn,
    COALESCE(a.lost, 0)                AS lost,
    COALESCE(a.goals_for, 0)           AS goals_for,
    COALESCE(a.goals_against, 0)       AS goals_against,
    COALESCE(a.goals_for - a.goals_against, 0) AS goal_diff,
    COALESCE(a.points, 0)              AS points
FROM teams t
LEFT JOIN agg a ON a.team_id = t.id
WHERE t.group_name IS NOT NULL;

-- ── 2. Match results (all tournaments in the DB) ──────────────
CREATE OR REPLACE VIEW v_match_results AS
SELECT
    m.fifa_match_num,
    m.competition,
    m.tournament_label,
    EXTRACT(YEAR FROM m.kickoff_utc)::int AS tournament_year,
    m.kickoff_utc,
    m.stage,
    m.group_name,
    th.name  AS home_team,
    ta.name  AS away_team,
    m.home_score,
    m.away_score,
    CASE m.winner
        WHEN 'HOME' THEN th.name
        WHEN 'AWAY' THEN ta.name
        WHEN 'DRAW' THEN 'Draw'
    END      AS result,
    m.venue
FROM matches m
LEFT JOIN teams th ON th.id = m.home_team_id
LEFT JOIN teams ta ON ta.id = m.away_team_id
WHERE m.status = 'FINISHED';

-- ── 3. Upcoming fixtures ──────────────────────────────────────
-- Placeholders ('2A' = group A runner-up, 'W73' = winner of match
-- 73) show until knockout slots resolve.
CREATE OR REPLACE VIEW v_upcoming_fixtures AS
SELECT
    m.fifa_match_num,
    m.kickoff_utc,
    m.stage,
    m.group_name,
    COALESCE(th.name, m.home_placeholder, 'TBD') AS home_team,
    COALESCE(ta.name, m.away_placeholder, 'TBD') AS away_team,
    m.venue,
    m.status
FROM matches m
LEFT JOIN teams th ON th.id = m.home_team_id
LEFT JOIN teams ta ON ta.id = m.away_team_id
WHERE m.status <> 'FINISHED'
ORDER BY m.kickoff_utc;

-- ── 4. Player tournament stats with per-90 rates ──────────────
-- One row per player per tournament. Event-level metrics (xG, passes,
-- pressures) exist for StatsBomb-covered tournaments (WC 2018/2022,
-- EURO 2020/2024, COPA 2024, AFCON 2023); WC 2010/2014 rows carry
-- goals only — other metrics are NULL, not zero.
CREATE OR REPLACE VIEW v_player_stats AS
SELECT
    p.name                                  AS player,
    p.position,
    t.name                                  AS team,
    m.competition,
    m.tournament_label,
    MIN(EXTRACT(YEAR FROM m.kickoff_utc))::int AS tournament_year,
    COUNT(*)                                AS matches_played,
    SUM(s.minutes_played)                   AS minutes,
    SUM(s.goals)                            AS goals,
    SUM(s.assists)                          AS assists,
    ROUND(SUM(s.xg), 2)                     AS xg,
    SUM(s.shots)                            AS shots,
    SUM(s.passes)                           AS passes,
    SUM(s.key_passes)                       AS key_passes,
    SUM(s.pressures)                        AS pressures,
    SUM(s.tackles)                          AS tackles,
    ROUND(SUM(s.goals)      * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS goals_p90,
    ROUND(SUM(s.assists)    * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS assists_p90,
    ROUND(SUM(s.xg)         * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS xg_p90,
    ROUND(SUM(s.shots)      * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS shots_p90,
    ROUND(SUM(s.key_passes) * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS key_passes_p90,
    ROUND(SUM(s.pressures)  * 90.0 / NULLIF(SUM(s.minutes_played), 0), 3) AS pressures_p90
FROM player_match_stats s
JOIN players p ON p.id = s.player_id
JOIN matches m ON m.id = s.match_id
LEFT JOIN teams t ON t.id = s.team_id
GROUP BY p.id, p.name, p.position, t.name, m.competition, m.tournament_label;

-- ── 5. Top scorers per tournament ─────────────────────────────
CREATE OR REPLACE VIEW v_top_scorers AS
SELECT
    competition,
    tournament_label,
    tournament_year,
    player,
    team,
    goals,
    assists,
    xg,
    minutes,
    RANK() OVER (PARTITION BY tournament_label
                 ORDER BY goals DESC, xg DESC NULLS LAST) AS scorer_rank
FROM v_player_stats
WHERE goals > 0;

-- ── 6. Team performance per match (xG dashboard feed) ─────────
CREATE OR REPLACE VIEW v_team_match_stats AS
SELECT
    m.competition,
    m.tournament_label,
    EXTRACT(YEAR FROM m.kickoff_utc)::int AS tournament_year,
    m.kickoff_utc,
    m.stage,
    t.name                                AS team,
    CASE WHEN s.team_id = m.home_team_id THEN ta.name ELSE th.name END AS opponent,
    CASE WHEN s.team_id = m.home_team_id THEN m.home_score ELSE m.away_score END AS goals_scored,
    CASE WHEN s.team_id = m.home_team_id THEN m.away_score ELSE m.home_score END AS goals_conceded,
    ROUND(SUM(s.xg), 2)                   AS team_xg,
    SUM(s.shots)                          AS shots,
    SUM(s.passes)                         AS passes,
    SUM(s.pressures)                      AS pressures
FROM player_match_stats s
JOIN matches m  ON m.id  = s.match_id
JOIN teams   t  ON t.id  = s.team_id
LEFT JOIN teams th ON th.id = m.home_team_id
LEFT JOIN teams ta ON ta.id = m.away_team_id
GROUP BY m.id, m.competition, m.tournament_label, m.kickoff_utc, m.stage,
         t.name, s.team_id, m.home_team_id, m.home_score, m.away_score,
         th.name, ta.name;

-- ── 7. Pre-tournament player form (Road to 2026 snapshot) ─────
-- Community-sourced Kaggle data: club/NT form BEFORE the tournament.
-- Once WC 2026 player stats accumulate, join to v_player_stats to ask
-- "did pre-tournament form predict tournament output?"
CREATE OR REPLACE VIEW v_player_form_2026 AS
SELECT
    f.player_name,
    COALESCE(t.name, f.team_name_raw) AS team,
    COALESCE(t.group_name, f.group_name) AS group_name,
    t.fifa_ranking AS team_fifa_rank,
    t.confederation,
    f.appearances,
    f.goals,
    f.assists,
    f.minutes,
    f.total_contributions,
    f.contributions_per_90,
    f.efficiency_score
FROM player_form_2026 f
LEFT JOIN teams t ON t.id = f.team_id;

-- ── 8. Model predictions vs. actual results ───────────────────
-- Evaluation feed: join stored predictions to outcomes once
-- matches finish. Empty until predictions are written to the DB.
CREATE OR REPLACE VIEW v_predictions_vs_results AS
SELECT
    m.fifa_match_num,
    m.kickoff_utc,
    th.name           AS home_team,
    ta.name           AS away_team,
    pr.home_win_prob,
    pr.draw_prob,
    pr.away_win_prob,
    pr.predicted_winner,
    m.winner          AS actual_winner,
    (pr.predicted_winner = m.winner) AS prediction_correct,
    pr.model_version
FROM predictions pr
JOIN matches m  ON m.id = pr.match_id
LEFT JOIN teams th ON th.id = m.home_team_id
LEFT JOIN teams ta ON ta.id = m.away_team_id;

-- ── 9. Team advancement probabilities (Monte Carlo bracket) ───
-- Populated by scripts/run_bracket_sim.py. One row per WC 2026 team
-- with its simulated probability of reaching each knockout round.
CREATE OR REPLACE VIEW v_bracket_predictions AS
SELECT
    a.team_name        AS team,
    t.group_name,
    t.fifa_ranking     AS fifa_rank,
    a.strength,
    a.reached_r32,
    a.reached_r16,
    a.reached_qf,
    a.reached_sf,
    a.reached_final,
    a.won_cup,
    a.model_version
FROM team_advancement a
LEFT JOIN teams t ON t.id = a.team_id
ORDER BY a.won_cup DESC;

-- ── 10. Model scorecard — accuracy KPIs as results land ───────
-- The headline KPI feed: per-match Brier score and hit/miss for every
-- finished, predicted match. Aggregate in BI for overall Brier, hit
-- rate, and round-by-round skill. Brier = mean squared error between
-- the predicted-winner probability and the realised 0/1 outcome.
CREATE OR REPLACE VIEW v_model_scorecard AS
SELECT
    m.fifa_match_num,
    m.tournament_label,
    m.stage,
    th.name AS home_team,
    ta.name AS away_team,
    pr.predicted_winner,
    m.winner AS actual_winner,
    GREATEST(pr.home_win_prob, pr.away_win_prob) AS predicted_confidence,
    (pr.predicted_winner = m.winner)             AS hit,
    -- Brier for the binary "did the predicted side win?" event
    POWER(GREATEST(pr.home_win_prob, pr.away_win_prob)
          - (pr.predicted_winner = m.winner)::int, 2) AS brier,
    pr.model_version
FROM predictions pr
JOIN matches m ON m.id = pr.match_id
LEFT JOIN teams th ON th.id = m.home_team_id
LEFT JOIN teams ta ON ta.id = m.away_team_id
WHERE m.status = 'FINISHED' AND m.winner IS NOT NULL;
