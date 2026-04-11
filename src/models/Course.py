import datetime
from dataclasses import dataclass

@dataclass(frozen=True)
class Course:
    #integer primary key, auto-incremented by SQLite
    department_id: int
    #foreign key referencing departments table
    course_id: int
    #string like "3500"
    course_number: int
    #integer like 3000, derived from course number but stored explicitly
    course_level: int
    #human readable title like "Software Practice"
    course_name: str
    #full catalog description text
    course_description: str
    #number of credits
    course_units: float
    #exact text as scraped from the catalog
    raw_prerequisites_string: str
    #parsed list of course ID integers
    prerequisites_ids: {str}
    #boolean, whether the course is currently offered
    is_active: bool
    #timestamp of when this record was last fetched
    last_scraped: datetime
