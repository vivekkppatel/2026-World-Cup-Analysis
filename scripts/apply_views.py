"""
scripts/apply_views.py
───────────────────────
(Re)create the BI views defined in database/views.sql.
Run after any schema change or view edit:
    python scripts/apply_views.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from sqlalchemy import text

from database.db import engine, health_check
from database.migrations import ensure_schema_upgrades

VIEWS_SQL = Path(__file__).parent.parent / "database" / "views.sql"


def main() -> None:
    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    ensure_schema_upgrades()  # views depend on migrated columns

    sql = VIEWS_SQL.read_text(encoding="utf-8")
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

        created = conn.execute(text("""
            SELECT table_name FROM information_schema.views
            WHERE table_schema = 'public' AND table_name LIKE 'v\\_%'
            ORDER BY table_name
        """)).fetchall()

    logger.info("✅ Views applied:")
    for (name,) in created:
        logger.info(f"   • {name}")


if __name__ == "__main__":
    main()
