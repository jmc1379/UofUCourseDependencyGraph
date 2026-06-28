import networkx as nx


def to_vis(graph: nx.DiGraph) -> dict:
    """Convert a course DiGraph into the {nodes, edges} shape vis-network expects."""
    nodes = []
    for code, data in graph.nodes(data=True):
        course = data.get("course")
        nodes.append({
            "id": code,
            "label": code,
            "title": course.course_name if course else code,
        })

    edges = [{"from": u, "to": v} for u, v in graph.edges()]

    return {"nodes": nodes, "edges": edges}
