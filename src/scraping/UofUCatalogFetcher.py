from src.scraping.CatalogFetcher import CatalogFetcher

# U of U term IDs for reference:
# 1258 = Fall 2025
# 1264 = Spring 2026
# 1266 = Summer 2026
# 1268 = Fall 2026


class UofUCatalogFetcher(CatalogFetcher):
    def __init__(self, term: str, semaphore: int = 5, request_delay: float = 0.3):
        super().__init__(semaphore=semaphore, request_delay=request_delay)
        self.term = term

    def _construct_course_url(self, department_code: str, course_number: str, section: str) -> str:
        """Construct a U of U course detail page URL for a specific section."""
        base_url = f"https://class-schedule.app.utah.edu/main/{self.term}"
        return (
            f"{base_url}/description.html"
            f"?subj={department_code}&catno={course_number}&section={section}"
        )

    def _construct_department_list_url(self, department_code: str) -> str:
        """Construct a U of U department course listing page URL."""
        base_url = f"https://class-schedule.app.utah.edu/main/{self.term}"
        return f"{base_url}/class_list.html?subject={department_code}"

    def _construct_sections_url(self, department_code: str, course_number: str) -> str:
        """Construct a U of U course section listing page URL."""
        base_url = f"https://class-schedule.app.utah.edu/main/{self.term}"
        return f"{base_url}/sections.html?subj={department_code}&catno={course_number}"