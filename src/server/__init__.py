from flask import Flask, render_template

from src.graph.CourseGraph import CourseGraph
from src.server.routes import api
from src.server.service import GraphService
from src.storage.CacheManager import CacheManager


def create_app() -> Flask:
    """Construct and configure the Flask application."""
    app = Flask(__name__)

    with CacheManager() as cache:
        course_graph = CourseGraph(cache)
    app.config["GRAPH_SERVICE"] = GraphService(course_graph)

    app.register_blueprint(api)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
