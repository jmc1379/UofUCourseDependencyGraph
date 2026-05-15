import asyncio
import logging
from pathlib import Path

from src.scraping.UofUCatalogFetcher import UofUCatalogFetcher
from src.scraping.UofUCatalogParser import UofUCatalogParser
from src.storage.CacheManager import CacheManager


class Pipeline:
    """
    Orchestrates the scraping pipeline: fetch course data, parse it,
    and populate the database using the two-pass insertion approach.
    """

    def __init__(self, term: str, semaphore: int = 5):
        self.term      = term
        self.semaphore = semaphore
        self._configure_logging()

    # ─── Logging ──────────────────────────────────────────────────────────────

    def _configure_logging(self) -> None:
        """Configure logging once for the whole run — console and file output."""
        log_path = Path(__file__).parent.parent / "data" / "pipeline.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(),                 # console
                logging.FileHandler(log_path, mode="a"), # file
            ],
        )

    # ─── Scraping ─────────────────────────────────────────────────────────────

    def run_scrape(self, department_codes: list[str], refresh: bool = False) -> None:
        """
        Scrape the given departments and populate the database.
        If refresh is True, existing department data is cleared first.
        """
        logging.info(f"Starting scrape for departments: {', '.join(department_codes)}")
        try:
            asyncio.run(self._scrape_async(department_codes, refresh))
            logging.info("Scrape completed successfully.")
        except Exception as e:
            logging.error(f"Scrape failed: {e}", exc_info=True)
            raise

    async def _scrape_async(self, department_codes: list[str], refresh: bool) -> None:
        """Async portion of the scrape — fetching is async, DB work is sync."""
        parser = UofUCatalogParser()

        with CacheManager() as cache:
            async with UofUCatalogFetcher(term=self.term, semaphore=self.semaphore) as fetcher:

                # ── Discover course numbers per department ────────────────────
                department_map = {}
                for department_code in department_codes:
                    if refresh:
                        logging.info(f"Refresh enabled — clearing {department_code} from cache.")
                        cache.clear_department(department_code)

                    list_html = await fetcher.fetch_department_list(department_code)
                    if list_html is None:
                        logging.error(f"Could not fetch course list for {department_code}, skipping.")
                        continue

                    course_numbers = parser.get_course_list(list_html)
                    logging.info(f"{department_code}: discovered {len(course_numbers)} courses.")

                    # Filter out courses already cached and fresh (unless refreshing)
                    if not refresh:
                        course_numbers = [
                            n for n in course_numbers
                            if not self._is_cached_and_fresh(cache, department_code, n)
                        ]
                        logging.info(f"{department_code}: {len(course_numbers)} courses need fetching.")

                    department_map[department_code] = course_numbers

                # ── Fetch all course detail pages ─────────────────────────────
                html_by_department = await fetcher.fetch_all(department_map)

                # ── Pass 1: parse and insert all courses ──────────────────────
                inserted_courses = []
                for department_code, html_list in html_by_department.items():
                    for html in html_list:
                        course = parser.parse_course_detail(html, department_code)
                        if course is None:
                            continue
                        inserted = cache.insert_course(course)
                        inserted_courses.append(inserted)

                logging.info(f"Pass 1 complete — inserted {len(inserted_courses)} courses.")

                # ── Pass 2: link prerequisite relationships ───────────────────
                for course in inserted_courses:
                    cache.insert_prerequisites(course)

                logging.info(f"Pass 2 complete — linked prerequisites for {len(inserted_courses)} courses.")

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _is_cached_and_fresh(cache: CacheManager, department_code: str, course_number: str) -> bool:
        """Return True if the course is already in the cache and not stale."""
        row = cache.get_course_by_code(department_code, course_number)
        if row is None:
            return False
        return not cache.is_stale(row["course_id"])