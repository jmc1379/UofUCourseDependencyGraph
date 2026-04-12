import datetime
import pytest
from src.models.Course import Course


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_course():
    """A fully populated, valid Course instance for reuse across tests."""
    return Course(
        department_id=1,
        department_code="CS",
        course_id=101,
        course_number="3500",
        course_name="Software Practice",
        course_description="Practical exposure to the process of creating large software systems.",
        course_units=4.0,
        raw_prerequisites_string="Prerequisites: CS 2420 AND CS 2100",
        prerequisites_ids={1, 2},
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def minimal_course():
    """A course with empty/minimal optional-style fields."""
    return Course(
        department_id=2,
        department_code="MATH",
        course_id=202,
        course_number="2270",
        course_name="Linear Algebra",
        course_description="",
        course_units=3.0,
        raw_prerequisites_string="",
        prerequisites_ids=set(),
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


# ─── Instantiation ────────────────────────────────────────────────────────────

class TestCourseInstantiation:

    def test_valid_course_creates_successfully(self, sample_course):
        assert sample_course is not None

    def test_all_fields_stored_correctly(self, sample_course):
        assert sample_course.department_id == 1
        assert sample_course.department_code == "CS"
        assert sample_course.course_id == 101
        assert sample_course.course_number == "3500"
        assert sample_course.course_name == "Software Practice"
        assert sample_course.course_units == 4.0
        assert sample_course.is_active is True
        assert sample_course.prerequisites_ids == {1, 2}

    def test_course_with_no_prerequisites(self, minimal_course):
        assert minimal_course.prerequisites_ids == set()
        assert minimal_course.raw_prerequisites_string == ""

    def test_course_with_float_units(self, sample_course):
        assert isinstance(sample_course.course_units, float)

    def test_last_scraped_is_datetime(self, sample_course):
        assert isinstance(sample_course.last_scraped, datetime.datetime)


# ─── Immutability ─────────────────────────────────────────────────────────────

class TestCourseImmutability:

    def test_cannot_set_course_name(self, sample_course):
        with pytest.raises(AttributeError):
            sample_course.course_name = "New Name"

    def test_cannot_set_department_code(self, sample_course):
        with pytest.raises(AttributeError):
            sample_course.department_code = "MATH"

    def test_cannot_set_prerequisites_ids(self, sample_course):
        with pytest.raises(AttributeError):
            sample_course.prerequisites_ids = {99}

    def test_cannot_set_is_active(self, sample_course):
        with pytest.raises(AttributeError):
            sample_course.is_active = False

    def test_cannot_set_course_id(self, sample_course):
        with pytest.raises(AttributeError):
            sample_course.course_id = 999


# ─── course_code property ─────────────────────────────────────────────────────

class TestCourseCode:

    def test_course_code_combines_department_and_number(self, sample_course):
        assert sample_course.course_code == "CS3500"

    def test_course_code_math_department(self, minimal_course):
        assert minimal_course.course_code == "MATH2270"

    def test_course_code_is_string(self, sample_course):
        assert isinstance(sample_course.course_code, str)

    def test_course_code_changes_with_department_code(self):
        course = Course(
            department_id=3,
            department_code="ECE",
            course_id=303,
            course_number="3500",
            course_name="Some ECE Course",
            course_description="",
            course_units=3.0,
            raw_prerequisites_string="",
            prerequisites_ids=set(),
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        assert course.course_code == "ECE3500"


# ─── Edge Cases ───────────────────────────────────────────────────────────────

class TestCourseEdgeCases:

    def test_prerequisites_ids_is_a_set(self, sample_course):
        assert isinstance(sample_course.prerequisites_ids, set)

    def test_prerequisites_ids_no_duplicates(self):
        """Sets inherently disallow duplicates — confirm behavior is as expected."""
        course = Course(
            department_id=1,
            department_code="CS",
            course_id=101,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_ids={1, 1, 2},  # duplicate 1
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        assert course.prerequisites_ids == {1, 2}

    def test_inactive_course(self):
        course = Course(
            department_id=1,
            department_code="CS",
            course_id=999,
            course_number="4999",
            course_name="Deprecated Course",
            course_description="",
            course_units=3.0,
            raw_prerequisites_string="",
            prerequisites_ids=set(),
            is_active=False,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        assert course.is_active is False

    def test_course_number_can_contain_letters(self):
        """Course numbers like '3500H' (honors) should be valid."""
        course = Course(
            department_id=1,
            department_code="CS",
            course_id=102,
            course_number="3500H",
            course_name="Software Practice Honors",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_ids=set(),
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        assert course.course_number == "3500H"
        assert course.course_code == "CS3500H"