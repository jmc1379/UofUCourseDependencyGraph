import datetime
import pytest

from src.graph.CourseGraph import CourseGraph
from src.models.Course import Course
from src.storage.CacheManager import CacheManager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_course(
    department_code: str,
    course_number: str,
    name: str = "Test Course",
    units: float = 3.0,
    prerequisite_codes: frozenset[str] = frozenset(),
) -> Course:
    """Build a Course with placeholder IDs and sensible defaults."""
    return Course(
        department_id=-1,
        department_code=department_code,
        course_id=-1,
        course_number=course_number,
        course_name=name,
        course_description=f"{name} description.",
        course_units=units,
        raw_prerequisites_string="",
        prerequisite_codes=prerequisite_codes,
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


def populate(cache: CacheManager, courses: list[Course]) -> dict[str, Course]:
    """
    Run the two-pass insertion against the cache.
    Returns a dict mapping course_code to the inserted Course (with real IDs).
    """
    inserted = {}
    # Pass 1 — insert all courses
    for course in courses:
        result = cache.insert_course(course)
        inserted[result.course_code] = result

    # Pass 2 — link prerequisites
    for course_code, course in inserted.items():
        original = next(c for c in courses if c.course_code == course_code)
        if original.prerequisite_codes:
            import dataclasses
            with_codes = dataclasses.replace(course, prerequisite_codes=original.prerequisite_codes)
            cache.insert_prerequisites(with_codes)

    return inserted


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cache():
    """A fresh in-memory CacheManager for each test."""
    with CacheManager(db_path=":memory:") as cm:
        yield cm


@pytest.fixture
def empty_graph(cache):
    """A CourseGraph built against an empty database."""
    return CourseGraph(cache)


@pytest.fixture
def single_course_graph(cache):
    """A graph with one course and no prerequisites."""
    populate(cache, [make_course("CS", "1400", "Intro to Programming")])
    return CourseGraph(cache)


@pytest.fixture
def linear_chain_graph(cache):
    """
    A graph with three courses forming a linear chain:
    CS1400 → CS2420 → CS3500
    """
    courses = [
        make_course("CS", "1400", "Intro to Programming"),
        make_course("CS", "2420", "Algorithms", prerequisite_codes=frozenset({"CS1400"})),
        make_course("CS", "3500", "Software Practice", prerequisite_codes=frozenset({"CS2420"})),
    ]
    populate(cache, courses)
    return CourseGraph(cache)


@pytest.fixture
def multi_department_graph(cache):
    """
    A graph with courses from multiple departments and cross-department prereqs.
    CS3500 requires MATH2270
    """
    courses = [
        make_course("MATH", "2270", "Linear Algebra"),
        make_course("CS", "3500", "Software Practice", prerequisite_codes=frozenset({"MATH2270"})),
        make_course("CS", "1400", "Intro to Programming"),
    ]
    populate(cache, courses)
    return CourseGraph(cache)


# ─── Initialization ───────────────────────────────────────────────────────────

class TestInitialization:

    def test_empty_graph_has_no_courses(self, empty_graph):
        assert empty_graph.course_count == 0

    def test_empty_graph_has_no_edges(self, empty_graph):
        assert empty_graph.edge_count == 0

    def test_single_course_graph_has_one_node(self, single_course_graph):
        assert single_course_graph.course_count == 1

    def test_single_course_graph_has_no_edges(self, single_course_graph):
        assert single_course_graph.edge_count == 0

    def test_chain_graph_node_count(self, linear_chain_graph):
        assert linear_chain_graph.course_count == 3

    def test_chain_graph_edge_count(self, linear_chain_graph):
        assert linear_chain_graph.edge_count == 2


# ─── has_course / get_course ──────────────────────────────────────────────────

class TestCourseAccess:

    def test_has_course_returns_true_for_existing(self, single_course_graph):
        assert single_course_graph.has_course("CS1400") is True

    def test_has_course_returns_false_for_missing(self, single_course_graph):
        assert single_course_graph.has_course("CS9999") is False

    def test_get_course_returns_course_object(self, single_course_graph):
        course = single_course_graph.get_course("CS1400")
        assert isinstance(course, Course)
        assert course.course_number == "1400"
        assert course.course_name == "Intro to Programming"

    def test_get_course_returns_none_for_missing(self, single_course_graph):
        assert single_course_graph.get_course("CS9999") is None

    def test_get_course_preserves_full_data(self, single_course_graph):
        course = single_course_graph.get_course("CS1400")
        assert course.department_code == "CS"
        assert course.course_units == 3.0
        assert course.is_active is True

    def test_course_prerequisite_codes_is_frozenset(self, linear_chain_graph):
        """Verify prerequisite_codes is stored as frozenset (immutable)."""
        course = linear_chain_graph.get_course("CS2420")
        assert isinstance(course.prerequisite_codes, frozenset)


# ─── get_direct_prerequisites ─────────────────────────────────────────────────

class TestDirectPrerequisites:

    def test_returns_empty_set_for_course_with_no_prereqs(self, linear_chain_graph):
        result = linear_chain_graph.get_direct_prerequisites("CS1400")
        assert result == set()

    def test_returns_single_prereq(self, linear_chain_graph):
        result = linear_chain_graph.get_direct_prerequisites("CS2420")
        assert result == {"CS1400"}

    def test_returns_only_direct_not_transitive(self, linear_chain_graph):
        """CS3500 → CS2420 → CS1400. Direct prereqs of CS3500 should be {CS2420}, not {CS2420, CS1400}."""
        result = linear_chain_graph.get_direct_prerequisites("CS3500")
        assert result == {"CS2420"}
        assert "CS1400" not in result

    def test_returns_none_for_missing_course(self, linear_chain_graph):
        result = linear_chain_graph.get_direct_prerequisites("CS9999")
        assert result is None

    def test_handles_cross_department_prereq(self, multi_department_graph):
        result = multi_department_graph.get_direct_prerequisites("CS3500")
        assert result == {"MATH2270"}


# ─── get_direct_dependents ────────────────────────────────────────────────────

class TestDirectDependents:

    def test_returns_empty_set_for_terminal_course(self, linear_chain_graph):
        """CS3500 has no courses depending on it."""
        result = linear_chain_graph.get_direct_dependents("CS3500")
        assert result == set()

    def test_returns_single_dependent(self, linear_chain_graph):
        result = linear_chain_graph.get_direct_dependents("CS1400")
        assert result == {"CS2420"}

    def test_returns_only_direct_not_transitive(self, linear_chain_graph):
        """CS1400 unlocks CS2420 directly. CS3500 is two hops away."""
        result = linear_chain_graph.get_direct_dependents("CS1400")
        assert "CS3500" not in result

    def test_returns_none_for_missing_course(self, linear_chain_graph):
        result = linear_chain_graph.get_direct_dependents("CS9999")
        assert result is None

    def test_cross_department_dependent(self, multi_department_graph):
        result = multi_department_graph.get_direct_dependents("MATH2270")
        assert result == {"CS3500"}


# ─── search_by_name ───────────────────────────────────────────────────────────

class TestSearchByName:

    def test_empty_query_matches_all(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("")
        assert len(result) == 3

    def test_exact_match(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("Software Practice")
        assert len(result) == 1
        assert next(iter(result)).course_number == "3500"

    def test_substring_match(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("Software")
        assert len(result) == 1

    def test_case_insensitive(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("SOFTWARE")
        assert len(result) == 1

    def test_no_match_returns_empty(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("Quantum Physics")
        assert result == set()

    def test_returns_course_objects(self, linear_chain_graph):
        result = linear_chain_graph.search_by_name("Intro")
        assert all(isinstance(c, Course) for c in result)


# ─── get_all_courses ──────────────────────────────────────────────────────────

class TestGetAllCourses:

    def test_empty_graph_returns_empty_set(self, empty_graph):
        assert empty_graph.get_all_courses() == set()

    def test_returns_all_courses_in_graph(self, linear_chain_graph):
        result = linear_chain_graph.get_all_courses()
        assert len(result) == 3

    def test_returns_course_objects(self, linear_chain_graph):
        result = linear_chain_graph.get_all_courses()
        assert all(isinstance(c, Course) for c in result)

    def test_courses_are_hashable(self, linear_chain_graph):
        """A frozen dataclass with frozenset fields should be hashable."""
        result = linear_chain_graph.get_all_courses()
        # If Course isn't hashable this conversion would raise.
        as_set = set(result)
        assert len(as_set) == 3


# ─── get_courses_by_department ────────────────────────────────────────────────

class TestGetCoursesByDepartment:

    def test_returns_only_matching_department(self, multi_department_graph):
        result = multi_department_graph.get_courses_by_department("CS")
        assert all(c.department_code == "CS" for c in result)

    def test_returns_correct_count(self, multi_department_graph):
        cs_courses   = multi_department_graph.get_courses_by_department("CS")
        math_courses = multi_department_graph.get_courses_by_department("MATH")
        assert len(cs_courses) == 2
        assert len(math_courses) == 1

    def test_lowercase_query_uppercased(self, multi_department_graph):
        """Method does .upper() so lowercase queries should also work."""
        result = multi_department_graph.get_courses_by_department("cs")
        assert len(result) == 2

    def test_missing_department_returns_empty(self, multi_department_graph):
        result = multi_department_graph.get_courses_by_department("PHYS")
        assert result == set()

    def test_substring_does_not_match(self, multi_department_graph):
        """'C' should not match 'CS' — query is exact match."""
        result = multi_department_graph.get_courses_by_department("C")
        assert result == set()


# ─── get_departments ──────────────────────────────────────────────────────────

class TestGetDepartments:

    def test_empty_graph_has_no_departments(self, empty_graph):
        assert empty_graph.get_departments() == set()

    def test_single_department(self, linear_chain_graph):
        assert linear_chain_graph.get_departments() == {"CS"}

    def test_multiple_departments(self, multi_department_graph):
        assert multi_department_graph.get_departments() == {"CS", "MATH"}

    def test_no_duplicates(self, linear_chain_graph):
        """Three CS courses should yield a single 'CS' entry."""
        assert len(linear_chain_graph.get_departments()) == 1