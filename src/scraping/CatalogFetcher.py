import asyncio
import logging
from abc import ABC, abstractmethod

import aiohttp

MAX_RETRIES   = 5
REQUEST_DELAY = 0.3    # seconds between requests (be polite)


class CatalogFetcher(ABC):
    def __init__(self, semaphore: int = 5):
        self.semaphore = asyncio.Semaphore(semaphore)
        self.session: aiohttp.ClientSession | None = None

    # ─── Context Manager ──────────────────────────────────────────────────────

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def close(self):
        """Cleanly close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    # ─── Abstract Interface ───────────────────────────────────────────────────

    @abstractmethod
    def _construct_course_url(self, department_code: str, course_number: str) -> str:
        """Construct the URL for a single course detail page."""
        pass

    @abstractmethod
    def _construct_department_list_url(self, department_code: str) -> str:
        """Construct the URL for a department course listing page."""
        pass

    # ─── Shared Fetch Logic ───────────────────────────────────────────────────

    async def _fetch(self, url: str, label: str) -> str | None:
        """
        Core fetch method with retry logic and error handling.
        Used internally by fetch_course and fetch_department_list.
        """
        for attempt in range(MAX_RETRIES):
            try:
                async with self.semaphore:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            await asyncio.sleep(REQUEST_DELAY)
                            return await response.text()
                        else:
                            logging.warning(
                                f"{label}: HTTP {response.status} "
                                f"on attempt {attempt + 1}/{MAX_RETRIES}"
                            )
            except aiohttp.ClientError as e:
                logging.warning(
                    f"{label}: Request failed "
                    f"on attempt {attempt + 1}/{MAX_RETRIES} — {e}"
                )

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(REQUEST_DELAY)

        logging.error(f"{label}: All {MAX_RETRIES} attempts failed, skipping.")
        return None

    # ─── Public Fetch Methods ─────────────────────────────────────────────────

    async def fetch_course(self, department_code: str, course_number: str) -> str | None:
        """Fetch a single course detail page. Returns HTML string or None on failure."""
        url   = self._construct_course_url(department_code, course_number)
        label = f"{department_code} {course_number}"
        return await self._fetch(url, label)

    async def fetch_department_list(self, department_code: str) -> str | None:
        """Fetch the course listing page for a department. Returns HTML string or None on failure."""
        url   = self._construct_department_list_url(department_code)
        label = f"{department_code} list page"
        return await self._fetch(url, label)

    async def fetch_department(self, department_code: str, course_numbers: list[str]) -> list[str]:
        """
        Fetch all course detail pages for a given list of course numbers concurrently.
        Returns a list of HTML strings for successfully fetched courses.
        """
        logging.info(f"{department_code}: fetching {len(course_numbers)} courses...")

        results = await asyncio.gather(
            *[self.fetch_course(department_code, number) for number in course_numbers],
            return_exceptions=False
        )

        successful = [html for html in results if html is not None]
        logging.info(
            f"{department_code}: {len(successful)}/{len(course_numbers)} "
            f"courses fetched successfully."
        )
        return successful

    async def fetch_all(self, department_map: dict[str, list[str]]) -> dict[str, list[str]]:
        """
        Fetch all course detail pages for every department.
        Accepts a dict mapping department code to list of course numbers to fetch.
        Returns a dict mapping department code to list of HTML strings.
        """
        logging.info(f"Beginning full fetch for {len(department_map)} departments.")
        results = {}
        for department_code, course_numbers in department_map.items():
            results[department_code] = await self.fetch_department(department_code, course_numbers)
        logging.info("Full fetch complete.")
        return results