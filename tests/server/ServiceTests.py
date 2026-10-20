# ─── prereq_subgraph ────────────────────────────────────────────────────────────

class TestPrereqSubgraph:

    def test_returns_none_for_unknown_course(self, graph_service):
        assert graph_service.prereq_subgraph("CS0000") is None

    def test_course_with_no_prereqs_returns_itself_only(self, graph_service):
        subgraph = graph_service.prereq_subgraph("CS1400")
        assert set(subgraph.nodes) == {"CS1400"}
        assert subgraph.number_of_edges() == 0

    def test_includes_transitive_prerequisites(self, graph_service):
        subgraph = graph_service.prereq_subgraph("CS3500")
        assert set(subgraph.nodes) == {"CS1400", "CS2420", "CS3500"}

    def test_preserves_edges_within_subgraph(self, graph_service):
        subgraph = graph_service.prereq_subgraph("CS3500")
        assert set(subgraph.edges) == {("CS1400", "CS2420"), ("CS2420", "CS3500")}

    def test_isolated_course_has_no_edges(self, graph_service):
        subgraph = graph_service.prereq_subgraph("CS9999")
        assert set(subgraph.nodes) == {"CS9999"}
        assert subgraph.number_of_edges() == 0

    def test_does_not_include_dependents(self, graph_service):
        """CS2420's subgraph should include its prereq CS1400, but not its dependent CS3500."""
        subgraph = graph_service.prereq_subgraph("CS2420")
        assert set(subgraph.nodes) == {"CS1400", "CS2420"}
        assert "CS3500" not in subgraph.nodes


# ─── search ──────────────────────────────────────────────────────────────────────

class TestSearch:

    def test_empty_query_returns_empty_list(self, graph_service):
        assert graph_service.search("") == []

    def test_matches_by_code_substring(self, graph_service):
        results = graph_service.search("2420")
        assert {"code": "CS2420", "name": "CS2420"} in results

    def test_case_insensitive(self, graph_service):
        results = graph_service.search("cs2420")
        assert {"code": "CS2420", "name": "CS2420"} in results

    def test_no_match_returns_empty_list(self, graph_service):
        assert graph_service.search("PHYS9999") == []

    def test_respects_limit(self, graph_service):
        results = graph_service.search("CS", limit=2)
        assert len(results) == 2


# ─── course_detail ───────────────────────────────────────────────────────────────

class TestCourseDetail:

    def test_returns_none_for_unknown_course(self, graph_service):
        assert graph_service.course_detail("CS0000") is None

    def test_returns_none_when_node_has_no_course_data(self, graph_service):
        """CS2420 is in the fixture graph but its node has course=None."""
        assert graph_service.course_detail("CS2420") is None

    def test_returns_course_fields(self, graph_service):
        detail = graph_service.course_detail("CS1400")
        assert detail == {
            "code": "CS1400",
            "name": "Fundamentals of Programming",
            "description": "Intro to programming.",
            "units": 4.0,
            "department": "CS",
            "raw_prerequisites": "",
            "is_active": True,
        }
