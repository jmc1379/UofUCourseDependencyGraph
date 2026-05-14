import networkx as nx

from src.graph.CourseGraph import CourseGraph


class GraphAnalyzer:
    def __init__(self, graph: CourseGraph):
        self.course_graph = graph
        self._depths      = self._compute_all_depths()
        self._centrality  = nx.pagerank(self.course_graph.G) if self.course_graph.course_count > 0 else {}

    # ─── Prerequisites and dependents ─────────────────────────────────────────

    def get_all_prerequisites(self, course_code: str) -> set[str]:
        if not self.course_graph.has_course(course_code):
            return set()
        return nx.ancestors(self.course_graph.G, course_code)

    def get_all_dependents(self, course_code: str) -> set[str]:
        if not self.course_graph.has_course(course_code):
            return set()
        return nx.descendants(self.course_graph.G, course_code)

    # ─── Depth ────────────────────────────────────────────────────────────────

    def get_prerequisite_depth(self, course_code: str) -> int | None:
        """Longest prerequisite chain depth for the given course."""
        return self._depths.get(course_code)

    def get_courses_at_depth(self, depth: int) -> set[str]:
        """All courses with the given prerequisite depth."""
        return {code for code, d in self._depths.items() if d == depth}

    def get_max_depth(self) -> int:
        """Deepest prerequisite depth across the entire graph."""
        return max(self._depths.values(), default=0)

    # ─── Chains ───────────────────────────────────────────────────────────────

    def get_shortest_prerequisite_chains(self, course_code: str) -> list[list[str]]:
        """
        Return all prerequisite chains of the shortest length leading to the course.
        Each chain is a list of course codes from a leaf to the target.
        """
        if not self.course_graph.has_course(course_code):
            return []

        leaves = self._get_leaves()
        shortest_length = float("inf")
        shortest_paths  = []

        for leaf in leaves:
            try:
                path = nx.shortest_path(self.course_graph.G, leaf, course_code)
            except nx.NetworkXNoPath:
                continue

            if len(path) < shortest_length:
                shortest_length = len(path)
                shortest_paths  = [path]
            elif len(path) == shortest_length:
                shortest_paths.append(path)

        return shortest_paths

    def get_all_prerequisite_chains(self, course_code: str) -> list[list[str]]:
        """Return every simple prerequisite chain leading to the course."""
        if not self.course_graph.has_course(course_code):
            return []

        leaves = self._get_leaves()
        chains = []
        for leaf in leaves:
            chains.extend(nx.all_simple_paths(self.course_graph.G, leaf, course_code))
        return chains

    # ─── Structural analysis ──────────────────────────────────────────────────

    def find_orphan_courses(self, department_code: str | None = None) -> set[str]:
        """Courses with no prerequisites AND no dependents."""
        return {
            node for node, degree in self.course_graph.G.degree()
            if degree == 0
            and (department_code is None
                 or self.course_graph.get_course(node).department_code == department_code)
        }

    def detect_cycles(self) -> bool:
        """Return True if the graph contains any cycles."""
        return not nx.is_directed_acyclic_graph(self.course_graph.G)

    def topological_sort(self) -> list[str]:
        """Return a valid topological ordering of all courses."""
        return list(nx.topological_sort(self.course_graph.G))

    # ─── Centrality ───────────────────────────────────────────────────────────

    def get_centrality_scores(self) -> dict[str, float]:
        """Return PageRank scores for every course (precomputed)."""
        return self._centrality

    def get_course_centrality_score(self, course_code: str) -> float | None:
        """Return the PageRank score for a specific course."""
        return self._centrality.get(course_code)

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _get_leaves(self) -> set[str]:
        """Courses with no prerequisites — valid starting points for chains."""
        return {
            node for node in self.course_graph.G.nodes
            if self.course_graph.G.in_degree(node) == 0
        }

    def _compute_all_depths(self) -> dict[str, int]:
        """
        Compute the longest prerequisite chain depth for every course in the graph.
        A course with no prerequisites has depth 0.
        """
        G = self.course_graph.G
        depths = {}

        for node in nx.topological_sort(G):
            predecessors = list(G.predecessors(node))
            if not predecessors:
                depths[node] = 0
            else:
                depths[node] = 1 + max(depths[p] for p in predecessors)

        return depths