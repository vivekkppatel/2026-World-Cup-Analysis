"""
scripts/fetch_external_data.py
───────────────────────────────
Download the Fjelstul World Cup Database CSVs (1930–2022 history).

Source:  https://github.com/jfjelstul/worldcup
License: CC-BY-SA 4.0 — © Joshua C. Fjelstul, Ph.D.
         Attribution is required; see README "Data Sources".

Used for: historical team-strength features (Elo priors) for the
leakage-free match predictor, and long-horizon EDA.

Run:
    python scripts/fetch_external_data.py
"""
import logging
import sys
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv"
DEST_DIR = Path(__file__).parent.parent / "data" / "external" / "fjelstul"

# Only what the project consumes — the full database has 27 files.
FILES = [
    "matches.csv",        # every WC match 1930–2022: teams, scores, stage
    "teams.csv",          # team id ↔ name ↔ confederation
    "tournaments.csv",    # tournament metadata (year, host, winner)
    "team_appearances.csv",  # one row per team per match — Elo input
    "goals.csv",          # goal-level detail for EDA
    "squads.csv",         # historical squad lists for EDA
]

ATTRIBUTION = (
    "Fjelstul World Cup Database © Joshua C. Fjelstul, Ph.D.\n"
    "https://github.com/jfjelstul/worldcup — CC-BY-SA 4.0\n"
)


def fetch_file(filename: str, dest_dir: Path, timeout: int = 60) -> bool:
    """Download one CSV. Returns True on success."""
    url = f"{BASE_URL}/{filename}"
    dest = dest_dir / filename
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info(f"  ✓ {filename}  ({len(resp.content) / 1024:.0f} KB)")
        return True
    except requests.RequestException as e:
        logger.error(f"  ✗ {filename}: {e}")
        return False


def main() -> None:
    logger.info("Fetching Fjelstul World Cup Database (1930–2022) …")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    (DEST_DIR / "ATTRIBUTION.txt").write_text(ATTRIBUTION, encoding="utf-8")

    results = [fetch_file(f, DEST_DIR) for f in FILES]
    n_ok = sum(results)
    logger.info(f"Done: {n_ok}/{len(FILES)} files in {DEST_DIR}")
    if n_ok < len(FILES):
        sys.exit(1)


if __name__ == "__main__":
    main()
