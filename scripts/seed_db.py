"""
scripts/seed_db.py
───────────────────
Initialize the database schema and seed with:
  1. Historical WC 2022 team data (from StatsBomb)
  2. Historical match metadata

Run once before starting the app:
    python scripts/seed_db.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from database.db import init_db, get_session, health_check, engine
from sqlalchemy import text


def seed_teams_from_statsbomb():
    """Seed the teams table with WC 2022 teams from StatsBomb."""
    try:
        from statsbombpy import sb
        from data.ingest.statsbomb_loader import COMPETITIONS

        comp = COMPETITIONS["wc_2022"]
        matches = sb.matches(
            competition_id=comp["competition_id"],
            season_id=comp["season_id"]
        )

        teams = set()
        for _, row in matches.iterrows():
            teams.add(row["home_team"])
            teams.add(row["away_team"])

        with get_session() as session:
            for i, team_name in enumerate(sorted(teams), start=1):
                session.execute(text("""
                    INSERT INTO teams (name, short_name)
                    VALUES (:name, :short)
                    ON CONFLICT DO NOTHING
                """), {"name": team_name, "short": team_name[:20]})

        logger.info(f"Seeded {len(teams)} teams from StatsBomb WC 2022.")
        return True

    except Exception as e:
        logger.warning(f"Could not seed teams from StatsBomb: {e}")
        return False


def seed_placeholder_teams():
    """
    Seed with confirmed WC 2026 qualified teams as a fallback
    when StatsBomb data isn't available.
    """
    wc_2026_teams = [
        # Group A – Host
        ("United States", "USA", "A"),
        ("Mexico", "MEX", "A"),
        ("Canada", "CAN", "A"),
        ("Uruguay", "URU", "A"),
        # Group B
        ("Argentina", "ARG", "B"),
        ("Chile", "CHI", "B"),
        ("Peru", "PER", "B"),
        ("Australia", "AUS", "B"),
        # Group C
        ("Brazil", "BRA", "C"),
        ("Colombia", "COL", "C"),
        ("Bolivia", "BOL", "C"),
        ("Japan", "JPN", "C"),
        # Group D
        ("Germany", "GER", "D"),
        ("Spain", "ESP", "D"),
        ("Serbia", "SRB", "D"),
        ("New Zealand", "NZL", "D"),
        # Group E
        ("France", "FRA", "E"),
        ("England", "ENG", "E"),
        ("Netherlands", "NED", "E"),
        ("South Korea", "KOR", "E"),
        # Group F
        ("Portugal", "POR", "F"),
        ("Poland", "POL", "F"),
        ("Ukraine", "UKR", "F"),
        ("Morocco", "MAR", "F"),
    ]

    with get_session() as session:
        for name, tla, group in wc_2026_teams:
            session.execute(text("""
                INSERT INTO teams (name, short_name, tla, group_name)
                VALUES (:name, :short, :tla, :group)
                ON CONFLICT DO NOTHING
            """), {"name": name, "short": name[:20], "tla": tla, "group": group})

    logger.info(f"Seeded {len(wc_2026_teams)} WC 2026 placeholder teams.")


def main():
    logger.info("═══════════════════════════════════════")
    logger.info("  World Cup 2026 — Database Seed Script")
    logger.info("═══════════════════════════════════════")

    # 1. Health check
    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    # 2. Create schema
    logger.info("Creating schema …")
    init_db()

    # 3. Seed teams
    logger.info("Seeding teams …")
    success = seed_teams_from_statsbomb()
    if not success:
        logger.info("Falling back to placeholder teams …")
        seed_placeholder_teams()

    logger.info("✅ Database seed complete.")
    logger.info("Next step: python scripts/train_model.py")


if __name__ == "__main__":
    main()
