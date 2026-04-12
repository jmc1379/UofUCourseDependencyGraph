import dataclasses
import datetime
import sqlite3
from dataclasses import asdict
from pathlib import Path

from src.models.Course import Course

STALE_THRESHOLD_DAYS = 30


class CacheManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "UofUCourses.db"

        schema_path = Path(__file__).parent / "schema.sql"
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        self.cursor.executescript(schema_path.read_text())

    # ─── Context Manager ──────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Cleanly close the database connection."""
        if self.connection:
            self.connection.close()

    # ─── Department Methods ───────────────────────────────────────────────────

    def get_department_by_code(self, department_code: str) -> sqlite3.Row | None:
        """Fetch a single department row by its code e.g. 'CS'."""
        self.cursor.execute(
            "SELECT * FROM departments WHERE department_code = ?",
            (department_code,)
        )
        return self.cursor.fetchone()

    def get_all_departments(self) -> list[sqlite3.Row]:
        """Fetch every department row."""
        self.cursor.execute("SELECT * FROM departments")
        return self.cursor.fetchall()

    # ─── Course Write Methods ─────────────────────────────────────────────────

    def insert_course(self, course: Course) -> Course:
        """
        Insert a course and its prerequisite relationships into the database.
        Returns a new immutable Course with real database IDs populated.
        """
        data = asdict(course)

        # Insert department if it doesn't already exist
        self.cursor.execute(
            "INSERT OR IGNORE INTO departments (department_code) VALUES (:department_code)",
            data
        )
        self.cursor.execute(
            "SELECT department_id FROM departments WHERE department_code = :department_code",
            data
        )
        department_id = self.cursor.fetchone()[0]

        # Insert course
        self.cursor.execute(
            """
            INSERT INTO courses (
                department_id, course_number, course_name, course_description,
                course_units, raw_prerequisites_string, is_active, last_scraped
            ) VALUES (
                :department_id, :course_number, :course_name, :course_description,
                :course_units, :raw_prerequisites_string, :is_active, :last_scraped
            )
            """,
            {**data, "department_id": department_id}
        )
        course_id = self.cursor.lastrowid

        # Insert prerequisite relationships
        for prerequisite_id in course.prerequisites_ids:
            self.cursor.execute(
                "INSERT OR IGNORE INTO prerequisites (course_id, prerequisite_id) VALUES (?, ?)",
                (course_id, prerequisite_id)
            )

        self.connection.commit()

        return dataclasses.replace(course, department_id=department_id, course_id=course_id)

    # ─── Course Read Methods ──────────────────────────────────────────────────

    def get_course_by_id(self, course_id: int) -> sqlite3.Row | None:
        """Fetch a single course row by its primary key."""
        self.cursor.execute(
            "SELECT * FROM courses WHERE course_id = ?",
            (course_id,)
        )
        return self.cursor.fetchone()

    def get_course_by_code(self, department_code: str, course_number: str) -> sqlite3.Row | None:
        """Fetch a single course row by its natural key e.g. 'CS', '3500'."""
        self.cursor.execute(
            """
            SELECT c.* FROM courses c
            JOIN departments d ON c.department_id = d.department_id
            WHERE d.department_code = ? AND c.course_number = ?
            """,
            (department_code, course_number)
        )
        return self.cursor.fetchone()

    def get_courses_by_department(self, department_code: str) -> list[sqlite3.Row]:
        """Fetch all course rows belonging to a given department code."""
        self.cursor.execute(
            """
            SELECT c.* FROM courses c
            JOIN departments d ON c.department_id = d.department_id
            WHERE d.department_code = ?
            """,
            (department_code,)
        )
        return self.cursor.fetchall()

    def get_all_courses(self) -> list[sqlite3.Row]:
        """Fetch every course row in the database."""
        self.cursor.execute("SELECT * FROM courses")
        return self.cursor.fetchall()

    # ─── Prerequisite Methods ─────────────────────────────────────────────────

    def get_prerequisites_for_course(self, course_id: int) -> list[sqlite3.Row]:
        """Return all courses that are prerequisites of the given course."""
        self.cursor.execute(
            """
            SELECT c.* FROM courses c
            JOIN prerequisites p ON c.course_id = p.prerequisite_id
            WHERE p.course_id = ?
            """,
            (course_id,)
        )
        return self.cursor.fetchall()

    def get_dependents_for_course(self, course_id: int) -> list[sqlite3.Row]:
        """Return all courses that require the given course as a prerequisite."""
        self.cursor.execute(
            """
            SELECT c.* FROM courses c
            JOIN prerequisites p ON c.course_id = p.course_id
            WHERE p.prerequisite_id = ?
            """,
            (course_id,)
        )
        return self.cursor.fetchall()

    # ─── Cache Utility Methods ────────────────────────────────────────────────

    def course_exists(self, department_code: str, course_number: str) -> bool:
        """Return True if a course already exists in the database."""
        return self.get_course_by_code(department_code, course_number) is not None

    def is_stale(self, course_id: int) -> bool:
        """
        Return True if the course has not been scraped within STALE_THRESHOLD_DAYS.
        Courses that don't exist are considered stale.
        """
        row = self.get_course_by_id(course_id)
        if row is None:
            return True
        last_scraped = datetime.datetime.fromisoformat(row["last_scraped"])
        age = datetime.datetime.now() - last_scraped
        return age.days > STALE_THRESHOLD_DAYS

    def mark_scraped(self, course_id: int) -> None:
        """Update last_scraped for a course to the current timestamp."""
        self.cursor.execute(
            "UPDATE courses SET last_scraped = ? WHERE course_id = ?",
            (datetime.datetime.now().isoformat(), course_id)
        )
        self.connection.commit()

    def clear_department(self, department_code: str) -> None:
        """
        Delete all courses and their prerequisite relationships for a department.
        Useful before a full re-scrape of a department.
        """
        department = self.get_department_by_code(department_code)
        if department is None:
            return

        department_id = department["department_id"]

        # Prerequisites must be deleted first to respect foreign key constraints
        self.cursor.execute(
            """
            DELETE FROM prerequisites WHERE course_id IN (
                SELECT course_id FROM courses WHERE department_id = ?
            )
            """,
            (department_id,)
        )
        self.cursor.execute(
            "DELETE FROM courses WHERE department_id = ?",
            (department_id,)
        )
        self.connection.commit()