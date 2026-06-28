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
