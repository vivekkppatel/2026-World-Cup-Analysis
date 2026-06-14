"""
data/ingest/apifootball_loader.py
──────────────────────────────────
Live WC 2026 fixtures/results/standings from API-Football
(https://www.api-football.com). Unlike the free openfootball feed, this is a
real-time provider — once matches kick off it has live scores within seconds.

Auth: set APIFOOTBALL_KEY in .env. Works with both access modes:
  • Direct (api-sports.io):  header  x-apisports-key
  • RapidAPI:                set APIFOOTBALL_HOST=api-football-v1.p.rapidapi.com
                             (then x-rapidapi-key / x-rapidapi-host are used)

The FIFA World Cup is league id 1; the 2026 edition is season 2026.

Usage:
    loader = ApiFootballLoader()           # reads APIFOOTBALL_KEY from env
    fixtures = loader.get_fixtures()        # normalized DataFrame
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pandas as pd
import requests

from data.transform.team_aliases import canonicalize

logger = logging.getLogger(__name__)

WORLD_CUP_LEAGUE_ID = 1
SEASON = 2026

# API-Football status code → our vocabulary
_FINISHED = {"FT", "AET", "PEN"}
_IN_PLAY = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}

# Round label → our stage vocabulary
_STAGE_MAP = {
    "group": "GROUP_STAGE", "round of 32": "LAST_32", "round of 16": "LAST_16",
    "quarter": "QUARTER_FINALS", "semi": "SEMI_FINALS",
    "3rd place": "THIRD_PLACE", "final": "FINAL",
}


class ApiFootballConfigError(RuntimeError):
    """Raised when no API key is configured."""


class ApiFootballLoader:
    def __init__(self, api_key: str | None = None, timeout: int = 20):
        self.api_key = api_key or os.getenv("APIFOOTBALL_KEY", "")
        self.host = os.getenv("APIFOOTBALL_HOST", "v3.football.api-sports.io")
        self.timeout = timeout
        if not self.api_key or self.api_key == "your_apifootball_key_here":
            raise ApiFootballConfigError(
                "APIFOOTBALL_KEY not set in .env — get a free key at "
                "https://www.api-football.com/")

    # ── HTTP ──────────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        if "rapidapi" in self.host:
            return {"x-rapidapi-key": self.api_key, "x-rapidapi-host": self.host}
        return {"x-apisports-key": self.api_key}

    def _get(self, path: str, params: dict) -> list[dict]:
        url = f"https://{self.host}/{path}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            logger.warning("API-Football errors: %s", body["errors"])
        return body.get("response", [])

    # ── Normalizers ───────────────────────────────────────────────────────────
    @staticmethod
    def _status(short: str) -> str:
        if short in _FINISHED:
            return "FINISHED"
        if short in _IN_PLAY:
            return "IN_PLAY"
        return "SCHEDULED"

    @classmethod
    def _stage(cls, round_label: str) -> str:
        label = (round_label or "").lower()
        for needle, stage in _STAGE_MAP.items():
            if needle in label:
                return stage
        return "GROUP_STAGE" if "group" in label else "UNKNOWN"

    @staticmethod
    def _winner(hs, as_) -> str | None:
        if hs is None or as_ is None:
            return None
        return "HOME" if hs > as_ else "AWAY" if as_ > hs else "DRAW"

    def _normalize(self, fx: dict) -> dict:
        f, teams, goals = fx["fixture"], fx["teams"], fx["goals"]
        hs, as_ = goals.get("home"), goals.get("away")
        kickoff = None
        try:
            kickoff = datetime.fromisoformat(f["date"]).astimezone(timezone.utc)
        except (ValueError, KeyError, TypeError):
            pass
        return {
            "apifootball_id": f.get("id"),
            "home_team_name": canonicalize(teams["home"]["name"]),
            "away_team_name": canonicalize(teams["away"]["name"]),
            "home_score": hs,
            "away_score": as_,
            "status": self._status(f.get("status", {}).get("short", "NS")),
            "stage": self._stage(fx.get("league", {}).get("round", "")),
            "kickoff_utc": kickoff,
            "venue": (f.get("venue") or {}).get("name") or "",
            "winner": self._winner(hs, as_),
        }

    # ── Public API ────────────────────────────────────────────────────────────
    def get_fixtures(self) -> pd.DataFrame:
        """All WC 2026 fixtures with live scores/status, normalized."""
        raw = self._get("fixtures", {"league": WORLD_CUP_LEAGUE_ID, "season": SEASON})
        rows = [self._normalize(fx) for fx in raw]
        df = pd.DataFrame(rows)
        finished = int((df["status"] == "FINISHED").sum()) if not df.empty else 0
        logger.info("API-Football: %d fixtures (%d finished).", len(df), finished)
        return df

    def get_top_scorers(self, limit: int = 20) -> pd.DataFrame:
        raw = self._get("players/topscorers",
                        {"league": WORLD_CUP_LEAGUE_ID, "season": SEASON})
        rows = []
        for r in raw[:limit]:
            p, stats = r["player"], r["statistics"][0]
            rows.append({
                "player": p["name"],
                "team": canonicalize(stats["team"]["name"]),
                "goals": (stats.get("goals") or {}).get("total") or 0,
            })
        return pd.DataFrame(rows)
