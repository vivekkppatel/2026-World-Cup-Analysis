"""
database/migrations.py
───────────────────────
Idempotent schema upgrades applied on top of schema.sql.

schema.sql creates tables with IF NOT EXISTS, so existing databases never
pick up new columns from it. Every upgrade here must be safe to run
repeatedly (ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS).

Called by: scripts/refresh_live.py, scripts/load_statsbomb_history.py
"""
import logging

from sqlalchemy import text

from database.db import engine

logger = logging.getLogger(__name__)

# Ordered list of idempotent upgrade statements.
_UPGRADES = [
    # teams.name needs a unique index so name-keyed upserts work.
    # (seed_db's ON CONFLICT DO NOTHING was a no-op without it — re-running
    # the seed could duplicate teams, so dedupe before creating the index.)
    """
    DELETE FROM teams a USING teams b
    WHERE a.id > b.id AND a.name = b.name
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_name ON teams (name)",

    # Stable natural key for WC 2026 fixtures (official FIFA match number
    # 1–104, derived from openfootball schedule order). football-data.org
    # rows key on api_id instead; this column lets both sources coexist.
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS fifa_match_num SMALLINT",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_matches_fifa_num ON matches (fifa_match_num)",

    # Knockout slots before qualification is decided ('2A', 'W73', …).
    # Kept as text so fixtures can display 'Winner of Match 73' style labels
    # while team_id stays NULL until the slot resolves.
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_placeholder VARCHAR(20)",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_placeholder VARCHAR(20)",

    # Tournament dimension. With Euros/Copa/AFCON joining the WCs in one
    # matches table, kickoff year alone is ambiguous (Euro 2024 vs Copa 2024
    # share 2024; Euro 2020 was played in 2021). tournament_label is the
    # human-readable BI slice ('WC 2022', 'EURO 2024'); competition groups
    # them ('WORLD_CUP', 'EURO', 'COPA_AMERICA', 'AFCON').
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS competition VARCHAR(20)",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS tournament_label VARCHAR(20)",
    # Backfill rows written before these columns existed — at that point the
    # table only held World Cup matches, so the year-derived label is safe.
    """
    UPDATE matches
    SET competition = 'WORLD_CUP',
        tournament_label = 'WC ' || EXTRACT(YEAR FROM kickoff_utc)::int
    WHERE competition IS NULL AND kickoff_utc IS NOT NULL
    """,

    # Fjelstul World Cup Database ids (e.g. 'M-2014-01', 'P-09032') for the
    # 2010/2014 tournaments, which predate StatsBomb open data coverage.
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS fjelstul_id VARCHAR(20)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_matches_fjelstul ON matches (fjelstul_id)",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS fjelstul_id VARCHAR(20)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_players_fjelstul ON players (fjelstul_id)",

    # Pre-tournament player form snapshot (Kaggle "Road to 2026" dataset).
    # Separate table: this is club/NT form BEFORE the tournament, not
    # per-match tournament output — joining it to CPCS later answers
    # "did pre-tournament form predict tournament performance?"
    """
    CREATE TABLE IF NOT EXISTS player_form_2026 (
        id                    SERIAL PRIMARY KEY,
        player_name           VARCHAR(150) NOT NULL,
        team_id               INTEGER REFERENCES teams(id),
        team_name_raw         VARCHAR(100),
        group_name            CHAR(1),
        appearances           SMALLINT,
        goals                 SMALLINT,
        assists               SMALLINT,
        minutes               INTEGER,
        total_contributions   SMALLINT,
        contributions_per_90  NUMERIC(6,3),
        efficiency_score      NUMERIC(8,3),
        loaded_at             TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (player_name, team_name_raw)
    )
    """,
]


def ensure_schema_upgrades() -> None:
    """Apply all pending idempotent upgrades. Raises on failure."""
    with engine.connect() as conn:
        for stmt in _UPGRADES:
            conn.execute(text(stmt))
        conn.commit()
    logger.info("Schema upgrades applied (%d statements).", len(_UPGRADES))
