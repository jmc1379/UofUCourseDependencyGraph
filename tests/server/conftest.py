import networkx as nx
import pytest
from flask import Flask

from src.server.routes import api
from src.server.service import GraphService


class FakeCourseGraph:
    """Minimal stand-in for CourseGraph — just enough surface for GraphService to use."""

    def __init__(self, G: nx.DiGraph):
        self.G = G

    def has_course(self, course_code: str) -> bool:
        return course_code in self.G.nodes


@pytest.fixture
def course_digraph() -> nx.DiGraph:
    """
    A tiny hand-built prerequisite graph:
    CS1400 -> CS2420 -> CS3500
    CS9999 is isolated (no prereqs, no dependents).
    """
    G = nx.DiGraph()
    G.add_node("CS1400", course=None)
    G.add_node("CS2420", course=None)
    G.add_node("CS3500", course=None)
    G.add_node("CS9999", course=None)
    G.add_edge("CS1400", "CS2420")
    G.add_edge("CS2420", "CS3500")
    return G


@pytest.fixture
def graph_service(course_digraph) -> GraphService:
    """A GraphService wired to the tiny fixture graph — no database involved."""
    return GraphService(FakeCourseGraph(course_digraph))


@pytest.fixture
def app(graph_service) -> Flask:
    """A minimal Flask app with just the api blueprint, using the fixture GraphService."""
    flask_app = Flask(__name__)
    flask_app.config["GRAPH_SERVICE"] = graph_service
    flask_app.register_blueprint(api)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
