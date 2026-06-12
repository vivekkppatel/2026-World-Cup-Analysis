-- ============================================================
-- World Cup 2026 Analytics Platform — PostgreSQL Schema
-- ============================================================

-- ── Teams ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    id              SERIAL PRIMARY KEY,
    api_id          INTEGER UNIQUE,          -- football-data.org team id
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(20),
    tla             CHAR(3),                 -- 3-letter abbreviation
    crest_url       TEXT,
    group_name      CHAR(1),                 -- 'A' through 'L'
    confederation   VARCHAR(20),             -- UEFA, CONMEBOL, etc.
    fifa_ranking    INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Players ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS players (
    id              SERIAL PRIMARY KEY,
    api_id          INTEGER UNIQUE,
    statsbomb_id    INTEGER UNIQUE,
    fjelstul_id     VARCHAR(20) UNIQUE,      -- Fjelstul DB id, e.g. 'P-09032'
    name            VARCHAR(150) NOT NULL,
    position        VARCHAR(30),             -- GK, CB, LB, CM, CAM, ST …
    nationality     VARCHAR(100),
    date_of_birth   DATE,
    team_id         INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    shirt_number    SMALLINT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Matches ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    id              SERIAL PRIMARY KEY,
    api_id          INTEGER UNIQUE,          -- football-data.org match id
    statsbomb_id    INTEGER UNIQUE,          -- StatsBomb match id (historical)
    fifa_match_num  SMALLINT UNIQUE,         -- official WC2026 match number 1-104
    fjelstul_id     VARCHAR(20) UNIQUE,      -- Fjelstul DB id, e.g. 'M-2014-01'
    competition     VARCHAR(20),             -- WORLD_CUP | EURO | COPA_AMERICA | AFCON
    tournament_label VARCHAR(20),            -- 'WC 2022', 'EURO 2024', …
    home_team_id    INTEGER REFERENCES teams(id),
    away_team_id    INTEGER REFERENCES teams(id),
    home_placeholder VARCHAR(20),            -- unresolved KO slot, e.g. '2A', 'W73'
    away_placeholder VARCHAR(20),
    home_score      SMALLINT,
    away_score      SMALLINT,
    stage           VARCHAR(30),             -- 'GROUP_STAGE', 'ROUND_OF_16', etc.
    group_name      CHAR(1),
    match_day       SMALLINT,
    kickoff_utc     TIMESTAMPTZ,
    venue           VARCHAR(100),
    city            VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'SCHEDULED', -- SCHEDULED | IN_PLAY | FINISHED
    winner          VARCHAR(10),             -- 'HOME' | 'AWAY' | 'DRAW'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Group Standings ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS standings (
    id              SERIAL PRIMARY KEY,
    team_id         INTEGER REFERENCES teams(id),
    group_name      CHAR(1),
    position        SMALLINT,
    played          SMALLINT DEFAULT 0,
    won             SMALLINT DEFAULT 0,
    drawn           SMALLINT DEFAULT 0,
    lost            SMALLINT DEFAULT 0,
    goals_for       SMALLINT DEFAULT 0,
    goals_against   SMALLINT DEFAULT 0,
    goal_diff       SMALLINT GENERATED ALWAYS AS (goals_for - goals_against) STORED,
    points          SMALLINT DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (team_id, group_name)
);

-- ── Player Match Statistics ───────────────────────────────────
CREATE TABLE IF NOT EXISTS player_match_stats (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER REFERENCES players(id),
    match_id        INTEGER REFERENCES matches(id),
    team_id         INTEGER REFERENCES teams(id),
    minutes_played  SMALLINT DEFAULT 0,
    goals           SMALLINT DEFAULT 0,
    assists         SMALLINT DEFAULT 0,
    shots           SMALLINT DEFAULT 0,
    shots_on_target SMALLINT DEFAULT 0,
    xg              NUMERIC(5,3) DEFAULT 0,   -- expected goals
    xa              NUMERIC(5,3) DEFAULT 0,   -- expected assists
    passes          SMALLINT DEFAULT 0,
    pass_accuracy   NUMERIC(4,1),             -- percent
    key_passes      SMALLINT DEFAULT 0,
    dribbles        SMALLINT DEFAULT 0,
    dribble_success SMALLINT DEFAULT 0,
    pressures       SMALLINT DEFAULT 0,
    tackles         SMALLINT DEFAULT 0,
    interceptions   SMALLINT DEFAULT 0,
    progressive_carries    SMALLINT DEFAULT 0,
    progressive_passes     SMALLINT DEFAULT 0,
    yellow_cards    SMALLINT DEFAULT 0,
    red_cards       SMALLINT DEFAULT 0,
    player_rating   NUMERIC(4,2),             -- computed composite score
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (player_id, match_id)
);

-- ── Tournament Goal Events ────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER REFERENCES matches(id),
    scorer_id       INTEGER REFERENCES players(id),
    assist_id       INTEGER REFERENCES players(id),
    team_id         INTEGER REFERENCES teams(id),
    minute          SMALLINT,
    penalty         BOOLEAN DEFAULT FALSE,
    own_goal        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Match Predictions ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER REFERENCES matches(id) UNIQUE,
    home_win_prob   NUMERIC(5,4),
    draw_prob       NUMERIC(5,4),
    away_win_prob   NUMERIC(5,4),
    predicted_winner VARCHAR(10),            -- 'HOME' | 'AWAY' | 'DRAW'
    model_version   VARCHAR(20),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_name          ON teams(name);
CREATE INDEX IF NOT EXISTS idx_matches_status         ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_stage          ON matches(stage);
CREATE INDEX IF NOT EXISTS idx_player_match_player_id ON player_match_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_match_match_id  ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_standings_group        ON standings(group_name);
CREATE INDEX IF NOT EXISTS idx_goals_match            ON goals(match_id);
CREATE INDEX IF NOT EXISTS idx_goals_scorer           ON goals(scorer_id);
