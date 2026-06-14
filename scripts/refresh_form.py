"""
scripts/refresh_form.py
────────────────────────
Pull each WC 2026 team's recent form from API-Football, compute a
competition-weighted + recency-decayed form score, and cache it in
team_recent_form. The match predictor reads this to nudge its expected goals
toward current form (the reference-notebook enrichment).

Budget note: API-Football's free tier is 100 requests/day. This makes ~49
requests (1 for team ids + 1 per team), so run it once or twice a day — NOT
on every page load. The result is cached in Postgres and read for free.

Run:
    python scripts/refresh_form.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from sqlalchemy import text

from database.db import get_session, health_check
from database.migrations import ensure_schema_upgrades
from models.recent_form import compute_form, form_to_elo_delta


def main() -> None:
    logger.info("═══════════════════════════════════════")
    logger.info("  WC 2026 — Recent Form Refresh (API-Football)")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)
    ensure_schema_upgrades()

    from data.ingest.apifootball_loader import ApiFootballLoader, ApiFootballConfigError
    try:
        loader = ApiFootballLoader()
    except ApiFootballConfigError as e:
        logger.error(str(e))
        logger.error("Add APIFOOTBALL_KEY to your .env, then re-run.")
        sys.exit(1)

    # Which 48 teams to refresh (the WC 2026 squads already in the DB).
    with get_session() as session:
        wc_teams = [r[0] for r in session.execute(text(
            "SELECT name FROM teams WHERE group_name IS NOT NULL ORDER BY name")).fetchall()]

    try:
        team_ids = loader.get_team_ids()
    except Exception as e:
        logger.error(f"Could not fetch team ids from API-Football: {e}")
        sys.exit(1)

    from datetime import date
    ref = date.today()
    written, skipped = 0, []

    with get_session() as session:
        for name in wc_teams:
            tid = team_ids.get(name)
            if tid is None:
                skipped.append(name)
                continue
            try:
                matches = loader.get_recent_matches(tid, last=20)
            except Exception as e:
                logger.warning(f"  {name}: fetch failed ({e})")
                skipped.append(name)
                continue
            form = compute_form(matches, ref)
            delta = form_to_elo_delta(form)
            session.execute(text("""
                INSERT INTO team_recent_form
                    (team_name, win_rate, gf_pg, ga_pg, gd_pg, pts_pg, matches, elo_delta)
                VALUES (:n, :wr, :gf, :ga, :gd, :pts, :m, :d)
                ON CONFLICT (team_name) DO UPDATE SET
                    win_rate=EXCLUDED.win_rate, gf_pg=EXCLUDED.gf_pg,
                    ga_pg=EXCLUDED.ga_pg, gd_pg=EXCLUDED.gd_pg,
                    pts_pg=EXCLUDED.pts_pg, matches=EXCLUDED.matches,
                    elo_delta=EXCLUDED.elo_delta, updated_at=NOW()
            """), {"n": name, "wr": form["win_rate"], "gf": form["gf_pg"],
                   "ga": form["ga_pg"], "gd": form["gd_pg"], "pts": form["pts_pg"],
                   "m": form["n"], "d": round(delta, 2)})
            written += 1
            time.sleep(0.3)  # be gentle on the rate limit

    logger.info(f"✅ Refreshed form for {written}/{len(wc_teams)} teams.")
    if skipped:
        logger.info(f"   No API-Football match for: {', '.join(skipped[:10])}"
                    + (" …" if len(skipped) > 10 else ""))


if __name__ == "__main__":
    main()
