# ─── /api/health ─────────────────────────────────────────────────────────────────

class TestHealth:

    def test_returns_200(self, client):
        assert client.get("/api/health").status_code == 200

    def test_returns_ok_true(self, client):
        assert client.get("/api/health").get_json() == {"ok": True}


# ─── /api/prerequisites/<code> ───────────────────────────────────────────────────

class TestPrerequisites:

    def test_known_course_returns_200(self, client):
        assert client.get("/api/prerequisites/CS3500").status_code == 200

    def test_response_has_vis_shape(self, client):
        data = client.get("/api/prerequisites/CS3500").get_json()
        assert set(data.keys()) == {"nodes", "edges"}

    def test_includes_transitive_prerequisites(self, client):
        data = client.get("/api/prerequisites/CS3500").get_json()
        node_ids = {node["id"] for node in data["nodes"]}
        assert node_ids == {"CS1400", "CS2420", "CS3500"}

    def test_edges_use_vis_from_to_shape(self, client):
        data = client.get("/api/prerequisites/CS3500").get_json()
        assert {"from": "CS1400", "to": "CS2420"} in data["edges"]
        assert {"from": "CS2420", "to": "CS3500"} in data["edges"]

    def test_unknown_course_returns_404(self, client):
        response = client.get("/api/prerequisites/CS0000")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_code_is_uppercased(self, client):
        """The route uppercases the code before querying — fixture nodes are uppercase."""
        data = client.get("/api/prerequisites/cs1400").get_json()
        assert data["nodes"] == [{"id": "CS1400", "label": "CS1400", "title": "CS1400"}]


# ─── /api/search ──────────────────────────────────────────────────────────────────

class TestSearch:

    def test_returns_200(self, client):
        assert client.get("/api/search?q=CS").status_code == 200

    def test_matches_returned(self, client):
        data = client.get("/api/search?q=2420").get_json()
        assert {"code": "CS2420", "name": "CS2420"} in data

    def test_missing_query_param_returns_empty_list(self, client):
        assert client.get("/api/search").get_json() == []
