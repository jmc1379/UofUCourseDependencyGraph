CREATE TABLE IF NOT EXISTS departments (
    department_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    department_code TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS courses (
    course_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL,
    course_number           TEXT    NOT NULL,
    course_name             TEXT    NOT NULL,
    course_description      TEXT,
    course_units            REAL    NOT NULL,
    raw_prerequisites_string TEXT,
    is_active               INTEGER NOT NULL DEFAULT 1,
    last_scraped            TEXT    NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments (department_id)
);

CREATE TABLE IF NOT EXISTS prerequisites (
    course_id       INTEGER NOT NULL,
    prerequisite_id INTEGER NOT NULL,
    PRIMARY KEY (course_id, prerequisite_id),
    FOREIGN KEY (course_id)       REFERENCES courses (course_id),
    FOREIGN KEY (prerequisite_id) REFERENCES courses (course_id)
);