"""
scripts/load_statsbomb_history.py
──────────────────────────────────
Load WC 2018 + 2022 StatsBomb data into PostgreSQL so the BI views
(v_player_stats, v_top_scorers, v_team_match_stats) have real data
for Tableau / Power BI before WC 2026 produces its own.

Writes: matches (keyed on statsbomb_id), players (keyed on statsbomb_id),
player_match_stats (keyed on player_id + match_id). All upserts —
safe to re-run.

First run downloads ~128 match event files from GitHub (several minutes).
    python scripts/load_statsbomb_history.py
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
from data.ingest.statsbomb_loader import COMPETITIONS, StatsBombLoader
from data.transform.team_aliases import canonicalize

# statsbombpy stage names → project stage vocabulary
_STAGE_MAP = {
    "group stage":     "GROUP_STAGE",
    "round of 16":     "LAST_16",
    "quarter-finals":  "QUARTER_FINALS",
    "semi-finals":     "SEMI_FINALS",
    "3rd place final": "THIRD_PLACE",
    "final":           "FINAL",
}


def _normalize_stage(raw: str) -> str:
    return _STAGE_MAP.get((raw or "").strip().lower(), "UNKNOWN")


def _winner(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "HOME"
    if away_score > home_score:
        return "AWAY"
    return "DRAW"


def upsert_teams(matches: pd.DataFrame) -> dict[str, int]:
    """Ensure every team in this tournament exists; return name → id map."""
    names = set(matches["home_team"]) | set(matches["away_team"])
    with get_session() as session:
        for name in sorted(names):
            session.execute(text("""
                INSERT INTO teams (name, short_name)
                VALUES (:name, :short)
                ON CONFLICT (name) DO NOTHING
            """), {"name": name, "short": name[:20]})
        rows = session.execute(text("SELECT name, id FROM teams")).fetchall()
    return {name: tid for name, tid in rows}


def upsert_matches(matches: pd.DataFrame, team_ids: dict[str, int],
                   competition: str, label: str) -> dict[int, int]:
    """Upsert historical matches; return statsbomb match_id → internal id map."""
    with get_session() as session:
        for _, m in matches.iterrows():
            kickoff = f"{m['match_date']} {m.get('kick_off') or '00:00:00'}"
            session.execute(text("""
                INSERT INTO matches (statsbomb_id, home_team_id, away_team_id,
                                     home_score, away_score, stage, kickoff_utc,
                                     venue, status, winner, competition, tournament_label)
                VALUES (:sb_id, :home_id, :away_id, :hs, :aws, :stage,
                        :kickoff, :venue, 'FINISHED', :winner, :comp, :label)
                ON CONFLICT (statsbomb_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    stage      = EXCLUDED.stage,
                    competition = EXCLUDED.competition,
                    tournament_label = EXCLUDED.tournament_label,
                    updated_at = NOW()
            """), {
                "comp": competition, "label": label,
                "sb_id":   int(m["match_id"]),
                "home_id": team_ids.get(m["home_team"]),
                "away_id": team_ids.get(m["away_team"]),
                "hs":      int(m["home_score"]),
                "aws":     int(m["away_score"]),
                "stage":   _normalize_stage(m.get("competition_stage", "") or ""),
                "kickoff": kickoff,
                "venue":   str(m.get("stadium", "") or "")[:100],
                "winner":  _winner(int(m["home_score"]), int(m["away_score"])),
            })
        rows = session.execute(text(
            "SELECT statsbomb_id, id FROM matches WHERE statsbomb_id IS NOT NULL"
        )).fetchall()
    return {sb_id: mid for sb_id, mid in rows}


def upsert_player_stats(stats: pd.DataFrame, team_ids: dict[str, int],
                        match_ids: dict[int, int]) -> int:
    """Upsert per-player-per-match stat rows. Returns rows written."""
    written = 0
    with get_session() as session:
        # Players first (statsbomb_id is the stable key)
        players = stats.drop_duplicates("player_id")
        for _, p in players.iterrows():
            session.execute(text("""
                INSERT INTO players (statsbomb_id, name, position, team_id)
                VALUES (:sb_id, :name, :pos, :team_id)
                ON CONFLICT (statsbomb_id) DO UPDATE SET
                    position = EXCLUDED.position,
                    team_id  = EXCLUDED.team_id
            """), {
                "sb_id":   int(p["player_id"]),
                "name":    p["player_name"],
                "pos":     str(p.get("position", "") or "")[:30],
                "team_id": team_ids.get(p["team_name"]),
            })
        pid_rows = session.execute(text(
            "SELECT statsbomb_id, id FROM players WHERE statsbomb_id IS NOT NULL"
        )).fetchall()
        player_ids = {sb: pid for sb, pid in pid_rows}

        for _, s in stats.iterrows():
            internal_match = match_ids.get(int(s["match_id"]))
            internal_player = player_ids.get(int(s["player_id"]))
            if internal_match is None or internal_player is None:
                continue
            session.execute(text("""
                INSERT INTO player_match_stats
                    (player_id, match_id, team_id, minutes_played, goals, assists,
                     shots, shots_on_target, xg, xa, passes, key_passes,
                     pressures, tackles, progressive_carries, progressive_passes)
                VALUES (:pid, :mid, :tid, :mins, :goals, :assists, :shots, :sot,
                        :xg, :xa, :passes, :kp, :press, :tackles, :pc, :pp)
                ON CONFLICT (player_id, match_id) DO UPDATE SET
                    minutes_played = EXCLUDED.minutes_played,
                    goals = EXCLUDED.goals, assists = EXCLUDED.assists,
                    shots = EXCLUDED.shots, shots_on_target = EXCLUDED.shots_on_target,
                    xg = EXCLUDED.xg, xa = EXCLUDED.xa,
                    passes = EXCLUDED.passes, key_passes = EXCLUDED.key_passes,
                    pressures = EXCLUDED.pressures, tackles = EXCLUDED.tackles,
                    progressive_carries = EXCLUDED.progressive_carries,
                    progressive_passes = EXCLUDED.progressive_passes
            """), {
                "pid": internal_player, "mid": internal_match,
                "tid": team_ids.get(s["team_name"]),
                "mins": int(s["minutes_played"]), "goals": int(s["goals"]),
                "assists": int(s["assists"]), "shots": int(s["shots"]),
                "sot": int(s["shots_on_target"]), "xg": float(s["xg"]),
                "xa": float(s["xa"]), "passes": int(s["passes"]),
                "kp": int(s["key_passes"]), "press": int(s["pressures"]),
                "tackles": int(s["tackles"]),
                "pc": int(s["progressive_carries"]),
                "pp": int(s["progressive_passes"]),
            })
            written += 1
    return written


def load_tournament(key: str) -> None:
    comp = COMPETITIONS[key]
    logger.info(f"── Loading {key} (competition={comp['competition_id']}, "
                f"season={comp['season_id']}) …")

    loader = StatsBombLoader()
    matches = loader.get_matches(comp["competition_id"], comp["season_id"])
    matches["home_team"] = matches["home_team"].map(canonicalize)
    matches["away_team"] = matches["away_team"].map(canonicalize)
    team_ids = upsert_teams(matches)
    match_ids = upsert_matches(matches, team_ids,
                               competition=comp["competition"],
                               label=comp["label"])
    logger.info(f"  {len(matches)} matches upserted.")

    # Per-match player rows (downloads each match's event file on first run)
    all_stats: list[pd.DataFrame] = []
    for i, (_, match) in enumerate(matches.iterrows(), start=1):
        try:
            events = loader.get_events_for_match(match["match_id"])
            stats = loader._aggregate_player_match(events, match)
            if stats is not None:
                all_stats.append(stats)
        except Exception as e:
            logger.warning(f"  Skipping match {match['match_id']}: {e}")
        if i % 16 == 0:
            logger.info(f"  … {i}/{len(matches)} matches processed")

    if not all_stats:
        logger.error(f"  No player stats produced for {key}.")
        return

    combined = pd.concat(all_stats, ignore_index=True)
    combined["team_name"] = combined["team_name"].map(canonicalize)
    written = upsert_player_stats(combined, team_ids, match_ids)
    logger.info(f"  {written} player-match stat rows upserted for {key}.")


def main() -> None:
    """
    Load all tournaments in COMPETITIONS, or only those named on the CLI:
        python scripts/load_statsbomb_history.py euro_2020 copa_2024
    """
    requested = sys.argv[1:] or list(COMPETITIONS)
    unknown = [k for k in requested if k not in COMPETITIONS]
    if unknown:
        logger.error(f"Unknown tournament key(s): {unknown}. "
                     f"Available: {list(COMPETITIONS)}")
        sys.exit(1)

    logger.info("═══════════════════════════════════════════")
    logger.info(f"  StatsBomb History → PostgreSQL ({', '.join(requested)})")
    logger.info("═══════════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    ensure_schema_upgrades()
    for key in requested:
        load_tournament(key)

    logger.info("✅ History load complete. BI views v_player_stats / "
                "v_top_scorers / v_team_match_stats now have data.")


if __name__ == "__main__":
    main()
