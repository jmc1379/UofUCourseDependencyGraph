import asyncio
import logging
from pathlib import Path
from typing import Callable

from src.models.Course import Course
from src.scraping.CatalogFetcher import CatalogFetcher
from src.scraping.CatalogParser import CatalogParser
from src.scraping.UofUCatalogFetcher import UofUCatalogFetcher
from src.scraping.UofUCatalogParser import UofUCatalogParser
from src.storage.CacheManager import CacheManager


class Pipeline:
    """
    Orchestrates the scraping pipeline: fetch course data, parse it,
    and populate the database using the two-pass insertion approach.
    """

    def __init__(
        self,
        term: str,
        semaphore: int = 5,
        cache_factory: Callable[[], CacheManager] | None = None,
        fetcher_factory: Callable[[], CatalogFetcher] | None = None,
        parser_factory: Callable[[], CatalogParser] | None = None,
    ):
        """
        Construct a Pipeline. The factory parameters allow tests to inject
        custom implementations without changing production code.

        - cache_factory:   () -> CacheManager (defaults to real CacheManager)
        - fetcher_factory: () -> CatalogFetcher (defaults to UofUCatalogFetcher)
        - parser_factory:  () -> CatalogParser  (defaults to UofUCatalogParser)
        """
        self.term      = term
        self.semaphore = semaphore

        self._cache_factory   = cache_factory   or (lambda: CacheManager())
        self._fetcher_factory = fetcher_factory or (lambda: UofUCatalogFetcher(term=term, semaphore=semaphore))
        self._parser_factory  = parser_factory  or (lambda: UofUCatalogParser())

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
        self.parser = self._parser_factory()

        with self._cache_factory() as cache:
            async with self._fetcher_factory() as fetcher:
                self.fetcher = fetcher

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

                    course_numbers = self.parser.get_course_list(list_html)
                    logging.info(f"{department_code}: discovered {len(course_numbers)} courses.")

                    if not refresh:
                        course_numbers = [
                            n for n in course_numbers
                            if not self._is_cached_and_fresh(cache, department_code, n)
                        ]
                        logging.info(f"{department_code}: {len(course_numbers)} courses need fetching.")

                    department_map[department_code] = course_numbers

                # ── Fetch + parse every course (with section fallback) ────────
                inserted_courses = []
                for department_code, course_numbers in department_map.items():
                    logging.info(f"{department_code}: fetching {len(course_numbers)} courses...")

                    courses = await asyncio.gather(*[
                        self._fetch_and_parse_course(department_code, number)
                        for number in course_numbers
                    ])

                    dept_inserted = 0
                    dept_skipped  = 0
                    for course in courses:
                        if course is None:
                            dept_skipped += 1
                            continue
                        inserted = cache.insert_course(course)
                        inserted_courses.append(inserted)
                        dept_inserted += 1

                    logging.info(
                        f"{department_code}: pass 1 inserted {dept_inserted}, "
                        f"skipped {dept_skipped}."
                    )

                logging.info(f"Pass 1 complete — inserted {len(inserted_courses)} courses.")

                # ── Pass 2: link prerequisite relationships ───────────────────
                for course in inserted_courses:
                    cache.insert_prerequisites(course)

                logging.info(
                    f"Pass 2 complete — linked prerequisites for {len(inserted_courses)} courses."
                )

    # ─── Per-course fetch + parse with section fallback ───────────────────────

    async def _fetch_and_parse_course(
        self, department_code: str, course_number: str
    ) -> Course | None:
        """
        Fetch and parse a single course. Tries section 001 first; if that page
        is a stub (no real course content), looks up a valid section from the
        course's section listing page and retries. Returns a Course or None.
        """
        # ── First attempt: section 001 ────────────────────────────────────────
        html = await self.fetcher.fetch_course(department_code, course_number, section="001")
        if html is not None and self.parser.is_course_page(html):
            return self.parser.parse_course_detail(html, department_code)

        # ── Fallback: discover a real section from the sections page ──────────
        logging.info(
            f"{department_code} {course_number}: section 001 not a valid course "
            f"page, checking sections listing."
        )
        sections_html = await self.fetcher.fetch_sections(department_code, course_number)
        if sections_html is None:
            logging.warning(
                f"{department_code} {course_number}: could not fetch sections page, skipping."
            )
            return None

        section = self.parser.get_section_number(sections_html)
        if section is None:
            logging.warning(
                f"{department_code} {course_number}: no valid section found "
                f"(no scheduled sections this term), skipping."
            )
            return None

        # ── Second attempt: the real section ──────────────────────────────────
        html = await self.fetcher.fetch_course(department_code, course_number, section=section)
        if html is None or not self.parser.is_course_page(html):
            logging.warning(
                f"{department_code} {course_number}: section {section} page still "
                f"not a valid course page, skipping."
            )
            return None

        return self.parser.parse_course_detail(html, department_code)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _is_cached_and_fresh(cache: CacheManager, department_code: str, course_number: str) -> bool:
        """Return True if the course is already in the cache and not stale."""
        row = cache.get_course_by_code(department_code, course_number)
        if row is None:
            return False
        return not cache.is_stale(row["course_id"])