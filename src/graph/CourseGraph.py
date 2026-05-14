from datetime import datetime

import networkx as nx

from src.models.Course import Course
from src.storage.CacheManager import CacheManager


class CourseGraph:

    @property
    def course_count(self):
        return self.G.number_of_nodes()

    @property
    def edge_count(self):
        return self.G.number_of_edges()

    def __init__(self, cache: CacheManager):
        self.G = nx.DiGraph()
        self.cache = cache
        courses = self._construct_course_list()

        # Add all vertices
        for course in courses:
            self.G.add_node(course.course_code, course=course)

        self._departments = {data["course"].department_code for _, data in self.G.nodes(data=True)}

        # Add all edges
        for course in courses:
            for prerequisite in course.prerequisite_codes:
                self.G.add_edge(prerequisite, course.course_code)


    def _construct_course_list(self) -> list[Course]:
        course_list = []
        for row in self.cache.get_all_courses():
            course_list.append(self._construct_course(row))

        return course_list

    def _construct_prerequisite_set(self, course_id) -> frozenset[str]:
        return frozenset({
            f"{row['department_code']}{row['course_number']}"
            for row in self.cache.get_prerequisites_for_course(course_id)
        })

    def _construct_course(self, row) -> Course:
        course = Course(
            department_id=row["department_id"],
            department_code=row["department_code"],
            course_id=row["course_id"],
            course_number=row["course_number"],
            course_name=row["course_name"],
            course_description=row["course_description"],
            course_units=row["course_units"],
            raw_prerequisites_string=row["raw_prerequisites_string"],
            prerequisite_codes=self._construct_prerequisite_set(row["course_id"]),
            is_active=bool(row["is_active"]),
            last_scraped=datetime.fromisoformat(row["last_scraped"]),
        )

        return course

    def get_course(self, course_code: str) -> Course | None:
        if not self.has_course(course_code):
            return None

        return self.G.nodes[course_code]["course"]

    def has_course(self, course_code: str) -> bool:
        return course_code in self.G.nodes

    def get_direct_prerequisites(self, course_code: str) -> set[str] | None:
        if not self.has_course(course_code):
            return None

        return set(self.G.predecessors(course_code))

    def get_direct_dependents(self, course_code: str) -> set[str] | None:
        if not self.has_course(course_code):
            return None

        return set(self.G.successors(course_code))

    def search_by_name(self, name: str) -> set[Course]:
        query = name.lower()
        return {
            data["course"] for _, data in self.G.nodes(data=True)
            if query in data["course"].course_name.lower()
        }

    def get_all_courses(self) -> set[Course]:
        return {data["course"] for _, data in self.G.nodes(data=True)}

    def get_courses_by_department(self, department_code) -> set[Course]:
        query = department_code.upper()
        return {
            data["course"] for _, data in self.G.nodes(data=True)
            if query == data["course"].department_code
        }

    def get_departments(self) -> set[str]:
        return self._departments
