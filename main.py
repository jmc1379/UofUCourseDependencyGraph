import argparse

from src.Pipeline import Pipeline

# U of U term IDs for reference:
# 1258 = Fall 2025
# 1264 = Spring 2026
# 1266 = Summer 2026
# 1268 = Fall 2026
DEFAULT_TERM = "1258"

# Departments scraped when --all is passed.
# Expand this list as more departments are supported.
ALL_DEPARTMENTS = ["CS", "MATH", "ECE", "PHYS"]

# Default speed values — moderate but not aggressive.
DEFAULT_SEMAPHORE = 2
DEFAULT_DELAY     = 0.3

# Polite preset — used when --polite is passed and no explicit
# --semaphore / --delay overrides are given.
POLITE_SEMAPHORE = 1
POLITE_DELAY     = 3.0


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
        "--polite",
        action="store_true",
        help=(
            f"Run with conservative speed settings to avoid rate limiting "
            f"(semaphore={POLITE_SEMAPHORE}, delay={POLITE_DELAY}s). "
            f"Overridden by explicit --semaphore or --delay."
        ),
    )
    parser.add_argument(
        "--semaphore",
        type=int,
        default=None,
        help=f"Maximum concurrent requests (default: {DEFAULT_SEMAPHORE}, "
             f"or {POLITE_SEMAPHORE} with --polite).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help=f"Seconds to pause between requests (default: {DEFAULT_DELAY}, "
             f"or {POLITE_DELAY} with --polite).",
    )

    args = parser.parse_args()

    # ── Validate department arguments ─────────────────────────────────────────
    if args.all and args.department:
        parser.error("--all and --department are mutually exclusive.")
    if not args.all and not args.department:
        parser.error("One of --department or --all is required.")

    # ── Resolve speed settings ────────────────────────────────────────────────
    # Precedence: explicit flag > polite preset > default.
    if args.semaphore is not None:
        semaphore = args.semaphore
    elif args.polite:
        semaphore = POLITE_SEMAPHORE
    else:
        semaphore = DEFAULT_SEMAPHORE

    if args.delay is not None:
        delay = args.delay
    elif args.polite:
        delay = POLITE_DELAY
    else:
        delay = DEFAULT_DELAY

    # ── Determine target departments ──────────────────────────────────────────
    if args.all:
        department_codes = ALL_DEPARTMENTS
    else:
        department_codes = [args.department.upper()]

    # ── Run the pipeline ──────────────────────────────────────────────────────
    pipeline = Pipeline(
        term=args.term,
        semaphore=semaphore,
        request_delay=delay,
    )
    pipeline.run_scrape(department_codes, refresh=args.refresh)


if __name__ == "__main__":
    main()