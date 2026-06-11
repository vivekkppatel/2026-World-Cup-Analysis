"""
data/ingest/football_data_api.py
─────────────────────────────────
Client for the football-data.org v4 API.

Free tier: 10 requests/minute, no historical event data.
Provides: live WC 2026 matches, standings, scorers, team rosters.

Docs: https://www.football-data.org/documentation/quickstart
"""
import os
import time
import logging
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL = "https://api.football-data.org/v4"
WC_2026_CODE = "WC"          # competition code on football-data.org
RATE_LIMIT_DELAY = 6.1       # seconds between requests (free tier = 10/min)


class FootballDataClient:
    """
    Thin wrapper around the football-data.org v4 REST API.

    Example:
        client = FootballDataClient()
        matches = client.get_matches()
        standings = client.get_standings()
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FOOTBALL_DATA_API_KEY not set. "
                "Register free at https://www.football-data.org/client/register"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": self.api_key,
            "Accept": "application/json",
        })
        self._last_request_time: float = 0.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _throttle(self):
        """Respect free-tier rate limit (10 req/min)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)

    def _get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Make a GET request and return the parsed JSON response."""
        self._throttle()
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=10)
            self._last_request_time = time.time()
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            logger.error(f"HTTP {resp.status_code} for {url}: {resp.text}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    # ── Public API methods ────────────────────────────────────────────────────

    def get_competition(self) -> dict:
        """Return competition metadata for WC 2026."""
        return self._get(f"/competitions/{WC_2026_CODE}")

    def get_teams(self) -> list[dict]:
        """Return all 48 teams in the tournament."""
        data = self._get(f"/competitions/{WC_2026_CODE}/teams")
        return data.get("teams", [])

    def get_matches(self, stage: Optional[str] = None) -> list[dict]:
        """
        Return all matches. Optionally filter by stage.
        Stages: GROUP_STAGE, ROUND_OF_16, QUARTER_FINALS,
                SEMI_FINALS, THIRD_PLACE, FINAL
        """
        params = {}
        if stage:
            params["stage"] = stage
        data = self._get(f"/competitions/{WC_2026_CODE}/matches", params=params)
        return data.get("matches", [])

    def get_standings(self) -> list[dict]:
        """Return group stage standings (list of group tables)."""
        data = self._get(f"/competitions/{WC_2026_CODE}/standings")
        return data.get("standings", [])

    def get_scorers(self, limit: int = 20) -> list[dict]:
        """Return top scorers for the tournament."""
        data = self._get(
            f"/competitions/{WC_2026_CODE}/scorers",
            params={"limit": limit}
        )
        return data.get("scorers", [])

    def get_team_squad(self, team_api_id: int) -> list[dict]:
        """Return the squad for a specific team."""
        data = self._get(f"/teams/{team_api_id}")
        return data.get("squad", [])

    def get_match(self, match_api_id: int) -> dict:
        """Return detailed data for a single match."""
        return self._get(f"/matches/{match_api_id}")

    # ── Convenience: fetch everything in one call ─────────────────────────────

    def fetch_all(self) -> dict[str, Any]:
        """
        Fetch teams, matches, and standings in one orchestrated call.
        Respects rate limiting automatically.
        Returns a dict with keys: teams, matches, standings, scorers
        """
        logger.info("Fetching full WC 2026 dataset from football-data.org …")
        return {
            "teams": self.get_teams(),
            "matches": self.get_matches(),
            "standings": self.get_standings(),
            "scorers": self.get_scorers(limit=30),
        }
