import datetime
import pytest

from src.models.Course import Course
from src.storage.CacheManager import CacheManager


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cache():
    """Provide a fresh in-memory CacheManager for each test."""
    with CacheManager(db_path=":memory:") as cache_manager:
        yield cache_manager


@pytest.fixture
def sample_course():
    """A valid Course with placeholder IDs for insertion."""
    return Course(
        department_id=-1,
        department_code="CS",
        course_id=-1,
        course_number="3500",
        course_name="Software Practice",
        course_description="Practical exposure to creating large software systems.",
        course_units=4.0,
        raw_prerequisites_string="Prerequisites: CS 2420",
        prerequisites_codes=set(),
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def prerequisite_course():
    """A course that will be used as a prerequisite for another course."""
    return Course(
        department_id=-1,
        department_code="CS",
        course_id=-1,
        course_number="2420",
        course_name="Algorithms and Data Structures",
        course_description="Introduction to algorithms and data structures.",
        course_units=4.0,
        raw_prerequisites_string="",
        prerequisites_codes=set(),
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def math_course():
    """A course in a different department."""
    return Course(
        department_id=-1,
        department_code="MATH",
        course_id=-1,
        course_number="2270",
        course_name="Linear Algebra",
        course_description="Vectors, matrices, and linear transformations.",
        course_units=3.0,
        raw_prerequisites_string="",
        prerequisites_codes=set(),
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def inserted_course(cache, sample_course):
    """A course that has already been inserted into the database."""
    return cache.insert_course(sample_course)


@pytest.fixture
def inserted_prereq(cache, prerequisite_course):
    """A prerequisite course already inserted into the database."""
    return cache.insert_course(prerequisite_course)


# ─── Initialization ───────────────────────────────────────────────────────────

class TestInitialization:

    def test_cache_manager_initializes(self, cache):
        assert cache is not None

    def test_tables_created_on_init(self, cache):
        cache.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cache.cursor.fetchall()}
        assert "departments" in tables
        assert "courses" in tables
        assert "prerequisites" in tables

    def test_foreign_keys_enabled(self, cache):
        cache.cursor.execute("PRAGMA foreign_keys")
        result = cache.cursor.fetchone()
        assert result[0] == 1


# ─── Context Manager ──────────────────────────────────────────────────────────

class TestContextManager:

    def test_context_manager_closes_connection(self):
        with CacheManager(db_path=":memory:") as cm:
            assert cm.connection is not None
        # After exiting, executing should raise
        with pytest.raises(Exception):
            cm.cursor.execute("SELECT 1")


# ─── Department Methods ───────────────────────────────────────────────────────

class TestDepartmentMethods:

    def test_get_department_by_code_returns_none_when_missing(self, cache):
        result = cache.get_department_by_code("CS")
        assert result is None

    def test_get_department_by_code_after_course_insert(self, cache, inserted_course):
        result = cache.get_department_by_code("CS")
        assert result is not None
        assert result["department_code"] == "CS"

    def test_get_all_departments_empty(self, cache):
        assert cache.get_all_departments() == []

    def test_get_all_departments_returns_all(self, cache, sample_course, math_course):
        cache.insert_course(sample_course)
        cache.insert_course(math_course)
        departments = cache.get_all_departments()
        codes = {d["department_code"] for d in departments}
        assert "CS" in codes
        assert "MATH" in codes

    def test_inserting_same_department_twice_does_not_duplicate(self, cache, sample_course, prerequisite_course):
        cache.insert_course(sample_course)
        cache.insert_course(prerequisite_course)
        departments = cache.get_all_departments()
        cs_departments = [d for d in departments if d["department_code"] == "CS"]
        assert len(cs_departments) == 1


# ─── Course Insert ────────────────────────────────────────────────────────────

class TestInsertCourse:

    def test_insert_course_returns_course(self, cache, sample_course):
        result = cache.insert_course(sample_course)
        assert isinstance(result, Course)

    def test_insert_course_assigns_real_course_id(self, cache, sample_course):
        result = cache.insert_course(sample_course)
        assert result.course_id > 0

    def test_insert_course_assigns_real_department_id(self, cache, sample_course):
        result = cache.insert_course(sample_course)
        assert result.department_id > 0

    def test_insert_course_preserves_fields(self, cache, sample_course):
        result = cache.insert_course(sample_course)
        assert result.course_number == "3500"
        assert result.course_name == "Software Practice"
        assert result.course_units == 4.0
        assert result.is_active is True

    def test_insert_course_with_prerequisites(self, cache, prerequisite_course, sample_course):
        inserted_prereq = cache.insert_course(prerequisite_course)
        course_with_prereq = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="Prerequisites: CS 2420",
            prerequisites_codes={inserted_prereq.course_id},
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        result = cache.insert_course(course_with_prereq)
        prereqs = cache.get_prerequisites_for_course(result.course_id)
        assert len(prereqs) == 1
        assert prereqs[0]["course_number"] == "2420"

    def test_insert_course_original_is_unchanged(self, cache, sample_course):
        """Original Course object should remain immutable after insert."""
        cache.insert_course(sample_course)
        assert sample_course.course_id == -1
        assert sample_course.department_id == -1


# ─── Course Read Methods ──────────────────────────────────────────────────────

class TestCourseReadMethods:

    def test_get_course_by_id_returns_correct_course(self, cache, inserted_course):
        result = cache.get_course_by_id(inserted_course.course_id)
        assert result is not None
        assert result["course_number"] == "3500"

    def test_get_course_by_id_returns_none_when_missing(self, cache):
        assert cache.get_course_by_id(9999) is None

    def test_get_course_by_code_returns_correct_course(self, cache, inserted_course):
        result = cache.get_course_by_code("CS", "3500")
        assert result is not None
        assert result["course_name"] == "Software Practice"

    def test_get_course_by_code_returns_none_when_missing(self, cache):
        assert cache.get_course_by_code("CS", "9999") is None

    def test_get_courses_by_department_returns_only_that_department(self, cache, sample_course, math_course):
        cache.insert_course(sample_course)
        cache.insert_course(math_course)
        cs_courses = cache.get_courses_by_department("CS")
        assert all(c["course_number"] != "2270" for c in cs_courses)

    def test_get_courses_by_department_empty_when_none(self, cache):
        assert cache.get_courses_by_department("CS") == []

    def test_get_all_courses_returns_all(self, cache, sample_course, math_course):
        cache.insert_course(sample_course)
        cache.insert_course(math_course)
        all_courses = cache.get_all_courses()
        assert len(all_courses) == 2

    def test_get_all_courses_empty(self, cache):
        assert cache.get_all_courses() == []


# ─── Prerequisite Methods ─────────────────────────────────────────────────────

class TestPrerequisiteMethods:

    def test_get_prerequisites_empty_when_none(self, cache, inserted_course):
        prereqs = cache.get_prerequisites_for_course(inserted_course.course_id)
        assert prereqs == []

    def test_get_dependents_empty_when_none(self, cache, inserted_course):
        dependents = cache.get_dependents_for_course(inserted_course.course_id)
        assert dependents == []

    def test_get_prerequisites_returns_correct_course(self, cache, inserted_prereq):
        course_with_prereq = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes={inserted_prereq.course_id},
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        inserted = cache.insert_course(course_with_prereq)
        prereqs = cache.get_prerequisites_for_course(inserted.course_id)
        assert len(prereqs) == 1
        assert prereqs[0]["course_number"] == "2420"

    def test_get_dependents_returns_correct_course(self, cache, inserted_prereq):
        course_with_prereq = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes={inserted_prereq.course_id},
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        cache.insert_course(course_with_prereq)
        dependents = cache.get_dependents_for_course(inserted_prereq.course_id)
        assert len(dependents) == 1
        assert dependents[0]["course_number"] == "3500"


# ─── Cache Utility Methods ────────────────────────────────────────────────────

class TestCacheUtilityMethods:

    def test_course_exists_returns_false_when_missing(self, cache):
        assert cache.course_exists("CS", "3500") is False

    def test_course_exists_returns_true_after_insert(self, cache, inserted_course):
        assert cache.course_exists("CS", "3500") is True

    def test_is_stale_returns_true_for_missing_course(self, cache):
        assert cache.is_stale(9999) is True

    def test_is_stale_returns_false_for_recently_scraped(self, cache, sample_course):
        fresh_course = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes=set(),
            is_active=True,
            last_scraped=datetime.datetime.now(),
        )
        inserted = cache.insert_course(fresh_course)
        assert cache.is_stale(inserted.course_id) is False

    def test_is_stale_returns_true_for_old_course(self, cache):
        old_course = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes=set(),
            is_active=True,
            last_scraped=datetime.datetime(2020, 1, 1),
        )
        inserted = cache.insert_course(old_course)
        assert cache.is_stale(inserted.course_id) is True

    def test_mark_scraped_updates_timestamp(self, cache):
        old_course = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes=set(),
            is_active=True,
            last_scraped=datetime.datetime(2020, 1, 1),
        )
        inserted = cache.insert_course(old_course)
        assert cache.is_stale(inserted.course_id) is True
        cache.mark_scraped(inserted.course_id)
        assert cache.is_stale(inserted.course_id) is False

    def test_clear_department_removes_courses(self, cache, sample_course):
        cache.insert_course(sample_course)
        assert len(cache.get_courses_by_department("CS")) == 1
        cache.clear_department("CS")
        assert len(cache.get_courses_by_department("CS")) == 0

    def test_clear_department_removes_prerequisites(self, cache, inserted_prereq):
        course_with_prereq = Course(
            department_id=-1,
            department_code="CS",
            course_id=-1,
            course_number="3500",
            course_name="Software Practice",
            course_description="",
            course_units=4.0,
            raw_prerequisites_string="",
            prerequisites_codes={inserted_prereq.course_id},
            is_active=True,
            last_scraped=datetime.datetime(2025, 1, 1),
        )
        cache.insert_course(course_with_prereq)
        cache.clear_department("CS")
        cache.cursor.execute("SELECT * FROM prerequisites")
        assert cache.cursor.fetchall() == []

    def test_clear_nonexistent_department_does_not_raise(self, cache):
        cache.clear_department("FAKE")