import asyncio
import logging
from abc import ABC, abstractmethod

import aiohttp

MAX_RETRIES        = 3
RATE_LIMIT_BACKOFF = 2.0    # base seconds for exponential backoff when rate limited


class BlockedError(Exception):
    """
    Raised when the server responds with HTTP 403 — the client is being
    actively blocked. This is non-recoverable within the run; the pipeline
    catches this at the top level and aborts cleanly.
    """
    def __init__(self, url: str):
        super().__init__(f"Blocked by server (HTTP 403): {url}")
        self.url = url


class CatalogFetcher(ABC):
    def __init__(self, semaphore: int = 5, request_delay: float = 0.3):
        """
        - semaphore: maximum concurrent in-flight requests.
        - request_delay: polite pause (seconds) after every successful request.
        """
        self.semaphore     = asyncio.Semaphore(semaphore)
        self.request_delay = request_delay
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
    def _construct_course_url(self, department_code: str, course_number: str, section: str) -> str:
        """Construct the URL for a single course detail page for a given section."""
        pass

    @abstractmethod
    def _construct_department_list_url(self, department_code: str) -> str:
        """Construct the URL for a department course listing page."""
        pass

    @abstractmethod
    def _construct_sections_url(self, department_code: str, course_number: str) -> str:
        """Construct the URL for a course's section listing page."""
        pass

    # ─── Shared Fetch Logic ───────────────────────────────────────────────────

    async def _fetch(self, url: str, label: str) -> str | None:
        """
        Core fetch method with retry logic, error handling, and rate-limit
        detection.

        - HTTP 200: returned as text.
        - HTTP 429: retried with exponential backoff (rate limited).
        - HTTP 403: raises BlockedError immediately, halting the entire run.
        - Other failures: retried with the standard polite delay.
        """
        for attempt in range(MAX_RETRIES):
            rate_limited = False
            try:
                async with self.semaphore:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            await asyncio.sleep(self.request_delay)
                            return html
                        elif response.status == 429:
                            rate_limited = True
                            logging.warning(
                                f"{label}: HTTP 429 (rate limited) "
                                f"on attempt {attempt + 1}/{MAX_RETRIES}."
                            )
                        elif response.status == 403:
                            logging.error(
                                f"{label}: HTTP 403 (forbidden) — server is "
                                f"actively blocking requests. Aborting scrape."
                            )
                            raise BlockedError(url)
                        else:
                            logging.warning(
                                f"{label}: HTTP {response.status} "
                                f"on attempt {attempt + 1}/{MAX_RETRIES}."
                            )
            except aiohttp.ClientError as e:
                logging.warning(
                    f"{label}: request failed "
                    f"on attempt {attempt + 1}/{MAX_RETRIES} — {e}"
                )

            # Wait before the next attempt. Rate-limited responses get an
            # exponentially growing backoff; everything else gets the
            # standard polite delay. Skip the wait after the final attempt.
            if attempt < MAX_RETRIES - 1:
                if rate_limited:
                    backoff = RATE_LIMIT_BACKOFF * (2 ** attempt)
                    logging.info(f"{label}: backing off {backoff:.1f}s before retry.")
                    await asyncio.sleep(backoff)
                else:
                    await asyncio.sleep(self.request_delay)

        logging.error(f"{label}: all {MAX_RETRIES} attempts failed, skipping.")
        return None

    # ─── Public Fetch Methods ─────────────────────────────────────────────────

    async def fetch_course(
        self, department_code: str, course_number: str, section: str = "001"
    ) -> str | None:
        """
        Fetch a single course detail page for the given section (default 001).
        Returns HTML string or None on failure.
        """
        url   = self._construct_course_url(department_code, course_number, section)
        label = f"{department_code} {course_number} (section {section})"
        return await self._fetch(url, label)

    async def fetch_sections(self, department_code: str, course_number: str) -> str | None:
        """Fetch a course's section listing page. Returns HTML string or None on failure."""
        url   = self._construct_sections_url(department_code, course_number)
        label = f"{department_code} {course_number} sections page"
        return await self._fetch(url, label)

    async def fetch_department_list(self, department_code: str) -> str | None:
        """Fetch the course listing page for a department. Returns HTML string or None on failure."""
        url   = self._construct_department_list_url(department_code)
        label = f"{department_code} list page"
        return await self._fetch(url, label)