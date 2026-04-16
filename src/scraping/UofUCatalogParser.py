import datetime
import logging
import re

from bs4 import BeautifulSoup
from numpy.matlib import empty

from src.models.Course import Course
from src.scraping.CatalogParser import CatalogParser, COURSE_CODE_RE

# Matches course numbers in U of U department list page links
# e.g. sections.html?subj=CS&catno=3500
COURSE_LIST_RE = re.compile(r"sections\.html\?subj=\w+&catno=(\d{4}[A-Z]?)")


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

    def parse_course_detail(self, html: str, department_code: str) -> Course | None:
        """
        Parse a U of U course detail page and return a Course with placeholder IDs.
        Returns None if required fields cannot be extracted.
        """
        try:
            soup = BeautifulSoup(html, "lxml")

            # ── Course name and number ────────────────────────────────────────
            h1 = soup.find("h1")
            if not h1:
                return None

            h1_text    = h1.get_text(" ")
            name_match = re.match(r"[A-Z]+\s+(\d{4}[A-Z]?)\s*[-–]?\s*(.*)", h1_text.strip())
            if not name_match:
                return None

            course_number = name_match.group(1).strip()
            course_name   = name_match.group(2).strip() or f"{department_code} {course_number}"

            # ── Units ─────────────────────────────────────────────────────────
            # Units live in the only <span class="col"> on the page
            units_span   = soup.find("span", class_="col")
            course_units = 0.0
            if units_span:
                try:
                    course_units = float(units_span.get_text(strip=True))
                except ValueError:
                    course_units = 0.0

            # ── Enrollment requirement ────────────────────────────────────────
            # Find the Enrollment Information card and extract the prereq span
            raw_prerequisites_string = ""
            enrollment_body = self._find_card_body(soup, "Enrollment Information")
            if enrollment_body:
                req_span = enrollment_body.find("span")
                if req_span:
                    raw_prerequisites_string = req_span.get_text(strip=True)

            # ── Description ───────────────────────────────────────────────────
            # Find the Description card and extract the text from the col div
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
            logging.warning(f"Failed to parse course detail for {department_code}: {e}")
            return None

    def parse_prerequisites(self, raw_prerequisite_string: str) -> set[str]:
        """
        Extract course codes from a raw prerequisite string.
        Returns a set of course code strings e.g. {"CS2420", "MATH2270"}.
        Non-course requirements like 'instructor consent' are discarded.
        """
        courses = set()

        # Match full patterns like "CS 2420" or "MATH 1210"
        pattern = re.findall(r'\b([A-Z]{2,4})\s*(\d{3,4})\b', raw_prerequisite_string)

        last_subject = None

        for subject, number in pattern:
            last_subject = subject
            courses.add(f"{subject}{number}")

        # Handle chained numbers like "MATH 1050 OR 1060 OR 1080"
        chain_pattern = re.findall(r'\b([A-Z]{2,4})\s*((?:\d{3,4}(?:\s*OR\s*)?)+)', raw_prerequisite_string)

        for subject, numbers_str in chain_pattern:
            numbers = re.findall(r'\d{3,4}', numbers_str)
            for num in numbers:
                courses.add(f"{subject}{num}")

        return courses

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_card_body(self, soup: BeautifulSoup, header_text: str):
        """Find the card-body div belonging to a card with a matching header."""
        for card in soup.find_all("div", class_="card"):
            header = card.find("div", class_="card-header")
            if header and header_text.lower() in header.get_text().lower():
                return card.find("div", class_="card-body")
        return None