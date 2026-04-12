from src.scraping.CatalogFetcher import CatalogFetcher

# U of U term IDs for reference:
# 1258 = Fall 2025
# 1264 = Spring 2026
# 1266 = Summer 2026
# 1268 = Fall 2026

class UofUCatalogFetcher(CatalogFetcher):
    def __init__(self, term: str, semaphore: int = 5):
        super().__init__(semaphore)
        self.term = term

    def _construct_course_url(self, department_code: str, course_number: str) -> str:
        """Construct a U of U course detail page URL."""
        base_url = f"https://class-schedule.app.utah.edu/main/{self.term}"
        return f"{base_url}/description.html?subj={department_code}&catno={course_number}&section=001"

    def _construct_department_list_url(self, department_code: str) -> str:
        """Construct a U of U department course listing page URL."""
        base_url = f"https://class-schedule.app.utah.edu/main/{self.term}"
        return f"{base_url}/class_list.html?subject={department_code}"