"""
scripts/run_bracket_sim.py
───────────────────────────
Run the WC 2026 Monte Carlo bracket simulation and persist the results.

Steps:
  1. Build Elo from Fjelstul WC history (1930–2022).
  2. Blend each 2026 qualifier's Elo with its FIFA rank → team strength.
  3. Read the bracket structure (groups + KO placeholders) from the matches table.
  4. Simulate the tournament N times.
  5. Write advancement probabilities to team_advancement and the modal
     knockout bracket to predictions (so v_predictions_vs_results compares
     it against reality as matches finish).

Run:
    python scripts/run_bracket_sim.py --sims 10000
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import pandas as pd
from sqlalchemy import text

from database.db import get_session, health_check, engine
from database.migrations import ensure_schema_upgrades
from data.transform.team_aliases import canonicalize
from models.elo import build_from_history, blended_strength
from models.tournament_sim import (
    BracketStructure, GroupTeam, TournamentSimulator, ROUND_ORDER,
)

FJELSTUL_MATCHES = Path(__file__).parent.parent / "data" / "external" / "fjelstul" / "matches.csv"
MODEL_VERSION = "elo-mc-v1"
KO_STAGES = ("LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS",
             "THIRD_PLACE", "FINAL")


def load_strengths() -> tuple[dict[str, list[GroupTeam]], dict[str, float]]:
    """Build group→teams with blended strengths from Elo + FIFA rank."""
    if not FJELSTUL_MATCHES.exists():
        logger.error("Fjelstul matches.csv missing. Run scripts/fetch_external_data.py")
        sys.exit(1)

    history = pd.read_csv(FJELSTUL_MATCHES)
    history["home_team_name"] = history["home_team_name"].map(canonicalize)
    history["away_team_name"] = history["away_team_name"].map(canonicalize)
    elo = build_from_history(history)

    with get_session() as session:
        rows = session.execute(text("""
            SELECT name, group_name, fifa_ranking
            FROM teams
            WHERE group_name IS NOT NULL
            ORDER BY group_name, name
        """)).fetchall()

    groups: dict[str, list[GroupTeam]] = {}
    strengths: dict[str, float] = {}
    for name, group, fifa_rank in rows:
        s = blended_strength(name, elo, fifa_rank)
        strengths[name] = s
        groups.setdefault(group, []).append(GroupTeam(name=name, strength=s))

    logger.info(f"Loaded {len(strengths)} teams across {len(groups)} groups.")
    return groups, strengths


def load_bracket_structure() -> BracketStructure:
    """Read KO placeholders straight from the matches table."""
    with get_session() as session:
        rows = session.execute(text("""
            SELECT fifa_match_num, stage, home_placeholder, away_placeholder
            FROM matches
            WHERE stage = ANY(:stages) AND fifa_match_num IS NOT NULL
            ORDER BY fifa_match_num
        """), {"stages": list(KO_STAGES)}).fetchall()

    matches = {int(num): (stage, home, away) for num, stage, home, away in rows}
    return BracketStructure(matches=matches, group_letters=[])


def ensure_advancement_table() -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS team_advancement (
                id            SERIAL PRIMARY KEY,
                team_id       INTEGER REFERENCES teams(id),
                team_name     VARCHAR(100) NOT NULL UNIQUE,
                strength      NUMERIC(7,2),
                reached_r32   NUMERIC(5,4),
                reached_r16   NUMERIC(5,4),
                reached_qf    NUMERIC(5,4),
                reached_sf    NUMERIC(5,4),
                reached_final NUMERIC(5,4),
                won_cup       NUMERIC(5,4),
                model_version VARCHAR(20),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


def persist_advancement(result, strengths: dict[str, float]) -> None:
    ensure_advancement_table()
    table = result.advancement_table()
    with get_session() as session:
        team_ids = {n: i for n, i in
                    session.execute(text("SELECT name, id FROM teams")).fetchall()}
        session.execute(text("TRUNCATE team_advancement RESTART IDENTITY"))
        for row in table:
            session.execute(text("""
                INSERT INTO team_advancement
                    (team_id, team_name, strength, reached_r32, reached_r16,
                     reached_qf, reached_sf, reached_final, won_cup, model_version)
                VALUES (:tid, :name, :str, :r32, :r16, :qf, :sf, :final, :win, :mv)
            """), {
                "tid": team_ids.get(row["team"]), "name": row["team"],
                "str": round(strengths.get(row["team"], 1500), 2),
                "r32": row["reached_r32"], "r16": row["reached_r16"],
                "qf": row["reached_qf"], "sf": row["reached_sf"],
                "final": row["reached_final"], "win": row["won_cup"],
                "mv": MODEL_VERSION,
            })
    logger.info(f"Wrote advancement probabilities for {len(table)} teams.")


def ensure_predicted_bracket_table() -> None:
    """
    Modal knockout bracket — the single most likely team in each KO slot.
    Separate from `predictions` because the `matches` table's team slots stay
    NULL until reality resolves them, so the bracket page needs somewhere to
    read the *predicted* teams for each match.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS predicted_bracket (
                fifa_match_num SMALLINT PRIMARY KEY,
                stage          VARCHAR(20),
                home_team      VARCHAR(100),
                away_team      VARCHAR(100),
                winner         VARCHAR(100),
                home_prob      NUMERIC(5,4),
                away_prob      NUMERIC(5,4),
                pairing_prob   NUMERIC(5,4),
                model_version  VARCHAR(20),
                updated_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


def persist_predictions(result) -> None:
    """
    Persist the modal knockout bracket to predicted_bracket (the bracket-page
    display). The per-match win/draw/loss predictions that v_model_scorecard
    grades are owned by the trained model (scripts/predict_wc2026.py), so this
    simulator stays out of the predictions table — one model, one scorecard.
    """
    ensure_predicted_bracket_table()
    bracket = result.modal_bracket()

    with get_session() as session:
        num_to_stage = {int(n): s for n, s in session.execute(text(
            "SELECT fifa_match_num, stage FROM matches WHERE fifa_match_num IS NOT NULL"
        )).fetchall()}

        session.execute(text("TRUNCATE predicted_bracket"))
        written = 0
        for mnum, slot in bracket.items():
            if slot["winner"] is None:
                continue
            win_tally = result.slot_winner_tally.get(mnum, {})
            total = sum(win_tally.values()) or 1
            home_share = win_tally.get(slot["home"], 0) / total
            away_share = win_tally.get(slot["away"], 0) / total
            pair_tally = result.slot_pair_tally.get(mnum, {})
            pairing_prob = (max(pair_tally.values()) / sum(pair_tally.values())
                            if pair_tally else 0.0)

            session.execute(text("""
                INSERT INTO predicted_bracket
                    (fifa_match_num, stage, home_team, away_team, winner,
                     home_prob, away_prob, pairing_prob, model_version)
                VALUES (:num, :stage, :home, :away, :winner,
                        :hp, :ap, :pp, :mv)
            """), {"num": mnum, "stage": num_to_stage.get(mnum),
                   "home": slot["home"], "away": slot["away"],
                   "winner": slot["winner"], "hp": round(home_share, 4),
                   "ap": round(away_share, 4), "pp": round(pairing_prob, 4),
                   "mv": MODEL_VERSION})
            written += 1
    logger.info(f"Wrote modal bracket for {written} knockout matches.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims", type=int, default=10000,
                        help="number of Monte Carlo tournaments")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    logger.info("═══════════════════════════════════════")
    logger.info(f"  WC 2026 Bracket Simulation ({args.sims:,} runs)")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)
    ensure_schema_upgrades()

    groups, strengths = load_strengths()
    structure = load_bracket_structure()
    if not structure.matches:
        logger.error("No knockout structure found. Run scripts/refresh_live.py first.")
        sys.exit(1)

    sim = TournamentSimulator(groups, structure)
    logger.info(f"Simulating {args.sims:,} tournaments …")
    result = sim.run(args.sims, seed=args.seed)

    persist_advancement(result, strengths)
    persist_predictions(result)

    # Console summary: title favourites
    logger.info("── Title odds (top 10) ──")
    for row in result.advancement_table()[:10]:
        logger.info(f"  {row['team']:<22} champion={row['won_cup']*100:5.1f}%  "
                    f"final={row['reached_final']*100:5.1f}%  SF={row['reached_sf']*100:5.1f}%")
    logger.info("✅ Simulation complete. View on the Bracket dashboard page.")


if __name__ == "__main__":
    main()
