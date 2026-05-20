"""
Populate the database from saved HTML fixtures — no network access required.

This is a development utility for rebuilding a working database without
scraping the live catalog. It runs the saved fixture pages through the real
UofUCatalogParser and inserts the results via CacheManager, using the same
two-pass approach as the real pipeline.

Usage:
    python load_fixtures.py
"""

import logging
from pathlib import Path

from src.scraping.UofUCatalogParser import UofUCatalogParser
from src.storage.CacheManager import CacheManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Map each course-detail fixture file to its department code.
# Add entries here as you capture more fixtures.
COURSE_FIXTURES = {
    "cs_1400_detail.html": "CS",
    "cs_3500_detail.html": "CS",
    "cs_4400_detail.html": "CS",
    "cs_6961_detail.html": "CS",
}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    parser = UofUCatalogParser()

    with CacheManager() as cache:
        inserted_courses = []

        # ── Pass 1: parse and insert every course ─────────────────────────────
        for filename, department_code in COURSE_FIXTURES.items():
            path = FIXTURES_DIR / filename
            if not path.exists():
                logging.warning(f"Fixture not found, skipping: {filename}")
                continue

            html   = path.read_text(encoding="utf-8")
            course = parser.parse_course_detail(html, department_code)
            if course is None:
                logging.warning(f"Could not parse {filename}, skipping.")
                continue

            inserted = cache.insert_course(course)
            inserted_courses.append(inserted)
            logging.info(f"Inserted {inserted.course_code} — {inserted.course_name}")

        # ── Pass 2: link prerequisite relationships ───────────────────────────
        for course in inserted_courses:
            cache.insert_prerequisites(course)

        logging.info(
            f"Done. Inserted {len(inserted_courses)} courses and linked their prerequisites."
        )

        # ── Quick summary ─────────────────────────────────────────────────────
        all_courses = cache.get_all_courses()
        logging.info(f"Database now contains {len(all_courses)} courses total.")


if __name__ == "__main__":
    main()