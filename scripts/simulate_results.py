"""
scripts/simulate_results.py
────────────────────────────
DEMO MODE — play out WC 2026 results with the model so the dashboard comes
alive (standings, scorers, brackets all populate and update) when no real
live feed is available.

These are SIMULATED scores, not real ones. The script sets app_meta
results_mode='simulated' so the UI labels them clearly. To wipe them and
return to the (empty) real feed, run:  python scripts/simulate_results.py --clear

Usage:
    python scripts/simulate_results.py            # simulate the group stage
    python scripts/simulate_results.py --all      # also simulate knockouts
    python scripts/simulate_results.py --clear     # remove simulated results
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import numpy as np
from sqlalchemy import text

from database.db import engine, get_session, health_check
from database.migrations import ensure_schema_upgrades
from models.match_poisson import expected_goals

SEED = 2026


def _set_mode(value: str) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO app_meta (key, value, updated_at)
            VALUES ('results_mode', :v, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """), {"v": value})
        conn.commit()


def clear_results() -> None:
    with get_session() as s:
        n = s.execute(text("""
            UPDATE matches SET home_score=NULL, away_score=NULL,
                   status='SCHEDULED', winner=NULL
            WHERE tournament_label='WC 2026'
        """)).rowcount
    _set_mode("live")
    logger.info(f"Cleared {n} WC 2026 results. Back to the real (live) feed.")


def simulate(do_all: bool) -> None:
    rng = np.random.default_rng(SEED)
    strengths = {n: float(s) for n, s in
                 _q("SELECT team_name, strength FROM team_advancement")}

    stages = ["GROUP_STAGE"] + (
        ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "THIRD_PLACE", "FINAL"]
        if do_all else [])

    with get_session() as s:
        rows = s.execute(text("""
            SELECT m.id, th.name AS home, ta.name AS away
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.tournament_label='WC 2026' AND m.stage = ANY(:stages)
        """), {"stages": stages}).fetchall()

        played = 0
        for mid, home, away in rows:
            lam_h, lam_a = expected_goals(strengths.get(home, 1700),
                                          strengths.get(away, 1700))
            hs, as_ = int(rng.poisson(lam_h)), int(rng.poisson(lam_a))
            winner = "HOME" if hs > as_ else "AWAY" if as_ > hs else "DRAW"
            s.execute(text("""
                UPDATE matches SET home_score=:hs, away_score=:as, status='FINISHED',
                       winner=:w, updated_at=NOW() WHERE id=:id
            """), {"hs": hs, "as": as_, "w": winner, "id": mid})
            played += 1

    _set_mode("simulated")
    logger.info(f"⚽ Simulated {played} matches ({'group + knockouts' if do_all else 'group stage'}).")
    logger.info("These are DEMO results — the UI shows a 'simulated' badge. "
                "Run with --clear to remove them.")


def _q(sql: str):
    with engine.connect() as conn:
        return conn.execute(text(sql)).fetchall()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also simulate knockouts")
    ap.add_argument("--clear", action="store_true", help="remove simulated results")
    args = ap.parse_args()

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)
    ensure_schema_upgrades()

    if args.clear:
        clear_results()
    else:
        simulate(args.all)


if __name__ == "__main__":
    main()
