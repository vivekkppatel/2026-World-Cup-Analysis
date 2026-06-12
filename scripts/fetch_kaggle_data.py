"""
scripts/fetch_kaggle_data.py
─────────────────────────────
Download the two Kaggle datasets into data/external/kaggle/ (gitignored).

1. kulkarniparth09/fifa-world-cup-complete-dataset-19302026
   → 2026 team metadata (FIFA ranks, confederations, coaches) and a
     1930–2026 tournament-edition summary. NOTE: its "all matches" file
     is a small curated subset — the Fjelstul database remains the
     authoritative historical match source.
2. ardaciftci/road-to-2026-world-cup-squad-prediction
   → pre-tournament form snapshot for 1,176 national-team players
     (appearances, goals, assists, minutes, contribution metrics).

Uses kagglehub anonymous access (public datasets, no API token needed).
Licenses are set by the dataset authors on their Kaggle pages; data is
kept out of git and re-fetched from source.

Run:
    python scripts/fetch_kaggle_data.py
Then:
    python scripts/load_kaggle_data.py
"""
import logging
import shutil
import sys
from pathlib import Path

import kagglehub

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEST_DIR = Path(__file__).parent.parent / "data" / "external" / "kaggle"

DATASETS = {
    "kulkarniparth09/fifa-world-cup-complete-dataset-19302026": "wc_complete",
    "ardaciftci/road-to-2026-world-cup-squad-prediction": "road_to_2026",
}

SOURCES_NOTE = """Kaggle community datasets — re-fetched from source, not redistributed.

1. FIFA World Cup Complete Dataset 1930-2026
   https://www.kaggle.com/datasets/kulkarniparth09/fifa-world-cup-complete-dataset-19302026
2. Road to 2026 World Cup Squad Prediction
   https://www.kaggle.com/datasets/ardaciftci/road-to-2026-world-cup-squad-prediction

License terms are those stated on each dataset's Kaggle page.
"""


def main() -> None:
    logger.info("Fetching Kaggle datasets …")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    (DEST_DIR / "SOURCES.txt").write_text(SOURCES_NOTE, encoding="utf-8")

    failures = 0
    for slug, folder in DATASETS.items():
        try:
            cache_path = Path(kagglehub.dataset_download(slug))
        except Exception as e:
            logger.error(f"  ✗ {slug}: {e}")
            failures += 1
            continue

        dest = DEST_DIR / folder
        dest.mkdir(exist_ok=True)
        copied = 0
        for csv in cache_path.rglob("*.csv"):
            shutil.copy2(csv, dest / csv.name)
            copied += 1
        logger.info(f"  ✓ {slug} → {dest}  ({copied} files)")

    if failures:
        sys.exit(1)
    logger.info("Done. Next: python scripts/load_kaggle_data.py")


if __name__ == "__main__":
    main()
