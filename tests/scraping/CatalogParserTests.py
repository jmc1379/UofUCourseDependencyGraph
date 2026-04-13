from pathlib import Path

import pytest

from src.models.Course import Course
from src.scraping.UofUCatalogParser import UofUCatalogParser

# ─── Fixture loading ──────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def parser():
    return UofUCatalogParser()


@pytest.fixture
def course_list_html():
    return load_fixture("cs_course_list.html")


@pytest.fixture
def cs_1400_html():
    return load_fixture("cs_1400_detail.html")


@pytest.fixture
def cs_3500_html():
    return load_fixture("cs_3500_detail.html")


@pytest.fixture
def cs_4400_html():
    return load_fixture("cs_4400_detail.html")


@pytest.fixture
def cs_6961_html():
    return load_fixture("cs_6961_detail.html")


# ─── get_course_list ──────────────────────────────────────────────────────────

class TestGetCourseList:

    def test_returns_a_list(self, parser, course_list_html):
        result = parser.get_course_list(course_list_html)
        assert isinstance(result, list)

    def test_returns_strings(self, parser, course_list_html):
        result = parser.get_course_list(course_list_html)
        assert all(isinstance(n, str) for n in result)

    def test_contains_known_courses(self, parser, course_list_html):
        result = parser.get_course_list(course_list_html)
        assert "1400" in result
        assert "3500" in result
        assert "4400" in result
        assert "6961" in result

    def test_results_are_sorted_numerically(self, parser, course_list_html):
        result = parser.get_course_list(course_list_html)
        numeric = [int(n.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")) for n in result]
        assert numeric == sorted(numeric)

    def test_no_duplicates(self, parser, course_list_html):
        result = parser.get_course_list(course_list_html)
        assert len(result) == len(set(result))

    def test_returns_empty_list_for_empty_html(self, parser):
        result = parser.get_course_list("<html><body></body></html>")
        assert result == []


# ─── parse_course_detail — CS 1400 (no CS prereqs, MATH prereqs) ─────────────

class TestParseCourseDetailCS1400:

    def test_returns_course_object(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert isinstance(result, Course)

    def test_course_number(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.course_number == "1400"

    def test_course_name(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.course_name == "Introduction to Computer Programming"

    def test_course_units(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.course_units == 4.0

    def test_department_code(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.department_code == "CS"

    def test_placeholder_ids(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.course_id == -1
        assert result.department_id == -1

    def test_prereq_string_captured(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert "MATH" in result.raw_prerequisites_string

    def test_math_prereq_extracted(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert "MATH1050" in result.prerequisite_codes

    def test_description_not_empty(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert len(result.course_description) > 0

    def test_description_content(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert "programming" in result.course_description.lower()

    def test_is_active(self, parser, cs_1400_html):
        result = parser.parse_course_detail(cs_1400_html, "CS")
        assert result.is_active is True


# ─── parse_course_detail — CS 3500 (policy-only prereqs, no course codes) ────

class TestParseCourseDetailCS3500:

    def test_course_number(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert result.course_number == "3500"

    def test_course_name(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert result.course_name == "Software Practice"

    def test_course_units(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert result.course_units == 4.0

    def test_no_prerequisite_codes_extracted(self, parser, cs_3500_html):
        """Policy-only prerequisites should yield an empty set of codes."""
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert result.prerequisite_codes == set(str)

    def test_prereq_string_captured(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert "Foundational Courses" in result.raw_prerequisites_string

    def test_description_not_empty(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert len(result.course_description) > 0

    def test_description_content(self, parser, cs_3500_html):
        result = parser.parse_course_detail(cs_3500_html, "CS")
        assert "software" in result.course_description.lower()


# ─── parse_course_detail — CS 4400 (has CS course prereq) ────────────────────

class TestParseCourseDetailCS4400:

    def test_course_number(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert result.course_number == "4400"

    def test_course_name(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert result.course_name == "Computer Systems"

    def test_course_units(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert result.course_units == 3.0

    def test_cs_prereq_extracted(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert "CS3810" in result.prerequisite_codes

    def test_policy_not_extracted_as_prereq(self, parser, cs_4400_html):
        """'Kahlert School of Computing' should not appear as a course code."""
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert not any("Kahlert" in code for code in result.prerequisite_codes)

    def test_description_not_empty(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert len(result.course_description) > 0

    def test_description_content(self, parser, cs_4400_html):
        result = parser.parse_course_detail(cs_4400_html, "CS")
        assert "programmer" in result.course_description.lower()


# ─── parse_course_detail — CS 6961 (empty description, grad level) ───────────

class TestParseCourseDetailCS6961:

    def test_course_number(self, parser, cs_6961_html):
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert result.course_number == "6961"

    def test_course_name(self, parser, cs_6961_html):
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert result.course_name == "Special Topics"

    def test_course_units(self, parser, cs_6961_html):
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert result.course_units == 3.0

    def test_empty_description(self, parser, cs_6961_html):
        """CS 6961 has no description text — should return empty string not footer content."""
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert result.course_description == ""

    def test_no_prerequisite_codes(self, parser, cs_6961_html):
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert result.prerequisite_codes == set()

    def test_prereq_string_captured(self, parser, cs_6961_html):
        result = parser.parse_course_detail(cs_6961_html, "CS")
        assert "Major status" in result.raw_prerequisites_string


# ─── parse_course_detail — edge cases ────────────────────────────────────────

class TestParseCourseDetailEdgeCases:

    def test_returns_none_for_empty_html(self, parser):
        result = parser.parse_course_detail("<html><body></body></html>", "CS")
        assert result is None

    def test_returns_none_for_malformed_html(self, parser):
        result = parser.parse_course_detail("<html><body><h1>bad</h1></body></html>", "CS")
        assert result is None


# ─── parse_prerequisites ──────────────────────────────────────────────────────

class TestParsePrerequisites:

    def test_empty_string_returns_empty_set(self, parser):
        assert parser.parse_prerequisites("") == set()

    def test_policy_only_returns_empty_set(self, parser):
        result = parser.parse_prerequisites(
            "Prerequisites: Foundational Courses complete AND Major status required"
        )
        assert result == set()

    def test_single_cs_course_extracted(self, parser):
        result = parser.parse_prerequisites("Prerequisites: CS 3810")
        assert result == {"CS3810"}

    def test_multiple_cs_courses_extracted(self, parser):
        result = parser.parse_prerequisites("Prerequisites: CS 2420 AND CS 2100")
        assert result == {"CS2420", "CS2100"}

    def test_cross_department_courses_extracted(self, parser):
        result = parser.parse_prerequisites(
            "Prerequisites: CS 3810 AND MATH 2270"
        )
        assert "CS3810" in result
        assert "MATH2270" in result

    def test_policy_mixed_with_courses_discards_policy(self, parser):
        result = parser.parse_prerequisites(
            "Prerequisites: 'C-' or better in CS 3810 AND Foundational Courses complete "
            "AND (Major OR Minor in Kahlert School of Computing OR ECE)"
        )
        assert result == {"CS3810"}

    def test_instructor_consent_discarded(self, parser):
        result = parser.parse_prerequisites(
            "Prerequisites: CS 2420 AND instructor consent required"
        )
        assert result == {"CS2420"}

    def test_returns_set_not_list(self, parser):
        result = parser.parse_prerequisites("Prerequisites: CS 2420")
        assert isinstance(result, set)

    def test_duplicate_courses_deduplicated(self, parser):
        result = parser.parse_prerequisites(
            "Prerequisites: CS 2420 AND CS 2420"
        )
        assert result == {"CS2420"}

    def test_real_cs_4400_prereq_string(self, parser):
        prereq = (
            "Prerequisites: 'C-' or better in CS 3810 AND Foundational Courses complete "
            "AND (Major OR Minor in Kahlert School of Computing OR ECE)"
        )
        assert parser.parse_prerequisites(prereq) == {"CS3810"}

    def test_real_cs_1400_prereq_string(self, parser):
        prereq = (
            "Prerequisites: AP CalcAB score of 3+ OR AP CalcBC score of 3+ OR "
            "Corerequisites: 'C' or better in MATH 1050 OR 1060 OR 1080 OR 1210 OR "
            "1215 OR 1250 OR 1310 OR 1311 OR Higher Math"
        )
        result = parser.parse_prerequisites(prereq)
        # Only "MATH 1050" is a fully qualified code — the rest lack a department prefix
        assert "MATH1050" in result