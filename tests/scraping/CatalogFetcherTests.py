from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

from src.scraping.UofUCatalogFetcher import UofUCatalogFetcher

TERM        = "1258"
DEPARTMENT  = "CS"
COURSE_NUM  = "3500"
SAMPLE_HTML = "<html><body>CS 3500 - Software Practice</body></html>"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_mock_response(status: int = 200, text: str = SAMPLE_HTML) -> MagicMock:
    """Build a mock aiohttp response that works as an async context manager."""
    response         = MagicMock()
    response.status  = status
    response.text    = AsyncMock(return_value=text)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__  = AsyncMock(return_value=False)
    return response


def make_mock_session(response: MagicMock) -> MagicMock:
    """Build a mock aiohttp ClientSession that returns the given response."""
    session       = MagicMock()
    session.get   = MagicMock(return_value=response)
    session.close = AsyncMock()
    return session


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def mock_session():
    """Provide a default mock session with a 200 response."""
    return make_mock_session(make_mock_response())


@pytest_asyncio.fixture
async def fetcher(mock_session):
    """
    Provide a UofUCatalogFetcher with aiohttp.ClientSession patched at the
    class level so no real session is ever created.
    """
    with patch("aiohttp.ClientSession", return_value=mock_session):
        async with UofUCatalogFetcher(term=TERM, semaphore=5) as f:
            yield f


# ─── URL Construction ─────────────────────────────────────────────────────────

class TestUofUUrlConstruction:
    """These tests require no mocking — just verify URL strings are correct."""

    def test_construct_course_url(self):
        f = UofUCatalogFetcher(term=TERM)
        url = f._construct_course_url(DEPARTMENT, COURSE_NUM)
        assert url == (
            f"https://class-schedule.app.utah.edu/main/{TERM}"
            f"/description.html?subj={DEPARTMENT}&catno={COURSE_NUM}&section=001"
        )

    def test_construct_department_list_url(self):
        f = UofUCatalogFetcher(term=TERM)
        url = f._construct_department_list_url(DEPARTMENT)
        assert url == (
            f"https://class-schedule.app.utah.edu/main/{TERM}"
            f"/class_list.html?subject={DEPARTMENT}"
        )

    def test_course_url_changes_with_term(self):
        f = UofUCatalogFetcher(term="1264")
        url = f._construct_course_url(DEPARTMENT, COURSE_NUM)
        assert "1264" in url

    def test_course_url_changes_with_department(self):
        f = UofUCatalogFetcher(term=TERM)
        url = f._construct_course_url("MATH", "2270")
        assert "MATH" in url
        assert "2270" in url

    def test_department_list_url_changes_with_department(self):
        f = UofUCatalogFetcher(term=TERM)
        url = f._construct_department_list_url("MATH")
        assert "MATH" in url
        assert "class_list" in url


# ─── Context Manager ──────────────────────────────────────────────────────────

class TestContextManager:

    @pytest.mark.asyncio
    async def test_session_created_on_enter(self, fetcher):
        assert fetcher.session is not None

    @pytest.mark.asyncio
    async def test_session_closed_on_exit(self, mock_session):
        with patch("aiohttp.ClientSession", return_value=mock_session):
            async with UofUCatalogFetcher(term=TERM) as f:
                assert f.session is not None
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_none_after_close(self, fetcher):
        await fetcher.close()
        assert fetcher.session is None


# ─── fetch_course ─────────────────────────────────────────────────────────────

class TestFetchCourse:

    @pytest.mark.asyncio
    async def test_returns_html_on_success(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(200, SAMPLE_HTML))
        result = await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
        assert result == SAMPLE_HTML

    @pytest.mark.asyncio
    async def test_returns_none_after_all_retries_fail(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=500))
        result = await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_client_error(self, fetcher, mock_session):
        bad_context = MagicMock()
        bad_context.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("connection failed"))
        bad_context.__aexit__  = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=bad_context)
        result = await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
        assert result is None

    @pytest.mark.asyncio
    async def test_retries_on_non_200(self, fetcher, mock_session):
        """Confirm multiple attempts are made before giving up."""
        response = make_mock_response(status=503)
        mock_session.get = MagicMock(return_value=response)
        await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
        assert response.__aenter__.call_count == 5   # MAX_RETRIES

    @pytest.mark.asyncio
    async def test_logs_warning_on_failed_attempt(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=500))
        with patch("src.scraping.CatalogFetcher.logging.warning") as mock_warning:
            await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
            assert mock_warning.call_count > 0

    @pytest.mark.asyncio
    async def test_logs_error_after_all_retries(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=500))
        with patch("src.scraping.CatalogFetcher.logging.error") as mock_error:
            await fetcher.fetch_course(DEPARTMENT, COURSE_NUM)
            assert mock_error.call_count == 1


# ─── fetch_department_list ────────────────────────────────────────────────────

class TestFetchDepartmentList:

    @pytest.mark.asyncio
    async def test_returns_html_on_success(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(200, SAMPLE_HTML))
        result = await fetcher.fetch_department_list(DEPARTMENT)
        assert result == SAMPLE_HTML

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=404))
        result = await fetcher.fetch_department_list(DEPARTMENT)
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_department_list_url(self, fetcher):
        with patch.object(fetcher, "_construct_department_list_url", return_value="http://fake-url") as mock_url:
            await fetcher.fetch_department_list(DEPARTMENT)
            mock_url.assert_called_once_with(DEPARTMENT)


# ─── fetch_department ─────────────────────────────────────────────────────────

class TestFetchDepartment:

    @pytest.mark.asyncio
    async def test_returns_list_of_html_strings(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(200, SAMPLE_HTML))
        results = await fetcher.fetch_department(DEPARTMENT, ["3500", "2420"])
        assert len(results) == 2
        assert all(r == SAMPLE_HTML for r in results)

    @pytest.mark.asyncio
    async def test_filters_out_failed_fetches(self, fetcher):
        async def mock_fetch_course(dept, num):
            return SAMPLE_HTML if num == "3500" else None

        fetcher.fetch_course = mock_fetch_course
        results = await fetcher.fetch_department(DEPARTMENT, ["3500", "9999"])
        assert len(results) == 1
        assert results[0] == SAMPLE_HTML

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_all_fail(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=500))
        results = await fetcher.fetch_department(DEPARTMENT, ["3500", "2420"])
        assert results == []

    @pytest.mark.asyncio
    async def test_empty_course_numbers_returns_empty_list(self, fetcher):
        results = await fetcher.fetch_department(DEPARTMENT, [])
        assert results == []


# ─── fetch_all ────────────────────────────────────────────────────────────────

class TestFetchAll:

    @pytest.mark.asyncio
    async def test_returns_dict_with_all_departments(self, fetcher, mock_session):
        mock_session.get   = MagicMock(return_value=make_mock_response(200, SAMPLE_HTML))
        department_map = {"CS": ["3500"], "MATH": ["2270"]}
        results = await fetcher.fetch_all(department_map)
        assert "CS" in results
        assert "MATH" in results

    @pytest.mark.asyncio
    async def test_empty_department_map_returns_empty_dict(self, fetcher):
        results = await fetcher.fetch_all({})
        assert results == {}

    @pytest.mark.asyncio
    async def test_failed_department_returns_empty_list(self, fetcher, mock_session):
        mock_session.get = MagicMock(return_value=make_mock_response(status=500))
        results = await fetcher.fetch_all({"CS": ["3500"]})
        assert results["CS"] == []