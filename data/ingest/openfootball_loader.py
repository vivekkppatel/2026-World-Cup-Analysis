"""
data/ingest/openfootball_loader.py
───────────────────────────────────
WC 2026 fixtures/results from openfootball/worldcup.json — a public-domain
(CC0) community dataset. No API key required.

Role in the pipeline: fallback + bootstrap source. football-data.org remains
the primary live source (faster updates, richer fields); openfootball is
maintainer-updated roughly daily, so scores lag by hours. Fixtures, groups,
and venues are complete for all 104 matches.

Source: https://github.com/openfootball/worldcup.json (CC0-1.0)

Usage:
    loader = OpenFootballLoader()
    fixtures = loader.get_matches_2026()   # normalized DataFrame
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

URL_2026 = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# openfootball round labels → the stage vocabulary used across this project
# (matches football-data.org's stage names so downstream code sees one format)
_STAGE_MAP = {
    "round of 32":   "LAST_32",
    "round of 16":   "LAST_16",
    "quarter":       "QUARTER_FINALS",
    "semi":          "SEMI_FINALS",
    "third place":   "THIRD_PLACE",
    "match for third place": "THIRD_PLACE",
    "final":         "FINAL",
}


class OpenFootballLoader:
    """Fetch and normalize openfootball WC 2026 fixture data."""

    def __init__(self, url: str = URL_2026, timeout: int = 30):
        self.url = url
        self.timeout = timeout

    def fetch_raw(self) -> dict[str, Any]:
        """Download the raw tournament JSON. Raises on HTTP errors."""
        resp = requests.get(self.url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_matches_2026(self) -> pd.DataFrame:
        """
        Return all 104 WC 2026 matches as a normalized DataFrame with columns:
        match_number, home_team_name, away_team_name, home_score, away_score,
        stage, group_name, kickoff_utc, venue, status, round_label
        """
        raw = self.fetch_raw()
        rows = [self._normalize_match(m, idx) for idx, m in enumerate(raw.get("matches", []), start=1)]
        df = pd.DataFrame(rows)
        logger.info(f"openfootball: loaded {len(df)} WC 2026 matches "
                    f"({(df['status'] == 'FINISHED').sum()} finished)")
        return df

    # ── Normalization helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_kickoff(date_str: str, time_str: Optional[str]) -> Optional[datetime]:
        """
        Combine openfootball date ('2026-06-11') and time ('13:00 UTC-6')
        into a UTC-aware datetime. Returns date-only midnight UTC if the
        time is missing or unparseable.
        """
        try:
            base = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

        if time_str:
            m = re.match(r"(\d{1,2}):(\d{2})\s*UTC([+-]\d{1,2})?", time_str)
            if m:
                hour, minute = int(m.group(1)), int(m.group(2))
                offset_h = int(m.group(3)) if m.group(3) else 0
                local = base.replace(hour=hour, minute=minute,
                                     tzinfo=timezone(timedelta(hours=offset_h)))
                return local.astimezone(timezone.utc)

        return base.replace(tzinfo=timezone.utc)

    @classmethod
    def _parse_stage(cls, round_label: str, group: Optional[str]) -> str:
        """Map openfootball round labels onto the project stage vocabulary."""
        if group:  # any match with a group assignment is group stage
            return "GROUP_STAGE"
        label = (round_label or "").lower()
        for needle, stage in _STAGE_MAP.items():
            if needle in label:
                return stage
        return "KNOCKOUT"  # unknown knockout round — never silently group

    @classmethod
    def _normalize_match(cls, m: dict[str, Any], idx: int) -> dict[str, Any]:
        """
        Flatten one openfootball match object into pipeline columns.

        `idx` is the 1-based position in the JSON array, which follows the
        official FIFA match numbering (1–104). Knockout entries carry an
        explicit "num" field that takes precedence; group-stage entries
        don't have one, so the array position is the key.
        """
        group_raw = m.get("group") or ""          # e.g. "Group A"
        group_name = group_raw.replace("Group", "").strip()[:1]

        score1, score2 = m.get("score1"), m.get("score2")
        is_finished = score1 is not None and score2 is not None

        winner = None
        if is_finished:
            if score1 > score2:
                winner = "HOME"
            elif score2 > score1:
                winner = "AWAY"
            else:
                winner = "DRAW"

        return {
            "match_number":   m.get("num") or idx,
            "home_team_name": m.get("team1"),
            "away_team_name": m.get("team2"),
            "home_score":     score1,
            "away_score":     score2,
            "stage":          cls._parse_stage(m.get("round", ""), m.get("group")),
            "group_name":     group_name,
            "kickoff_utc":    cls._parse_kickoff(m.get("date", ""), m.get("time")),
            "venue":          m.get("ground", ""),
            "status":         "FINISHED" if is_finished else "SCHEDULED",
            "winner":         winner,
            "round_label":    m.get("round", ""),
        }
