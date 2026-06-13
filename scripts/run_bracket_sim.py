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
import re
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


def _recent_form_bonus() -> dict[str, float]:
    """
    Elo-point bonus from a team's most recent major tournament (Euro 2024,
    Copa 2024, WC 2022 …). Reigning champions and strong recent campaigns get
    a lift; this is why Spain (Euro 2024 winners) and Argentina (Copa 2024 /
    WC 2022 winners) rate as genuine 2026 contenders despite middling
    World-Cup-only Elo. Avg goal difference per match → ±~45 Elo, so it nudges
    the order without overriding it.
    """
    df = pd.read_sql("""
        SELECT DISTINCT ON (team) team,
               AVG(goals_scored - goals_conceded)
                   OVER (PARTITION BY team, tournament_label) AS form,
               kickoff_utc
        FROM v_team_match_stats
        ORDER BY team, kickoff_utc DESC
    """, engine)
    return {r["team"]: max(-45.0, min(45.0, float(r["form"]) * 25.0))
            for _, r in df.iterrows() if pd.notna(r["form"])}


def load_strengths() -> tuple[dict[str, list[GroupTeam]], dict[str, float]]:
    """Build group→teams with blended strengths from Elo + FIFA rank + form."""
    if not FJELSTUL_MATCHES.exists():
        logger.error("Fjelstul matches.csv missing. Run scripts/fetch_external_data.py")
        sys.exit(1)

    history = pd.read_csv(FJELSTUL_MATCHES)
    history["home_team_name"] = history["home_team_name"].map(canonicalize)
    history["away_team_name"] = history["away_team_name"].map(canonicalize)
    elo = build_from_history(history)
    form = _recent_form_bonus()

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
        s = blended_strength(name, elo, fifa_rank) + form.get(name, 0.0)
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


def build_chalk_bracket(strengths: dict[str, float],
                        groups: dict[str, list[GroupTeam]],
                        structure: BracketStructure) -> dict[int, dict]:
    """
    A COHERENT "chalk" expected bracket: the stronger team advances at every
    step, so the tree feeds through consistently and the strongest side lifts
    the trophy (unlike the Monte Carlo modal bracket, where the single most
    likely finalist pairing and the most likely champion can disagree, showing
    a winner who isn't even in the displayed final).

    Group slots resolve by strength: '1X'/'2X' = the top two of group X, the
    eight best third-placed teams fill the '3…' slots. This is the favourites'
    path — the honest *distribution* still lives in the advancement table.
    """
    # Rank each group; collect third-placed teams for the best-thirds pool.
    ranked = {g: sorted(ts, key=lambda t: -strengths[t.name]) for g, ts in groups.items()}
    thirds = sorted((ranked[g][2] for g in ranked if len(ranked[g]) >= 3),
                    key=lambda t: -strengths[t.name])
    third_pool = iter([t.name for t in thirds[:8]])

    def resolve(ph: str, winners: dict[int, str]) -> str | None:
        s = str(ph or "")
        m = re.match(r"^([12])([A-L])$", s)
        if m:
            idx = int(m.group(1)) - 1
            grp = ranked.get(m.group(2), [])
            return grp[idx].name if len(grp) > idx else None
        if s.startswith("3"):
            return next(third_pool, None)
        w = re.match(r"^W(\d+)$", s)
        if w:
            return winners.get(int(w.group(1)))
        return None

    winners: dict[int, str] = {}
    bracket: dict[int, dict] = {}
    for num in sorted(structure.matches):
        stage, hp, ap = structure.matches[num]
        home = resolve(hp, winners)
        away = resolve(ap, winners)
        if not home or not away:
            continue
        sh, sa = strengths.get(home, 1500), strengths.get(away, 1500)
        winner = home if sh >= sa else away
        winners[num] = winner
        from models.elo import EloModel
        p_home = EloModel.expected_score(sh, sa)
        bracket[num] = {"stage": stage, "home": home, "away": away,
                        "winner": winner, "home_prob": p_home, "away_prob": 1 - p_home}
    return bracket


def persist_predictions(strengths, groups, structure) -> None:
    """Persist the coherent chalk bracket to predicted_bracket (display feed)."""
    import re as _re  # noqa: F401  (re already imported at module top)
    ensure_predicted_bracket_table()
    bracket = build_chalk_bracket(strengths, groups, structure)
    with get_session() as session:
        session.execute(text("TRUNCATE predicted_bracket"))
        for num, slot in bracket.items():
            session.execute(text("""
                INSERT INTO predicted_bracket
                    (fifa_match_num, stage, home_team, away_team, winner,
                     home_prob, away_prob, pairing_prob, model_version)
                VALUES (:num, :stage, :home, :away, :winner, :hp, :ap, NULL, :mv)
            """), {"num": num, "stage": slot["stage"], "home": slot["home"],
                   "away": slot["away"], "winner": slot["winner"],
                   "hp": round(slot["home_prob"], 4), "ap": round(slot["away_prob"], 4),
                   "mv": MODEL_VERSION})
    champ = bracket.get(104, {}).get("winner", "—")
    logger.info(f"Wrote chalk bracket for {len(bracket)} matches. Predicted champion: {champ}")


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
    persist_predictions(strengths, groups, structure)

    # Console summary: title favourites
    logger.info("── Title odds (top 10) ──")
    for row in result.advancement_table()[:10]:
        logger.info(f"  {row['team']:<22} champion={row['won_cup']*100:5.1f}%  "
                    f"final={row['reached_final']*100:5.1f}%  SF={row['reached_sf']*100:5.1f}%")
    logger.info("✅ Simulation complete. View on the Bracket dashboard page.")


if __name__ == "__main__":
    main()
