import networkx as nx

from src.graph.CourseGraph import CourseGraph


class GraphService:
    """NetworkX queries against the course graph, for the API layer to call."""

    def __init__(self, course_graph: CourseGraph):
        self.course_graph = course_graph

    def prereq_subgraph(self, course_code: str) -> nx.DiGraph | None:
        """
        Return the induced subgraph containing course_code and every one of
        its prerequisites, direct and transitive. Returns None if the course
        isn't in the graph.
        """
        if not self.course_graph.has_course(course_code):
            return None

        ancestors = nx.ancestors(self.course_graph.G, course_code)
        nodes = ancestors | {course_code}
        return self.course_graph.G.subgraph(nodes)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """
        Find courses whose code or name contains query (case-insensitive).
        Code matches are favored over name matches. Used as the UI's search
        entry point — not a graph traversal, just a lookup over graph nodes.
        """
        query = query.strip().lower()
        if not query:
            return []

        code_matches = []
        name_matches = []
        for code, data in self.course_graph.G.nodes(data=True):
            course = data.get("course")
            name = course.course_name if course else code

            if query in code.lower():
                code_matches.append({"code": code, "name": name})
            elif query in name.lower():
                name_matches.append({"code": code, "name": name})

        code_matches.sort(key=lambda c: c["code"])
        name_matches.sort(key=lambda c: c["name"])
        return (code_matches + name_matches)[:limit]
