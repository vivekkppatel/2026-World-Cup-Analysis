"""
data/transform/processors.py
──────────────────────────────
Normalizes raw API/StatsBomb data into clean DataFrames
ready for database insertion or direct use in the dashboard.
"""
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Team processor
# ═══════════════════════════════════════════════════════════════════════════════

def process_teams(raw_teams: list[dict]) -> pd.DataFrame:
    """
    Normalize raw team objects from football-data.org into a flat DataFrame.

    Returns columns: api_id, name, short_name, tla, crest_url
    """
    rows = []
    for t in raw_teams:
        rows.append({
            "api_id":     t.get("id"),
            "name":       t.get("name", "Unknown"),
            "short_name": t.get("shortName", t.get("name", "Unknown")),
            "tla":        t.get("tla", ""),
            "crest_url":  t.get("crest", ""),
        })
    df = pd.DataFrame(rows).drop_duplicates("api_id")
    logger.info(f"Processed {len(df)} teams.")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# Match processor
# ═══════════════════════════════════════════════════════════════════════════════

def process_matches(raw_matches: list[dict]) -> pd.DataFrame:
    """
    Normalize raw match objects from football-data.org.

    Returns columns: api_id, home_team_api_id, away_team_api_id,
                     home_score, away_score, stage, group_name,
                     match_day, kickoff_utc, venue, status, winner
    """
    rows = []
    for m in raw_matches:
        score = m.get("score", {})
        ft    = score.get("fullTime", {})
        home_score = ft.get("home")
        away_score = ft.get("away")

        # Determine winner
        winner = None
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = "HOME"
            elif away_score > home_score:
                winner = "AWAY"
            else:
                winner = "DRAW"

        rows.append({
            "api_id":           m.get("id"),
            "home_team_api_id": m["homeTeam"]["id"],
            "away_team_api_id": m["awayTeam"]["id"],
            "home_score":       home_score,
            "away_score":       away_score,
            "stage":            m.get("stage", ""),
            "group_name":       _extract_group(m.get("group", "")),
            "match_day":        m.get("matchday"),
            "kickoff_utc":      _parse_utc(m.get("utcDate")),
            "venue":            m.get("venue", ""),
            "status":           m.get("status", "SCHEDULED"),
            "winner":           winner,
        })

    df = pd.DataFrame(rows).drop_duplicates("api_id")
    logger.info(f"Processed {len(df)} matches.")
    return df


def _extract_group(group_str: str) -> str:
    """
    Extract single letter from e.g. 'GROUP_A' → 'A'.
    Returns empty string for knockout matches.
    """
    if group_str and "_" in group_str:
        return group_str.split("_")[-1]
    return ""


def _parse_utc(date_str: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string to UTC-aware datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Standings processor
# ═══════════════════════════════════════════════════════════════════════════════

def process_standings(raw_standings: list[dict]) -> pd.DataFrame:
    """
    Normalize group standings from football-data.org.

    Returns columns: team_api_id, group_name, position, played,
                     won, drawn, lost, goals_for, goals_against, points
    """
    rows = []
    for group in raw_standings:
        group_letter = _extract_group(group.get("group", ""))
        for entry in group.get("table", []):
            rows.append({
                "team_api_id":    entry["team"]["id"],
                "team_name":      entry["team"]["name"],
                "group_name":     group_letter,
                "position":       entry.get("position"),
                "played":         entry.get("playedGames", 0),
                "won":            entry.get("won", 0),
                "drawn":          entry.get("draw", 0),
                "lost":           entry.get("lost", 0),
                "goals_for":      entry.get("goalsFor", 0),
                "goals_against":  entry.get("goalsAgainst", 0),
                "points":         entry.get("points", 0),
            })

    df = pd.DataFrame(rows)
    logger.info(f"Processed standings for {len(df)} team-group entries.")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# Scorer processor
# ═══════════════════════════════════════════════════════════════════════════════

def process_scorers(raw_scorers: list[dict]) -> pd.DataFrame:
    """
    Normalize top scorers response into a flat DataFrame.

    Returns columns: player_api_id, player_name, team_name,
                     goals, assists, penalties, matches_played
    """
    rows = []
    for s in raw_scorers:
        p = s.get("player", {})
        t = s.get("team", {})
        rows.append({
            "player_api_id":  p.get("id"),
            "player_name":    p.get("name", "Unknown"),
            "nationality":    p.get("nationality", ""),
            "position":       p.get("section", ""),
            "team_api_id":    t.get("id"),
            "team_name":      t.get("name", "Unknown"),
            "goals":          s.get("goals", 0),
            "assists":        s.get("assists", 0),
            "penalties":      s.get("penalties", 0),
            "matches_played": s.get("playedMatches", 0),
        })

    df = pd.DataFrame(rows)
    logger.info(f"Processed {len(df)} top scorers.")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# Utility: build a match display label
# ═══════════════════════════════════════════════════════════════════════════════

def build_match_label(home_team: str, away_team: str, home_score: Any, away_score: Any) -> str:
    """Return a clean display string for a match result."""
    if home_score is not None and away_score is not None:
        return f"{home_team} {int(home_score)}–{int(away_score)} {away_team}"
    return f"{home_team} vs {away_team}"
