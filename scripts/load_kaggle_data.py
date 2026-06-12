"""
scripts/load_kaggle_data.py
────────────────────────────
Load the fetched Kaggle datasets into PostgreSQL:

1. Team enrichment — FIFA rank + confederation from wc_2026_teams.csv
   onto the existing teams rows (columns were NULL until now).
2. player_form_2026 — pre-tournament form snapshot for ~1,200 players
   (truncate-and-reload; the dataset is a point-in-time snapshot, not
   an incremental feed).

Prerequisite:  python scripts/fetch_kaggle_data.py
Run:           python scripts/load_kaggle_data.py
"""
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
from data.transform.team_aliases import canonicalize

KAGGLE_DIR = Path(__file__).parent.parent / "data" / "external" / "kaggle"


def _read_csv(path: Path) -> pd.DataFrame:
    """The community CSVs vary in encoding; try utf-8 then cp1252."""
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp1252")


def enrich_teams() -> None:
    """Fill teams.fifa_ranking and teams.confederation for the 48 squads."""
    path = KAGGLE_DIR / "wc_complete" / "wc_2026_teams.csv"
    if not path.exists():
        logger.warning(f"{path.name} not found — skipping team enrichment.")
        return

    df = _read_csv(path)
    df["team"] = df["team"].map(canonicalize)

    matched = 0
    with get_session() as session:
        for _, t in df.iterrows():
            result = session.execute(text("""
                UPDATE teams
                SET fifa_ranking = :rank, confederation = :conf
                WHERE name = :name
            """), {"rank": int(t["fifa_rank"]),
                   "conf": str(t["confederation"])[:20],
                   "name": t["team"]})
            matched += result.rowcount

    unmatched = len(df) - matched
    logger.info(f"Team enrichment: {matched} teams updated"
                + (f", {unmatched} names unmatched" if unmatched else ""))
    if unmatched:
        logger.warning("Unmatched names need entries in data/transform/team_aliases.py")


def load_player_form() -> None:
    """Truncate-and-reload the pre-tournament player form snapshot."""
    path = KAGGLE_DIR / "road_to_2026" / "fifa_world_cup_2026_golden_dataset.csv"
    if not path.exists():
        logger.warning(f"{path.name} not found — skipping player form load.")
        return

    df = _read_csv(path)
    df["team_canonical"] = df["team_name"].map(canonicalize)

    with get_session() as session:
        team_rows = session.execute(text("SELECT name, id FROM teams")).fetchall()
        team_ids = {name: tid for name, tid in team_rows}

        session.execute(text("TRUNCATE player_form_2026 RESTART IDENTITY"))
        for _, p in df.iterrows():
            session.execute(text("""
                INSERT INTO player_form_2026
                    (player_name, team_id, team_name_raw, group_name,
                     appearances, goals, assists, minutes,
                     total_contributions, contributions_per_90, efficiency_score)
                VALUES (:name, :team_id, :team_raw, :grp, :apps, :goals,
                        :assists, :minutes, :contrib, :per90, :eff)
                ON CONFLICT (player_name, team_name_raw) DO NOTHING
            """), {
                "name":     str(p["name"])[:150],
                "team_id":  team_ids.get(p["team_canonical"]),
                "team_raw": str(p["team_name"])[:100],
                "grp":      (str(p["group"]).strip()[:1] or None) if pd.notna(p["group"]) else None,
                "apps":     int(p["appearances"]),
                "goals":    int(p["goals"]),
                "assists":  int(p["assists"]),
                "minutes":  int(p["minutes"]),
                "contrib":  int(p["total_contributions"]),
                "per90":    float(p["contributions_per_90"]),
                "eff":      float(p["efficiency_score"]),
            })

        n = session.execute(text("SELECT COUNT(*) FROM player_form_2026")).scalar()
        n_linked = session.execute(text(
            "SELECT COUNT(*) FROM player_form_2026 WHERE team_id IS NOT NULL"
        )).scalar()

    logger.info(f"Player form: {n} rows loaded, {n_linked} linked to teams.")


def main() -> None:
    logger.info("═══════════════════════════════════════")
    logger.info("  Kaggle Datasets → PostgreSQL")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    ensure_schema_upgrades()
    enrich_teams()
    load_player_form()
    logger.info("✅ Kaggle data load complete.")


if __name__ == "__main__":
    main()
