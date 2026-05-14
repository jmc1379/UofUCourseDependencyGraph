import dataclasses
import datetime
import pytest

from src.graph.CourseGraph import CourseGraph
from src.graph.GraphAnalyzer import GraphAnalyzer
from src.models.Course import Course
from src.storage.CacheManager import CacheManager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_course(
    department_code: str,
    course_number: str,
    name: str = "Test Course",
    prerequisite_codes: frozenset[str] = frozenset(),
) -> Course:
    return Course(
        department_id=-1,
        department_code=department_code,
        course_id=-1,
        course_number=course_number,
        course_name=name,
        course_description=f"{name} description.",
        course_units=3.0,
        raw_prerequisites_string="",
        prerequisite_codes=prerequisite_codes,
        is_active=True,
        last_scraped=datetime.datetime(2025, 1, 1, 12, 0, 0),
    )


def populate(cache: CacheManager, courses: list[Course]):
    inserted = {}
    for course in courses:
        result = cache.insert_course(course)
        inserted[result.course_code] = result

    for course_code, course in inserted.items():
        original = next(c for c in courses if c.course_code == course_code)
        if original.prerequisite_codes:
            with_codes = dataclasses.replace(course, prerequisite_codes=original.prerequisite_codes)
            cache.insert_prerequisites(with_codes)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cache():
    with CacheManager(db_path=":memory:") as cm:
        yield cm


@pytest.fixture
def empty_analyzer(cache):
    """Analyzer over an empty graph."""
    return GraphAnalyzer(CourseGraph(cache))


@pytest.fixture
def linear_analyzer(cache):
    """
    Linear chain:
    CS1400 → CS2420 → CS3500 → CS4400
    """
    populate(cache, [
        make_course("CS", "1400"),
        make_course("CS", "2420", prerequisite_codes=frozenset({"CS1400"})),
        make_course("CS", "3500", prerequisite_codes=frozenset({"CS2420"})),
        make_course("CS", "4400", prerequisite_codes=frozenset({"CS3500"})),
    ])
    return GraphAnalyzer(CourseGraph(cache))


@pytest.fixture
def branching_analyzer(cache):
    """
    Branching structure:
    CS1400 → CS2420 → CS3500
    CS1410 → CS2420
    MATH2270 → CS3500
    Orphan: PHYS1010
    """
    populate(cache, [
        make_course("CS", "1400"),
        make_course("CS", "1410"),
        make_course("MATH", "2270"),
        make_course("CS", "2420", prerequisite_codes=frozenset({"CS1400", "CS1410"})),
        make_course("CS", "3500", prerequisite_codes=frozenset({"CS2420", "MATH2270"})),
        make_course("PHYS", "1010"),
    ])
    return GraphAnalyzer(CourseGraph(cache))


# ─── get_all_prerequisites ────────────────────────────────────────────────────

class TestGetAllPrerequisites:

    def test_leaf_has_no_prereqs(self, linear_analyzer):
        assert linear_analyzer.get_all_prerequisites("CS1400") == set()

    def test_terminal_has_all_prereqs(self, linear_analyzer):
        result = linear_analyzer.get_all_prerequisites("CS4400")
        assert result == {"CS1400", "CS2420", "CS3500"}

    def test_includes_transitive(self, linear_analyzer):
        """CS3500's prereqs should include CS1400, two hops back."""
        result = linear_analyzer.get_all_prerequisites("CS3500")
        assert "CS1400" in result

    def test_missing_course_returns_empty(self, linear_analyzer):
        assert linear_analyzer.get_all_prerequisites("CS9999") == set()

    def test_branching_collects_all_chains(self, branching_analyzer):
        result = branching_analyzer.get_all_prerequisites("CS3500")
        assert result == {"CS1400", "CS1410", "CS2420", "MATH2270"}


# ─── get_all_dependents ───────────────────────────────────────────────────────

class TestGetAllDependents:

    def test_terminal_has_no_dependents(self, linear_analyzer):
        assert linear_analyzer.get_all_dependents("CS4400") == set()

    def test_leaf_has_all_dependents(self, linear_analyzer):
        result = linear_analyzer.get_all_dependents("CS1400")
        assert result == {"CS2420", "CS3500", "CS4400"}

    def test_missing_course_returns_empty(self, linear_analyzer):
        assert linear_analyzer.get_all_dependents("CS9999") == set()


# ─── Depth ────────────────────────────────────────────────────────────────────

class TestDepth:

    def test_leaf_depth_is_zero(self, linear_analyzer):
        assert linear_analyzer.get_prerequisite_depth("CS1400") == 0

    def test_depth_increases_along_chain(self, linear_analyzer):
        assert linear_analyzer.get_prerequisite_depth("CS2420") == 1
        assert linear_analyzer.get_prerequisite_depth("CS3500") == 2
        assert linear_analyzer.get_prerequisite_depth("CS4400") == 3

    def test_missing_course_returns_none(self, linear_analyzer):
        assert linear_analyzer.get_prerequisite_depth("CS9999") is None

    def test_branching_depth_picks_longest(self, branching_analyzer):
        """CS3500 has two paths — through CS2420 (depth 2) or directly via MATH2270 (depth 1).
        Depth should be the longest: 2."""
        assert branching_analyzer.get_prerequisite_depth("CS3500") == 2

    def test_get_courses_at_depth(self, linear_analyzer):
        assert linear_analyzer.get_courses_at_depth(0) == {"CS1400"}
        assert linear_analyzer.get_courses_at_depth(2) == {"CS3500"}

    def test_get_max_depth(self, linear_analyzer):
        assert linear_analyzer.get_max_depth() == 3

    def test_get_max_depth_empty_graph(self, empty_analyzer):
        assert empty_analyzer.get_max_depth() == 0


# ─── Chains ───────────────────────────────────────────────────────────────────

class TestChains:

    def test_shortest_chain_linear(self, linear_analyzer):
        result = linear_analyzer.get_shortest_prerequisite_chains("CS4400")
        assert result == [["CS1400", "CS2420", "CS3500", "CS4400"]]

    def test_shortest_chain_for_leaf(self, linear_analyzer):
        """A leaf has only itself in its chain — length 1."""
        result = linear_analyzer.get_shortest_prerequisite_chains("CS1400")
        assert result == [["CS1400"]]

    def test_shortest_chain_missing_course(self, linear_analyzer):
        assert linear_analyzer.get_shortest_prerequisite_chains("CS9999") == []

    def test_shortest_chain_branching(self, branching_analyzer):
        """CS3500 has shortest chain MATH2270 → CS3500 (length 2)."""
        result = branching_analyzer.get_shortest_prerequisite_chains("CS3500")
        assert len(result) == 1
        assert result[0] == ["MATH2270", "CS3500"]

    def test_all_chains_linear(self, linear_analyzer):
        result = linear_analyzer.get_all_prerequisite_chains("CS4400")
        assert result == [["CS1400", "CS2420", "CS3500", "CS4400"]]

    def test_all_chains_branching(self, branching_analyzer):
        """CS3500 has three chains: via CS1400, via CS1410, and via MATH2270."""
        result = branching_analyzer.get_all_prerequisite_chains("CS3500")
        # Convert to set of tuples for order-independent comparison
        result_set = {tuple(chain) for chain in result}
        assert ("CS1400", "CS2420", "CS3500") in result_set
        assert ("CS1410", "CS2420", "CS3500") in result_set
        assert ("MATH2270", "CS3500") in result_set


# ─── Structural ───────────────────────────────────────────────────────────────

class TestStructural:

    def test_find_orphans_no_filter(self, branching_analyzer):
        """PHYS1010 has no prereqs and no dependents — it's an orphan."""
        result = branching_analyzer.find_orphan_courses()
        assert "PHYS1010" in result

    def test_find_orphans_excludes_leaves_with_dependents(self, branching_analyzer):
        """CS1400 has dependents (CS2420), so it's a leaf but not an orphan."""
        result = branching_analyzer.find_orphan_courses()
        assert "CS1400" not in result

    def test_find_orphans_by_department(self, branching_analyzer):
        result = branching_analyzer.find_orphan_courses(department_code="PHYS")
        assert result == {"PHYS1010"}

    def test_find_orphans_empty_for_unknown_department(self, branching_analyzer):
        result = branching_analyzer.find_orphan_courses(department_code="ECE")
        assert result == set()

    def test_detect_cycles_returns_false_for_dag(self, linear_analyzer):
        assert linear_analyzer.detect_cycles() is False

    def test_detect_cycles_empty_graph(self, empty_analyzer):
        assert empty_analyzer.detect_cycles() is False

    def test_topological_sort_returns_valid_order(self, linear_analyzer):
        order = linear_analyzer.topological_sort()
        # CS1400 must come before CS2420, etc.
        assert order.index("CS1400") < order.index("CS2420")
        assert order.index("CS2420") < order.index("CS3500")
        assert order.index("CS3500") < order.index("CS4400")

    def test_topological_sort_includes_all_nodes(self, branching_analyzer):
        order = branching_analyzer.topological_sort()
        assert len(order) == 6


# ─── Centrality ───────────────────────────────────────────────────────────────

class TestCentrality:

    def test_centrality_scores_returns_dict(self, linear_analyzer):
        result = linear_analyzer.get_centrality_scores()
        assert isinstance(result, dict)

    def test_centrality_scores_contain_all_courses(self, linear_analyzer):
        result = linear_analyzer.get_centrality_scores()
        assert set(result.keys()) == {"CS1400", "CS2420", "CS3500", "CS4400"}

    def test_centrality_scores_sum_to_approximately_one(self, linear_analyzer):
        """PageRank scores form a probability distribution."""
        result = linear_analyzer.get_centrality_scores()
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_course_centrality_score_returns_float(self, linear_analyzer):
        score = linear_analyzer.get_course_centrality_score("CS1400")
        assert isinstance(score, float)

    def test_course_centrality_score_returns_none_for_missing(self, linear_analyzer):
        assert linear_analyzer.get_course_centrality_score("CS9999") is None

    def test_empty_graph_has_empty_centrality(self, empty_analyzer):
        assert empty_analyzer.get_centrality_scores() == {}


# ─── Empty graph behavior ─────────────────────────────────────────────────────

class TestEmptyGraph:

    def test_empty_get_all_prerequisites(self, empty_analyzer):
        assert empty_analyzer.get_all_prerequisites("CS1400") == set()

    def test_empty_get_all_dependents(self, empty_analyzer):
        assert empty_analyzer.get_all_dependents("CS1400") == set()

    def test_empty_get_courses_at_depth(self, empty_analyzer):
        assert empty_analyzer.get_courses_at_depth(0) == set()

    def test_empty_topological_sort(self, empty_analyzer):
        assert empty_analyzer.topological_sort() == []

    def test_empty_find_orphans(self, empty_analyzer):
        assert empty_analyzer.find_orphan_courses() == set()

    def test_empty_get_shortest_chains(self, empty_analyzer):
        assert empty_analyzer.get_shortest_prerequisite_chains("CS1400") == []

    def test_empty_get_all_chains(self, empty_analyzer):
        assert empty_analyzer.get_all_prerequisite_chains("CS1400") == []