"""
scripts/refresh_live.py
────────────────────────
Pull current WC 2026 fixtures/results into PostgreSQL.

Sources, in order of authority:
  1. openfootball/worldcup.json — no API key, all 104 fixtures, scores
     lag a few hours behind live. Keyed on fifa_match_num.
  2. football-data.org — faster scores + official standings, requires
     FOOTBALL_DATA_API_KEY in .env. Currently only the standings table
     is written from this source; match reconciliation between the two
     sources is pending verification against a live API response.

Safe to run repeatedly (all writes are upserts). Schedule it:
    python scripts/refresh_live.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import pandas as pd
from sqlalchemy import text

from database.db import get_session, health_check
from database.migrations import ensure_schema_upgrades
from data.ingest.openfootball_loader import OpenFootballLoader
from data.transform.team_aliases import canonicalize

API_KEY_PLACEHOLDER = "your_api_key_here"


# ═══════════════════════════════════════════════════════════════════════════════
# openfootball → teams + matches
# ═══════════════════════════════════════════════════════════════════════════════

def _real_team_names(fixtures: pd.DataFrame) -> set[str]:
    """
    Teams appearing in group-stage rows are always real; knockout rows may
    contain unresolved placeholders like '2A' or 'W73' instead of teams.
    """
    group_rows = fixtures[fixtures["stage"] == "GROUP_STAGE"]
    return set(group_rows["home_team_name"]) | set(group_rows["away_team_name"])


def upsert_teams(fixtures: pd.DataFrame) -> dict[str, int]:
    """
    Upsert the 48 real WC 2026 teams (with group letters) and return a
    name → internal id map. Names already seeded from StatsBomb resolve
    to their existing rows and just gain a group assignment.
    """
    group_rows = fixtures[fixtures["stage"] == "GROUP_STAGE"]
    team_groups: dict[str, str] = {}
    for _, row in group_rows.iterrows():
        for side in ("home_team_name", "away_team_name"):
            team_groups[row[side]] = row["group_name"]

    with get_session() as session:
        for name, group in sorted(team_groups.items()):
            session.execute(text("""
                INSERT INTO teams (name, short_name, group_name)
                VALUES (:name, :short, :grp)
                ON CONFLICT (name) DO UPDATE SET group_name = EXCLUDED.group_name
            """), {"name": name, "short": name[:20], "grp": group})

        id_rows = session.execute(text("SELECT name, id FROM teams")).fetchall()

    logger.info(f"Upserted {len(team_groups)} WC 2026 teams.")
    return {name: tid for name, tid in id_rows}


def upsert_matches(fixtures: pd.DataFrame, team_ids: dict[str, int],
                   real_names: set[str]) -> tuple[int, int]:
    """
    Upsert all 104 fixtures keyed on fifa_match_num.
    Returns (total_rows, finished_rows).
    """
    finished = 0
    with get_session() as session:
        for _, m in fixtures.iterrows():
            home_real = m["home_team_name"] in real_names
            away_real = m["away_team_name"] in real_names
            if m["status"] == "FINISHED":
                finished += 1

            session.execute(text("""
                INSERT INTO matches (fifa_match_num, home_team_id, away_team_id,
                                     home_placeholder, away_placeholder,
                                     home_score, away_score, stage, group_name,
                                     kickoff_utc, venue, status, winner,
                                     competition, tournament_label)
                VALUES (:num, :home_id, :away_id, :home_ph, :away_ph,
                        :hs, :aws, :stage, :grp, :kickoff, :venue, :status, :winner,
                        'WORLD_CUP', 'WC 2026')
                ON CONFLICT (fifa_match_num) DO UPDATE SET
                    home_team_id     = EXCLUDED.home_team_id,
                    away_team_id     = EXCLUDED.away_team_id,
                    home_placeholder = EXCLUDED.home_placeholder,
                    away_placeholder = EXCLUDED.away_placeholder,
                    home_score       = EXCLUDED.home_score,
                    away_score       = EXCLUDED.away_score,
                    status           = EXCLUDED.status,
                    winner           = EXCLUDED.winner,
                    kickoff_utc      = EXCLUDED.kickoff_utc,
                    venue            = EXCLUDED.venue,
                    updated_at       = NOW()
            """), {
                "num":     int(m["match_number"]),
                "home_id": team_ids.get(m["home_team_name"]) if home_real else None,
                "away_id": team_ids.get(m["away_team_name"]) if away_real else None,
                "home_ph": None if home_real else (m["home_team_name"] or "")[:20],
                "away_ph": None if away_real else (m["away_team_name"] or "")[:20],
                "hs":      None if pd.isna(m["home_score"]) else int(m["home_score"]),
                "aws":     None if pd.isna(m["away_score"]) else int(m["away_score"]),
                "stage":   m["stage"],
                "grp":     m["group_name"] or None,
                "kickoff": m["kickoff_utc"],
                "venue":   (m["venue"] or "")[:100],
                "status":  m["status"],
                "winner":  m["winner"],
            })

    return len(fixtures), finished


def refresh_from_openfootball() -> None:
    fixtures = OpenFootballLoader().get_matches_2026()
    if fixtures.empty:
        logger.error("openfootball returned no matches — skipping.")
        return

    # One country, one identity — regardless of source spelling.
    fixtures["home_team_name"] = fixtures["home_team_name"].map(canonicalize)
    fixtures["away_team_name"] = fixtures["away_team_name"].map(canonicalize)

    real_names = _real_team_names(fixtures)
    team_ids = upsert_teams(fixtures)
    total, finished = upsert_matches(fixtures, team_ids, real_names)
    logger.info(f"Upserted {total} matches ({finished} finished).")


# ═══════════════════════════════════════════════════════════════════════════════
# API-Football → live scores (primary live source; requires APIFOOTBALL_KEY)
# ═══════════════════════════════════════════════════════════════════════════════

def refresh_from_apifootball() -> None:
    """
    Pull live WC 2026 scores from API-Football and update the matches table.

    API-Football is the real-time provider: openfootball seeds the fixtures,
    this overlays live scores/status onto them. Matches are matched by the
    canonicalised (home, away) team pair within WC 2026, so only fixtures
    whose teams are already known (group stage, and knockouts once resolved)
    get updated — exactly the ones that can have a score.
    """
    from data.ingest.apifootball_loader import ApiFootballLoader, ApiFootballConfigError
    try:
        loader = ApiFootballLoader()
    except ApiFootballConfigError as e:
        logger.info(f"API-Football not configured — skipping live scores. ({e})")
        return

    try:
        fixtures = loader.get_fixtures()
    except Exception as e:
        logger.error(f"API-Football fetch failed: {e}")
        return
    if fixtures.empty:
        logger.info("API-Football returned no WC 2026 fixtures yet.")
        return

    with get_session() as session:
        name_to_id = {n: i for n, i in
                      session.execute(text("SELECT name, id FROM teams")).fetchall()}
        updated = 0
        for _, fx in fixtures.iterrows():
            if fx["status"] == "SCHEDULED":
                continue  # nothing to write until there's a score/kickoff
            hid = name_to_id.get(fx["home_team_name"])
            aid = name_to_id.get(fx["away_team_name"])
            if hid is None or aid is None:
                continue
            res = session.execute(text("""
                UPDATE matches SET
                    home_score = :hs, away_score = :aws,
                    status = :status, winner = :winner, updated_at = NOW()
                WHERE tournament_label = 'WC 2026'
                  AND home_team_id = :hid AND away_team_id = :aid
            """), {
                "hs": None if pd.isna(fx["home_score"]) else int(fx["home_score"]),
                "aws": None if pd.isna(fx["away_score"]) else int(fx["away_score"]),
                "status": fx["status"], "winner": fx["winner"],
                "hid": hid, "aid": aid,
            })
            updated += res.rowcount
    logger.info(f"API-Football: updated {updated} live matches.")


# ═══════════════════════════════════════════════════════════════════════════════
# football-data.org → standings (requires API key)
# ═══════════════════════════════════════════════════════════════════════════════

def refresh_from_football_data() -> None:
    """
    Write official group standings from football-data.org.
    NOTE: field names in process_standings are unverified against a live
    v4 response (free key required) — treat the first run as a test.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not api_key or api_key == API_KEY_PLACEHOLDER:
        logger.info("No football-data.org API key set — skipping standings. "
                    "(Group standings remain available via the v_group_standings view.)")
        return

    from data.ingest.football_data_api import FootballDataClient
    from data.transform.processors import process_standings, process_teams

    client = FootballDataClient()
    try:
        raw_teams = client.get_teams()
        raw_standings = client.get_standings()
    except Exception as e:
        logger.error(f"football-data.org fetch failed: {e}")
        return

    teams_df = process_teams(raw_teams)
    teams_df["name"] = teams_df["name"].map(canonicalize)
    with get_session() as session:
        # Attach api_ids to existing rows by exact name; insert genuinely new teams.
        for _, t in teams_df.iterrows():
            session.execute(text("""
                INSERT INTO teams (api_id, name, short_name, tla, crest_url)
                VALUES (:api_id, :name, :short, :tla, :crest)
                ON CONFLICT (name) DO UPDATE SET
                    api_id = EXCLUDED.api_id,
                    tla = EXCLUDED.tla,
                    crest_url = EXCLUDED.crest_url
            """), {"api_id": int(t["api_id"]), "name": t["name"],
                   "short": t["short_name"][:20], "tla": (t["tla"] or "")[:3],
                   "crest": t["crest_url"]})

        standings_df = process_standings(raw_standings)
        for _, s in standings_df.iterrows():
            session.execute(text("""
                INSERT INTO standings (team_id, group_name, position, played, won,
                                       drawn, lost, goals_for, goals_against, points)
                SELECT id, :grp, :pos, :played, :won, :drawn, :lost, :gf, :ga, :pts
                FROM teams WHERE api_id = :team_api_id
                ON CONFLICT (team_id, group_name) DO UPDATE SET
                    position = EXCLUDED.position, played = EXCLUDED.played,
                    won = EXCLUDED.won, drawn = EXCLUDED.drawn, lost = EXCLUDED.lost,
                    goals_for = EXCLUDED.goals_for, goals_against = EXCLUDED.goals_against,
                    points = EXCLUDED.points, updated_at = NOW()
            """), {"team_api_id": int(s["team_api_id"]), "grp": s["group_name"],
                   "pos": s["position"], "played": s["played"], "won": s["won"],
                   "drawn": s["drawn"], "lost": s["lost"], "gf": s["goals_for"],
                   "ga": s["goals_against"], "pts": s["points"]})

    logger.info(f"Upserted official standings for {len(standings_df)} team-group rows.")


# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("═══════════════════════════════════════")
    logger.info("  WC 2026 — Live Data Refresh")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    ensure_schema_upgrades()
    refresh_from_openfootball()    # seeds all 104 fixtures + teams
    refresh_from_apifootball()     # overlays live scores (primary live source)
    refresh_from_football_data()   # official standings (optional)
    logger.info("✅ Refresh complete.")


if __name__ == "__main__":
    main()
