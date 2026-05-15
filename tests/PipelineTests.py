from pathlib import Path

import pytest

from src.Pipeline import Pipeline
from src.scraping.UofUCatalogParser import UofUCatalogParser
from src.storage.CacheManager import CacheManager

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

TERM = "1258"


def load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


# ─── Persistent cache subclass ────────────────────────────────────────────────

class PersistentCacheManager(CacheManager):
    """
    CacheManager whose close() is a no-op, so the pipeline's `with` block
    doesn't tear down the connection mid-test. Tests close the cache
    explicitly during teardown.
    """

    def close(self):
        pass

    def real_close(self):
        # Use the actual sqlite close when teardown is ready.
        if self.connection:
            self.connection.close()
            self.connection = None


# ─── Mock fetcher ─────────────────────────────────────────────────────────────

class MockFetcher:
    """
    Async context-manageable fetcher whose responses are controlled by the test.

    - `list_html`: HTML returned for fetch_department_list, keyed by department
    - `course_html`: HTML returned for fetch_course, keyed by (dept, number, section)
    - `sections_html`: HTML returned for fetch_sections, keyed by (dept, number)

    Returns None when no entry is configured so the pipeline sees a fetch failure.
    """

    def __init__(self):
        self.list_html:     dict[str, str | None]                  = {}
        self.course_html:   dict[tuple[str, str, str], str | None] = {}
        self.sections_html: dict[tuple[str, str], str | None]      = {}

        self.course_calls:   list[tuple[str, str, str]] = []
        self.sections_calls: list[tuple[str, str]]      = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def fetch_department_list(self, department_code: str) -> str | None:
        return self.list_html.get(department_code)

    async def fetch_course(self, department_code: str, course_number: str, section: str = "001") -> str | None:
        self.course_calls.append((department_code, course_number, section))
        return self.course_html.get((department_code, course_number, section))

    async def fetch_sections(self, department_code: str, course_number: str) -> str | None:
        self.sections_calls.append((department_code, course_number))
        return self.sections_html.get((department_code, course_number))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def build_course_list_html(course_numbers: list[str]) -> str:
    """Build a minimal department list page containing the given course numbers."""
    links = "\n".join(
        f'<a href="sections.html?subj=CS&catno={n}">CS {n}</a>'
        for n in course_numbers
    )
    return f"<html><body>{links}</body></html>"


def build_sections_html(section: str) -> str:
    """Build a minimal sections page that exposes the given section number."""
    return f"""
    <html><body>
      <table><tbody>
        <tr>
          <td data-label="Section">{section}</td>
        </tr>
      </tbody></table>
    </body></html>
    """


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cache():
    """A fresh in-memory PersistentCacheManager for each test."""
    cm = PersistentCacheManager(db_path=":memory:")
    yield cm
    cm.real_close()


@pytest.fixture
def mock_fetcher():
    return MockFetcher()


@pytest.fixture
def pipeline_factory(cache, mock_fetcher):
    """Return a function that builds a Pipeline wired to the test's mocks."""

    def build():
        return Pipeline(
            term=TERM,
            cache_factory=lambda: cache,
            fetcher_factory=lambda: mock_fetcher,
            parser_factory=lambda: UofUCatalogParser(),
        )

    return build


# ─── Happy path ───────────────────────────────────────────────────────────────

class TestHappyPath:

    def test_single_course_inserted(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)

        course = cache.get_course_by_code("CS", "1400")
        assert course is not None
        assert course["course_name"] == "Introduction to Computer Programming"

    def test_multiple_courses_inserted(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400", "3500", "4400"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")
        mock_fetcher.course_html[("CS", "3500", "001")] = load_fixture("cs_3500_detail.html")
        mock_fetcher.course_html[("CS", "4400", "001")] = load_fixture("cs_4400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)

        courses = cache.get_courses_by_department("CS")
        assert len(courses) == 3
        numbers = {c["course_number"] for c in courses}
        assert numbers == {"1400", "3500", "4400"}

    def test_pass_2_links_prerequisites(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["3810", "4400"])
        mock_fetcher.course_html[("CS", "3810", "001")] = """
            <html><body>
              <h1><span>CS 3810</span> - <span>Computer Organization</span></h1>
              <span class="col">4.0</span>
            </body></html>
        """
        mock_fetcher.course_html[("CS", "4400", "001")] = load_fixture("cs_4400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)

        cs_4400 = cache.get_course_by_code("CS", "4400")
        prereqs = cache.get_prerequisites_for_course(cs_4400["course_id"])
        prereq_numbers = {p["course_number"] for p in prereqs}
        assert "3810" in prereq_numbers


# ─── Section fallback ─────────────────────────────────────────────────────────

class TestSectionFallback:

    def test_falls_back_to_sections_page_when_001_is_stub(
        self, pipeline_factory, cache, mock_fetcher
    ):
        mock_fetcher.list_html["CS"] = build_course_list_html(["4400"])
        mock_fetcher.course_html[("CS", "4400", "001")] = "<html><body>stub</body></html>"
        mock_fetcher.sections_html[("CS", "4400")] = build_sections_html("010")
        mock_fetcher.course_html[("CS", "4400", "010")] = load_fixture("cs_4400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)

        course = cache.get_course_by_code("CS", "4400")
        assert course is not None
        assert ("CS", "4400") in mock_fetcher.sections_calls

    def test_skips_course_when_sections_page_is_empty(
        self, pipeline_factory, cache, mock_fetcher
    ):
        mock_fetcher.list_html["CS"] = build_course_list_html(["9999"])
        mock_fetcher.course_html[("CS", "9999", "001")] = "<html><body>stub</body></html>"
        mock_fetcher.sections_html[("CS", "9999")] = (
            "<html><body><table><tbody></tbody></table></body></html>"
        )

        pipeline_factory().run_scrape(["CS"], refresh=False)

        assert cache.get_course_by_code("CS", "9999") is None

    def test_no_section_fallback_when_001_succeeds(
        self, pipeline_factory, cache, mock_fetcher
    ):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)

        assert mock_fetcher.sections_calls == []


# ─── Cache and refresh behavior ───────────────────────────────────────────────

class TestCacheAndRefresh:

    def test_skips_already_cached_courses(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)
        mock_fetcher.course_calls.clear()

        pipeline_factory().run_scrape(["CS"], refresh=False)
        cs_1400_fetches = [c for c in mock_fetcher.course_calls if c[1] == "1400"]
        assert cs_1400_fetches == []

    def test_refresh_clears_department_before_scraping(
        self, pipeline_factory, cache, mock_fetcher
    ):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")

        pipeline_factory().run_scrape(["CS"], refresh=False)
        first_id = cache.get_course_by_code("CS", "1400")["course_id"]

        mock_fetcher.course_calls.clear()
        pipeline_factory().run_scrape(["CS"], refresh=True)
        second_id = cache.get_course_by_code("CS", "1400")["course_id"]
        assert first_id != second_id
        assert ("CS", "1400", "001") in mock_fetcher.course_calls


# ─── Failure tolerance ────────────────────────────────────────────────────────

class TestFailureTolerance:

    def test_failed_department_list_does_not_crash(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = None

        pipeline_factory().run_scrape(["CS"], refresh=False)

        assert cache.get_all_courses() == []

    def test_failed_course_fetch_does_not_crash(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400", "3500"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")
        mock_fetcher.course_html[("CS", "3500", "001")] = None
        mock_fetcher.sections_html[("CS", "3500")]      = None

        pipeline_factory().run_scrape(["CS"], refresh=False)

        assert cache.get_course_by_code("CS", "1400") is not None
        assert cache.get_course_by_code("CS", "3500") is None

    def test_parse_failure_does_not_crash(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"] = build_course_list_html(["1400", "9999"])
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")
        mock_fetcher.course_html[("CS", "9999", "001")] = (
            "<html><body><h1>Some Random Header</h1></body></html>"
        )
        mock_fetcher.sections_html[("CS", "9999")] = None

        pipeline_factory().run_scrape(["CS"], refresh=False)

        assert cache.get_course_by_code("CS", "1400") is not None
        assert cache.get_course_by_code("CS", "9999") is None


# ─── Multi-department ─────────────────────────────────────────────────────────

class TestMultiDepartment:

    def test_multiple_departments_processed(self, pipeline_factory, cache, mock_fetcher):
        mock_fetcher.list_html["CS"]   = build_course_list_html(["1400"])
        mock_fetcher.list_html["MATH"] = (
            '<html><body><a href="sections.html?subj=MATH&catno=2270">MATH 2270</a></body></html>'
        )
        mock_fetcher.course_html[("CS", "1400", "001")] = load_fixture("cs_1400_detail.html")
        mock_fetcher.course_html[("MATH", "2270", "001")] = """
            <html><body>
              <h1><span>MATH 2270</span> - <span>Linear Algebra</span></h1>
              <span class="col">3.0</span>
            </body></html>
        """

        pipeline_factory().run_scrape(["CS", "MATH"], refresh=False)

        assert cache.get_course_by_code("CS", "1400") is not None
        assert cache.get_course_by_code("MATH", "2270") is not None