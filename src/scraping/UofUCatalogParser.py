import datetime
import logging
import re

from bs4 import BeautifulSoup

from src.models.Course import Course
from src.scraping.CatalogParser import CatalogParser

# Matches course numbers in U of U department list page links
# e.g. sections.html?subj=CS&catno=3500
COURSE_LIST_RE = re.compile(r"sections\.html\?subj=\w+&catno=(\d{4}[A-Z]?)")

# Matches a department-qualified course code (e.g. "MATH 1060"), or a bare
# course number chained onto a preceding department via "OR" (e.g. "OR 1080"
# in "MATH 1050 OR 1060 OR 1080"). The department group excludes "OR"/"AND"
# so the connector word itself is never mistaken for a course code — U of U
# prereq strings list alternatives without repeating the department prefix.
PREREQUISITE_CODE_RE = re.compile(
    r"\b(?:(?!OR\b|AND\b)([A-Z]{2,})\s+(\d{4}[A-Z]?)|OR\s+(\d{4}[A-Z]?))\b"
)


class UofUCatalogParser(CatalogParser):

    def get_course_list(self, html: str) -> list[str]:
        """
        Parse a U of U department listing page and return unique course numbers.
        Course numbers are extracted from section links in the page.
        """
        soup    = BeautifulSoup(html, "lxml")
        numbers = set()

        for a in soup.find_all("a", href=True):
            match = COURSE_LIST_RE.search(a["href"])
            if match:
                numbers.add(match.group(1))

        return sorted(numbers, key=lambda x: int(re.sub(r"[A-Z]", "", x)))

    def is_course_page(self, html: str) -> bool:
        """
        Return True if the HTML looks like a real course detail page rather than
        a stub (e.g. a page for a section that doesn't exist, or a rate-limit
        page). A genuine course detail page always has an <h1> with the course
        name; stubs do not.
        """
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        if not h1:
            return False
        # The department/section listing pages also have an <h1>, but it reads
        # like "Main Campus - Fall 2026 Class Schedule". A real course page's
        # <h1> starts with a course code like "CS 4400".
        h1_text = h1.get_text(" ").strip()
        return bool(re.match(r"[A-Z]+\s+\d{4}[A-Z]?", h1_text))

    def get_section_number(self, html: str) -> str | None:
        """
        Parse a U of U section listing page and return the first section number,
        e.g. "010". Returns None if the page has no section rows (course has no
        scheduled sections this term).
        """
        soup  = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return None

        body = table.find("tbody")
        if not body:
            return None

        first_row = body.find("tr")
        if not first_row:
            return None

        section_cell = first_row.find("td", attrs={"data-label": "Section"})
        if not section_cell:
            return None

        section = section_cell.get_text(strip=True)
        return section or None

    def parse_course_detail(self, html: str, department_code: str) -> Course | None:
        """
        Parse a U of U course detail page and return a Course with placeholder IDs.
        Returns None if required fields cannot be extracted. Every failure path
        logs a warning identifying where parsing stopped.
        """
        try:
            soup = BeautifulSoup(html, "lxml")

            # ── Course name and number ────────────────────────────────────────
            h1 = soup.find("h1")
            if not h1:
                logging.warning(
                    f"{department_code}: parse failed — no <h1> element on page "
                    f"(html length {len(html)})."
                )
                return None

            h1_text    = h1.get_text(" ").strip()
            name_match = re.match(r"[A-Z]+\s+(\d{4}[A-Z]?)\s*[-–]?\s*(.*)", h1_text, re.DOTALL)
            if not name_match:
                logging.warning(
                    f"{department_code}: parse failed — <h1> did not match expected "
                    f"course pattern. h1 text was: {h1_text!r}"
                )
                return None

            course_number = name_match.group(1).strip()
            course_name   = name_match.group(2).strip() or f"{department_code} {course_number}"
            # Collapse any internal whitespace/newlines in the name
            course_name   = re.sub(r"\s+", " ", course_name)

            # ── Units ─────────────────────────────────────────────────────────
            units_span   = soup.find("span", class_="col")
            course_units = 0.0
            if units_span:
                try:
                    course_units = float(units_span.get_text(strip=True))
                except ValueError:
                    logging.warning(
                        f"{department_code} {course_number}: could not parse units "
                        f"from {units_span.get_text(strip=True)!r}, defaulting to 0.0."
                    )
                    course_units = 0.0
            else:
                logging.warning(
                    f"{department_code} {course_number}: no units span found, "
                    f"defaulting to 0.0."
                )

            # ── Enrollment requirement ────────────────────────────────────────
            raw_prerequisites_string = ""
            enrollment_body = self._find_card_body(soup, "Enrollment Information")
            if enrollment_body:
                req_span = enrollment_body.find("span")
                if req_span:
                    raw_prerequisites_string = req_span.get_text(strip=True)

            # ── Description ───────────────────────────────────────────────────
            course_description = ""
            desc_body = self._find_card_body(soup, "Description")
            if desc_body:
                desc_col = desc_body.find("div", class_="col")
                if desc_col:
                    course_description = desc_col.get_text(strip=True)[:2000]

            # ── Prerequisite course codes ─────────────────────────────────────
            prerequisite_codes = self.parse_prerequisites(raw_prerequisites_string)

            return Course(
                department_id=-1,
                department_code=department_code,
                course_id=-1,
                course_number=course_number,
                course_name=course_name,
                course_description=course_description,
                course_units=course_units,
                raw_prerequisites_string=raw_prerequisites_string,
                prerequisite_codes=prerequisite_codes,
                is_active=True,
                last_scraped=datetime.datetime.now(),
            )

        except Exception as e:
            # Best effort: try to pull an h1 for identification before giving up.
            identifier = department_code
            try:
                h1 = BeautifulSoup(html, "lxml").find("h1")
                if h1:
                    identifier = f"{department_code} (h1: {h1.get_text(' ').strip()!r})"
            except Exception:
                pass
            logging.warning(
                f"{identifier}: parse failed with unexpected error — "
                f"{type(e).__name__}: {e}",
                exc_info=True,
            )
            return None

    def parse_prerequisites(self, raw_prerequisite_string: str) -> frozenset[str]:
        """
        Extract course codes from a raw prerequisite string.
        Returns a frozenset of course code strings e.g. {"CS2420", "MATH2270"}.
        Non-course requirements like 'instructor consent' are discarded.

        Bare course numbers chained with "OR" onto a preceding department-
        qualified course (e.g. "MATH 1050 OR 1060 OR 1080") inherit that
        department, since the catalog doesn't repeat the prefix for each
        alternative.
        """
        codes = set()
        last_department = None
        for dept, number, bare_number in PREREQUISITE_CODE_RE.findall(raw_prerequisite_string):
            if dept:
                last_department = dept
                codes.add(f"{dept}{number}")
            elif last_department:
                codes.add(f"{last_department}{bare_number}")
        return frozenset(codes)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_card_body(self, soup: BeautifulSoup, header_text: str):
        """Find the card-body div belonging to a card with a matching header."""
        for card in soup.find_all("div", class_="card"):
            header = card.find("div", class_="card-header")
            if header and header_text.lower() in header.get_text().lower():
                return card.find("div", class_="card-body")
        return None