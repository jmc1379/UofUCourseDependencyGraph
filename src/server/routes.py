from flask import Blueprint, current_app, jsonify, request

from src.server.serialization import to_vis
from src.server.service import GraphService

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/health")
def health():
    """Trivial liveness check."""
    return jsonify({"ok": True})


@api.route("/prerequisites/<code>")
def prerequisites(code):
    """Return the prerequisite subgraph for a course code, in vis-network shape."""
    graph_service: GraphService = current_app.config["GRAPH_SERVICE"]
    subgraph = graph_service.prereq_subgraph(code.upper())
    if subgraph is None:
        return jsonify({"error": f"Unknown course: {code}"}), 404

    return jsonify(to_vis(subgraph))


@api.route("/search")
def search():
    """Search courses by code or title substring — the UI's search entry point."""
    graph_service: GraphService = current_app.config["GRAPH_SERVICE"]
    return jsonify(graph_service.search(request.args.get("q", "")))
