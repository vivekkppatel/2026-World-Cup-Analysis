"""
scripts/load_fjelstul_history.py
─────────────────────────────────
Load WC 2010 + 2014 into PostgreSQL from the Fjelstul World Cup Database
CSVs (StatsBomb open data only covers 2018+2022, so the two earlier
tournaments come in at match/goal level — no event data, no xG).

Writes: matches (keyed on fjelstul_id), players (keyed on fjelstul_id),
player_match_stats (goals only; event-derived metrics stay NULL so BI
shows "no data" rather than fake zeros), goals (event rows with minute,
penalty, own-goal flags).

Prerequisite:  python scripts/fetch_external_data.py
Run:           python scripts/load_fjelstul_history.py
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

DATA_DIR = Path(__file__).parent.parent / "data" / "external" / "fjelstul"
TOURNAMENTS = {"WC-2010": "WC 2010", "WC-2014": "WC 2014"}

# Fjelstul stage_name → project stage vocabulary
_STAGE_MAP = {
    "group stage":        "GROUP_STAGE",
    "round of 16":        "LAST_16",
    "quarter-finals":     "QUARTER_FINALS",
    "semi-finals":        "SEMI_FINALS",
    "third place match":  "THIRD_PLACE",
    "final":              "FINAL",
}


def _player_name(given: str, family: str) -> str:
    """Fjelstul uses the literal string 'not applicable' for missing parts."""
    parts = [p for p in (given, family) if p and p != "not applicable"]
    return " ".join(parts) or "Unknown"


def _winner(row: pd.Series) -> str:
    """Use Fjelstul's outcome flags — they already account for shootouts."""
    if row["home_team_win"] == 1:
        return "HOME"
    if row["away_team_win"] == 1:
        return "AWAY"
    return "DRAW"


def upsert_teams(matches: pd.DataFrame) -> dict[str, int]:
    names = set(matches["home_team_name"]) | set(matches["away_team_name"])
    with get_session() as session:
        for name in sorted(names):
            session.execute(text("""
                INSERT INTO teams (name, short_name)
                VALUES (:name, :short)
                ON CONFLICT (name) DO NOTHING
            """), {"name": name, "short": name[:20]})
        rows = session.execute(text("SELECT name, id FROM teams")).fetchall()
    return {name: tid for name, tid in rows}


def upsert_matches(matches: pd.DataFrame, team_ids: dict[str, int]) -> dict[str, int]:
    """Upsert matches keyed on fjelstul_id; return fjelstul_id → internal id."""
    with get_session() as session:
        for _, m in matches.iterrows():
            group = (m.get("group_name") or "").replace("Group", "").strip()[:1] or None
            session.execute(text("""
                INSERT INTO matches (fjelstul_id, home_team_id, away_team_id,
                                     home_score, away_score, stage, group_name,
                                     kickoff_utc, venue, city, status, winner,
                                     competition, tournament_label)
                VALUES (:fid, :home_id, :away_id, :hs, :aws, :stage, :grp,
                        :kickoff, :venue, :city, 'FINISHED', :winner,
                        'WORLD_CUP', :label)
                ON CONFLICT (fjelstul_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    winner     = EXCLUDED.winner,
                    updated_at = NOW()
            """), {
                "fid":     m["match_id"],
                "home_id": team_ids.get(m["home_team_name"]),
                "away_id": team_ids.get(m["away_team_name"]),
                "hs":      int(m["home_team_score"]),
                "aws":     int(m["away_team_score"]),
                "stage":   _STAGE_MAP.get(str(m["stage_name"]).strip().lower(), "UNKNOWN"),
                "grp":     group,
                "kickoff": f"{m['match_date']} {m.get('match_time') or '00:00'}",
                "venue":   str(m.get("stadium_name", "") or "")[:100],
                "city":    str(m.get("city_name", "") or "")[:100],
                "winner":  _winner(m),
                "label":   TOURNAMENTS[m["tournament_id"]],
            })
        rows = session.execute(text(
            "SELECT fjelstul_id, id FROM matches WHERE fjelstul_id IS NOT NULL"
        )).fetchall()
    return {fid: mid for fid, mid in rows}


def load_goals(goals: pd.DataFrame, team_ids: dict[str, int],
               match_ids: dict[str, int]) -> tuple[int, int]:
    """
    Upsert players (keyed fjelstul_id), rebuild goal events, and write
    per-player-per-match scorer rows. Returns (goal_rows, stat_rows).
    """
    goals = goals.copy()
    goals["player_name"] = [
        _player_name(g, f) for g, f in zip(goals["given_name"], goals["family_name"])
    ]
    goals["team_name"] = goals["team_name"].map(canonicalize)

    with get_session() as session:
        # Players
        for _, p in goals.drop_duplicates("player_id").iterrows():
            session.execute(text("""
                INSERT INTO players (fjelstul_id, name, team_id)
                VALUES (:fid, :name, :team_id)
                ON CONFLICT (fjelstul_id) DO NOTHING
            """), {"fid": p["player_id"], "name": p["player_name"],
                   "team_id": team_ids.get(p["team_name"])})
        pid_rows = session.execute(text(
            "SELECT fjelstul_id, id FROM players WHERE fjelstul_id IS NOT NULL"
        )).fetchall()
        player_ids = {fid: pid for fid, pid in pid_rows}

        # Goal events: delete-and-reinsert per loaded match (goals has no
        # natural unique key, so this keeps re-runs idempotent).
        internal_match_ids = [match_ids[m] for m in goals["match_id"].unique()
                              if m in match_ids]
        session.execute(
            text("DELETE FROM goals WHERE match_id = ANY(:ids)"),
            {"ids": internal_match_ids},
        )
        goal_rows = 0
        for _, g in goals.iterrows():
            mid = match_ids.get(g["match_id"])
            pid = player_ids.get(g["player_id"])
            if mid is None or pid is None:
                continue
            session.execute(text("""
                INSERT INTO goals (match_id, scorer_id, team_id, minute,
                                   penalty, own_goal)
                VALUES (:mid, :pid, :tid, :minute, :pen, :og)
            """), {
                "mid": mid, "pid": pid,
                "tid": team_ids.get(g["team_name"]),
                "minute": int(g["minute_regulation"]),
                "pen": bool(g["penalty"]),
                "og": bool(g["own_goal"]),
            })
            goal_rows += 1

        # Scorer rows → player_match_stats. Own goals excluded (official
        # convention). Non-goal metrics stay NULL — no event data exists.
        scorer_counts = (
            goals[goals["own_goal"] == 0]
            .groupby(["player_id", "match_id"])
            .size()
            .reset_index(name="goals")
        )
        stat_rows = 0
        for _, s in scorer_counts.iterrows():
            mid = match_ids.get(s["match_id"])
            pid = player_ids.get(s["player_id"])
            if mid is None or pid is None:
                continue
            team_fid = goals.loc[goals["player_id"] == s["player_id"], "team_name"].iloc[0]
            session.execute(text("""
                INSERT INTO player_match_stats (player_id, match_id, team_id,
                                                minutes_played, goals, xg)
                VALUES (:pid, :mid, :tid, NULL, :goals, NULL)
                ON CONFLICT (player_id, match_id) DO UPDATE SET
                    goals = EXCLUDED.goals
            """), {"pid": pid, "mid": mid,
                   "tid": team_ids.get(team_fid), "goals": int(s["goals"])})
            stat_rows += 1

    return goal_rows, stat_rows


def main() -> None:
    logger.info("═══════════════════════════════════════════════")
    logger.info("  Fjelstul History → PostgreSQL (WC 2010 + 2014)")
    logger.info("═══════════════════════════════════════════════")

    matches_csv = DATA_DIR / "matches.csv"
    goals_csv = DATA_DIR / "goals.csv"
    if not matches_csv.exists() or not goals_csv.exists():
        logger.error(f"Fjelstul CSVs not found in {DATA_DIR}. "
                     "Run: python scripts/fetch_external_data.py")
        sys.exit(1)

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    ensure_schema_upgrades()

    matches = pd.read_csv(matches_csv)
    matches = matches[matches["tournament_id"].isin(TOURNAMENTS)].copy()
    matches["home_team_name"] = matches["home_team_name"].map(canonicalize)
    matches["away_team_name"] = matches["away_team_name"].map(canonicalize)

    goals = pd.read_csv(goals_csv)
    goals = goals[goals["tournament_id"].isin(TOURNAMENTS)].copy()

    team_ids = upsert_teams(matches)
    match_ids = upsert_matches(matches, team_ids)
    logger.info(f"  {len(matches)} matches upserted across {len(TOURNAMENTS)} tournaments.")

    goal_rows, stat_rows = load_goals(goals, team_ids, match_ids)
    logger.info(f"  {goal_rows} goal events, {stat_rows} scorer stat rows written.")
    logger.info("✅ Fjelstul history load complete.")


if __name__ == "__main__":
    main()
