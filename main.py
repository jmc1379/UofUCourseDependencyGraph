import argparse

from src.Pipeline import Pipeline

# U of U term IDs for reference:
# 1258 = Fall 2025
# 1264 = Spring 2026
# 1266 = Summer 2026
# 1268 = Fall 2026
DEFAULT_TERM = "1268"

# Departments scraped when --all is passed.
# Expand this list as more departments are supported.
ALL_DEPARTMENTS = ["CS", "MATH", "ECE", "PHYS"]


def main():
    parser = argparse.ArgumentParser(
        description="Scrape University of Utah course data and build a prerequisite graph."
    )

    parser.add_argument(
        "--department",
        type=str,
        help="Department code to scrape, e.g. CS. Mutually exclusive with --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all supported departments.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Clear existing cached data for the target departments before scraping.",
    )
    parser.add_argument(
        "--term",
        type=str,
        default=DEFAULT_TERM,
        help=f"Term ID to scrape (default: {DEFAULT_TERM}).",
    )
    parser.add_argument(
        "--semaphore",
        type=int,
        default=5,
        help="Maximum concurrent requests (default: 5).",
    )

    args = parser.parse_args()

    # ── Validate arguments ────────────────────────────────────────────────────
    if args.all and args.department:
        parser.error("--all and --department are mutually exclusive.")
    if not args.all and not args.department:
        parser.error("One of --department or --all is required.")

    # ── Determine target departments ──────────────────────────────────────────
    if args.all:
        department_codes = ALL_DEPARTMENTS
    else:
        department_codes = [args.department.upper()]

    # ── Run the pipeline ──────────────────────────────────────────────────────
    pipeline = Pipeline(term=args.term, semaphore=args.semaphore)
    pipeline.run_scrape(department_codes, refresh=args.refresh)


if __name__ == "__main__":
    main()