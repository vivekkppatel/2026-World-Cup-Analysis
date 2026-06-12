"""
data/ingest/statsbomb_loader.py
────────────────────────────────
Loads historical World Cup event data from StatsBomb Open Data.

StatsBomb provides free event-level data for WC 2018 and WC 2022.
Each event is a granular action: shots, passes, dribbles, pressures,
carries, tackles, etc. — the richest public football dataset available.

GitHub: https://github.com/statsbomb/open-data
Docs:   https://statsbomb.com/what-we-do/hub/free-data/

Usage:
    loader = StatsBombLoader()
    matches_df = loader.get_matches(competition_id=43, season_id=106)  # WC 2022
    events_df  = loader.get_events_for_match(match_id=3869685)
    summary_df = loader.get_player_tournament_stats(competition_id=43, season_id=106)
"""
import logging
from functools import lru_cache
from typing import Optional

import pandas as pd
from statsbombpy import sb

logger = logging.getLogger(__name__)

# ── StatsBomb Competition / Season IDs ────────────────────────────────────────
# "competition" groups tournaments for filtering (e.g. the match predictor
# trains on WORLD_CUP only); "label" is the human-readable BI dimension.
COMPETITIONS = {
    "wc_2018":    {"competition_id": 43,   "season_id": 3,
                   "competition": "WORLD_CUP", "label": "WC 2018"},
    "wc_2022":    {"competition_id": 43,   "season_id": 106,
                   "competition": "WORLD_CUP", "label": "WC 2022"},
    # Non-WC tournaments: player-valuation context only — NOT used to
    # train the WC match predictor.
    "euro_2020":  {"competition_id": 55,   "season_id": 43,
                   "competition": "EURO", "label": "EURO 2020"},
    "euro_2024":  {"competition_id": 55,   "season_id": 282,
                   "competition": "EURO", "label": "EURO 2024"},
    "copa_2024":  {"competition_id": 223,  "season_id": 282,
                   "competition": "COPA_AMERICA", "label": "COPA 2024"},
    "afcon_2023": {"competition_id": 1267, "season_id": 107,
                   "competition": "AFCON", "label": "AFCON 2023"},
}


class StatsBombLoader:
    """
    Wrapper around statsbombpy for clean, typed access to
    World Cup historical event data.
    """

    # ── Competition / Match data ──────────────────────────────────────────────

    @staticmethod
    def list_open_competitions() -> pd.DataFrame:
        """Return all competitions available in StatsBomb Open Data."""
        return sb.competitions()

    @staticmethod
    def get_matches(competition_id: int, season_id: int) -> pd.DataFrame:
        """
        Return all matches for a given competition + season.
        WC 2022: competition_id=43, season_id=106
        WC 2018: competition_id=43, season_id=3
        """
        matches = sb.matches(competition_id=competition_id, season_id=season_id)
        logger.info(f"Loaded {len(matches)} matches (competition={competition_id}, season={season_id})")
        return matches

    # ── Event data ────────────────────────────────────────────────────────────

    @staticmethod
    @lru_cache(maxsize=256)
    def get_events_for_match(match_id: int) -> pd.DataFrame:
        """
        Return all events for a single match.
        Each row is one discrete action on the pitch.
        Cached in memory to avoid redundant API calls.
        """
        events = sb.events(match_id=match_id)
        logger.debug(f"Loaded {len(events)} events for match {match_id}")
        return events

    @staticmethod
    def get_lineups(match_id: int) -> dict[str, pd.DataFrame]:
        """
        Return lineups for a match.
        Returns dict keyed by team name, each value is a player DataFrame.
        """
        return sb.lineups(match_id=match_id)

    # ── Aggregated stats ──────────────────────────────────────────────────────

    @classmethod
    def get_player_tournament_stats(
        cls,
        competition_id: int,
        season_id: int,
        min_minutes: int = 45,
    ) -> pd.DataFrame:
        """
        Build a per-player tournament summary from event data.
        Aggregates across all matches: goals, assists, xG, xA,
        shots, pressures, passes, progressive carries/passes.

        Returns one row per player with per-90-minute rates.
        This is the primary input for the player rating model.
        """
        matches = cls.get_matches(competition_id, season_id)
        all_stats: list[pd.DataFrame] = []

        logger.info(f"Building player stats from {len(matches)} matches …")
        for _, match in matches.iterrows():
            try:
                events = cls.get_events_for_match(match["match_id"])
                stats = cls._aggregate_player_match(events, match)
                if stats is not None:
                    all_stats.append(stats)
            except Exception as e:
                logger.warning(f"Failed to process match {match['match_id']}: {e}")
                continue

        if not all_stats:
            return pd.DataFrame()

        combined = pd.concat(all_stats, ignore_index=True)

        # Aggregate across all matches per player
        numeric_cols = [
            "minutes_played", "goals", "assists", "shots",
            "shots_on_target", "xg", "xa", "passes", "key_passes",
            "pressures", "tackles", "progressive_carries", "progressive_passes",
        ]

        grouped = (
            combined
            .groupby(["player_id", "player_name", "team_name", "position"])[numeric_cols]
            .sum()
            .reset_index()
        )

        # Filter low-minute players
        grouped = grouped[grouped["minutes_played"] >= min_minutes].copy()

        # Add per-90 rates
        p90 = grouped["minutes_played"] / 90
        for col in ["goals", "assists", "xg", "xa", "shots", "pressures",
                    "key_passes", "progressive_carries", "progressive_passes"]:
            grouped[f"{col}_p90"] = (grouped[col] / p90).round(3)

        grouped["pass_accuracy"] = (grouped["key_passes"] / grouped["passes"].replace(0, 1) * 100).round(1)
        grouped["shot_conversion"] = (grouped["goals"] / grouped["shots"].replace(0, 1) * 100).round(1)

        logger.info(f"Built stats for {len(grouped)} players.")
        return grouped.sort_values("xg", ascending=False)

    @staticmethod
    def _aggregate_player_match(
        events: pd.DataFrame,
        match: pd.Series,
    ) -> Optional[pd.DataFrame]:
        """
        Extract per-player stats from a single match's events DataFrame.
        Returns a DataFrame with one row per player.
        """
        if events.empty:
            return None

        # Exclude penalty shootouts (period 5): those Shot events inflate
        # goals/xG/shots and don't count in official match stats.
        if "period" in events.columns:
            events = events[events["period"] <= 4]

        stats_rows = []

        # Get unique players in this match
        players = events[["player_id", "player", "team", "position"]].dropna(subset=["player_id"])
        unique_players = players.drop_duplicates("player_id")

        for _, player_row in unique_players.iterrows():
            pid = player_row["player_id"]
            pe = events[events["player_id"] == pid]

            # Minutes played: use max timestamp as proxy
            minutes = int(pe["minute"].max()) if not pe.empty else 0

            row = {
                "player_id":    pid,
                "player_name":  player_row["player"],
                "team_name":    player_row["team"],
                "position":     player_row.get("position", "Unknown"),
                "match_id":     match["match_id"],
                "minutes_played": minutes,

                # Attacking
                "goals":        int(pe[pe["type"] == "Shot"]["shot_outcome"].eq("Goal").sum()),
                "assists":      int(pe["pass_goal_assist"].sum() if "pass_goal_assist" in pe.columns else 0),
                "shots":        int((pe["type"] == "Shot").sum()),
                "shots_on_target": int(pe[pe["type"] == "Shot"]["shot_outcome"].isin(["Goal", "Saved"]).sum()),
                "xg":           float(pe[pe["type"] == "Shot"]["shot_statsbomb_xg"].sum() if "shot_statsbomb_xg" in pe.columns else 0),
                "xa":           float(pe["pass_xa"].sum() if "pass_xa" in pe.columns else 0),

                # Passing
                "passes":       int((pe["type"] == "Pass").sum()),
                "key_passes":   int(pe["pass_shot_assist"].sum() if "pass_shot_assist" in pe.columns else 0),

                # Defensive
                "pressures":    int((pe["type"] == "Pressure").sum()),
                "tackles":      int((pe["type"] == "Tackle").sum()),

                # Progression
                "progressive_carries": int(pe["carry_progressive"].sum() if "carry_progressive" in pe.columns else 0),
                "progressive_passes":  int(pe["pass_progressive"].sum() if "pass_progressive" in pe.columns else 0),
            }
            stats_rows.append(row)

        return pd.DataFrame(stats_rows) if stats_rows else None

    # ── Team-level data ───────────────────────────────────────────────────────

    @classmethod
    def get_team_match_stats(
        cls,
        competition_id: int,
        season_id: int,
    ) -> pd.DataFrame:
        """
        Build per-team, per-match summary stats for ML model training.
        Returns one row per team per match with xG, shots, passes, etc.
        """
        matches = cls.get_matches(competition_id, season_id)
        rows = []

        for _, match in matches.iterrows():
            try:
                events = cls.get_events_for_match(match["match_id"])
                # Exclude penalty shootouts (period 5) — see _aggregate_player_match
                if "period" in events.columns:
                    events = events[events["period"] <= 4]
                for team in [match["home_team"], match["away_team"]]:
                    te = events[events["team"] == team]
                    is_home = (team == match["home_team"])
                    rows.append({
                        "match_id":        match["match_id"],
                        "team":            team,
                        "opponent":        match["away_team"] if is_home else match["home_team"],
                        "is_home":         is_home,
                        "home_score":      match["home_score"],
                        "away_score":      match["away_score"],
                        "goals_for":       match["home_score"] if is_home else match["away_score"],
                        "goals_against":   match["away_score"] if is_home else match["home_score"],
                        "xg":              float(te[te["type"] == "Shot"]["shot_statsbomb_xg"].sum() if "shot_statsbomb_xg" in te.columns else 0),
                        "shots":           int((te["type"] == "Shot").sum()),
                        "passes":          int((te["type"] == "Pass").sum()),
                        "pressures":       int((te["type"] == "Pressure").sum()),
                        "stage":           match.get("competition_stage", "") or "",
                    })
            except Exception as e:
                logger.warning(f"Skipping match {match['match_id']}: {e}")

        df = pd.DataFrame(rows)
        if not df.empty:
            df["result"] = df.apply(
                lambda r: "W" if r["goals_for"] > r["goals_against"]
                else ("D" if r["goals_for"] == r["goals_against"] else "L"),
                axis=1
            )
        return df
