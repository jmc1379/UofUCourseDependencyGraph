import datetime
from dataclasses import dataclass

@dataclass(frozen=True)
class Course:
    #integer primary key, auto-incremented by SQLite
    department_id: int
    #string like "CS" for application use
    department_code: str
    #foreign key referencing departments table
    course_id: int
    #string like "3500"
    course_number: str

    #human readable title like "Software Practice"
    course_name: str
    #full catalog description text
    course_description: str
    #number of credits
    course_units: float

    #exact text as scraped from the catalog
    raw_prerequisites_string: str
    #parsed list of course ID integers
    prerequisites_ids: set[int]

    #boolean, whether the course is currently offered
    is_active: bool
    #timestamp of when this record was last fetched
    last_scraped: datetime.datetime

    @property
    def course_code(self):
        return str(f"{self.department_code}{self.course_number}")