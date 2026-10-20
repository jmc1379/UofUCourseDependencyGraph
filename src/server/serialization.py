import networkx as nx


def _level_bucket(course_number: str) -> str:
    """Bucket a course number like '4400' into a level group for UI coloring/filtering."""
    if not course_number or not course_number[0].isdigit():
        return "other"
    digit = int(course_number[0])
    if 1 <= digit <= 4:
        return f"{digit}000"
    if digit >= 5:
        return "5000+"
    return "other"


def to_vis(graph: nx.DiGraph) -> dict:
    """Convert a course DiGraph into the {nodes, edges} shape vis-network expects."""
    nodes = []
    for code, data in graph.nodes(data=True):
        course = data.get("course")
        nodes.append({
            "id": code,
            "label": code,
            "title": course.course_name if course else code,
            "department": course.department_code if course else None,
            # Named courseLevel, not level — vis-network reserves "level" on
            # node data for its own hierarchical-layout positioning.
            "courseLevel": _level_bucket(course.course_number) if course else "other",
        })

    edges = [{"from": u, "to": v} for u, v in graph.edges()]

    return {"nodes": nodes, "edges": edges}
