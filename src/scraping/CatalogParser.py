import re
from abc import ABC, abstractmethod

from src.models.Course import Course

# Matches department codes followed by a course number e.g. "CS 3500", "MATH 2270"
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,})\s+(\d{4}[A-Z]?)\b")


class CatalogParser(ABC):

    @abstractmethod
    def get_course_list(self, html: str) -> list[str]:
        """
        Parse a department listing page and return a list of course numbers.
        e.g. ["1400", "1410", "2420", ...]
        """
        pass

    @abstractmethod
    def parse_course_detail(self, html: str, department_code: str) -> Course | None:
        """
        Parse a course detail page and return a Course with placeholder IDs.
        Returns None if the page cannot be parsed.
        """
        pass

    @abstractmethod
    def parse_prerequisites(self, raw_prerequisite_string: str) -> set[str]:
        """
        Parse a raw prerequisite string and return a set of course codes.
        e.g. "Prerequisites: CS 2420 AND MATH 2270" -> {"CS2420", "MATH2270"}
        Non-course requirements like 'instructor consent' are discarded.
        """
        pass