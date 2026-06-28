# UofU Course Dependency Graph

A tool that scrapes the University of Utah course catalog, stores course data in SQLite, and builds a prerequisite dependency graph (plus a course similarity graph) from it. The end goal is a Flask web app with an interactive frontend for exploring course prerequisites — built as a demo to pitch to University of Utah IT for internal adoption or direct database access in lieu of scraping.

Architecture uses dependency injection and abstract base classes, so adding support for another university's catalog means writing a new fetcher/parser subclass rather than modifying existing code.

---

## Current Status

- **Done:** scraping pipeline, SQLite storage, and graph layer (prerequisite + similarity graphs). Tested and stable.
- **In progress:** Flask server and frontend. The `src/server/` module and its tests are scaffolded (empty files, no logic yet).
- **Known limitation:** the live catalog has previously blocked the scraper's requests; the fetcher now sends a realistic Chrome User-Agent to work around this.

See `CLAUDE.md` for the full architecture writeup, design decisions, and known issues.

---

## Project Structure

```
UofUCourseDependencyGraph/
├── src/
│   ├── models/
│   │   └── Course.py               # frozen dataclass; full course data
│   ├── storage/
│   │   ├── CacheManager.py         # SQLite read/write/cache — only place SQL lives
│   │   └── schema.sql              # tables: departments, courses, prerequisites
│   ├── scraping/
│   │   ├── CatalogFetcher.py       # abstract; async HTTP w/ retry, backoff, 403 handling
│   │   ├── CatalogParser.py        # abstract; HTML → Course
│   │   ├── UofUCatalogFetcher.py   # U of U-specific URL construction
│   │   └── UofUCatalogParser.py    # U of U-specific HTML parsing
│   ├── graph/
│   │   ├── CourseGraph.py          # NetworkX DiGraph wrapper, built from CacheManager
│   │   └── GraphAnalyzer.py        # traversal, depth, centrality, chains
│   ├── server/                     # Flask layer (scaffolded, not yet implemented)
│   │   ├── __init__.py             # create_app() — the factory
│   │   ├── service.py              # GraphService — NetworkX queries live here
│   │   ├── serialization.py        # to_vis() — DiGraph → vis-network JSON
│   │   ├── routes.py               # the api blueprint — thin endpoints
│   │   ├── templates/
│   │   │   └── index.html          # the page Flask serves
│   │   └── static/
│   │       ├── app.js              # vis.js setup + fetch() calls to the API
│   │       └── style.css
│   └── Pipeline.py                 # orchestrator; wires everything together
├── tests/                          # mirrors src/ structure
│   └── server/
│       ├── conftest.py             # a tiny fixture DiGraph + a test app
│       ├── test_service.py         # unit tests on GraphService (no Flask)
│       └── test_routes.py          # test_client tests on the endpoints
├── fixtures/                       # saved HTML pages for parser tests + offline dev
├── data/                           # generated: UofUCourses.db, pipeline.log
├── main.py                         # CLI entry point (scraping pipeline)
├── run.py                          # launch entry point for the Flask server
├── loadFixtures.py                 # dev utility: build DB from saved HTML fixtures
├── dbViewer.py                     # dev utility: inspect the SQLite database
└── requirements.txt
```

---

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/your-username/UofUCourseDependencyGraph.git
cd UofUCourseDependencyGraph
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# Scrape one department
python main.py --department CS

# Scrape every configured department (CS, MATH, ECE, PHYS)
python main.py --all

# Conservative speed — 1 concurrent request, 3s delay — for when the catalog is rate-limiting
python main.py --polite --department CS

# Clear cached data for the target department(s) and re-scrape
python main.py --department CS --refresh

# Custom concurrency / delay / term
python main.py --department CS --semaphore 1 --delay 5 --term 1268
```

Scraped data is cached in `data/UofUCourses.db` (SQLite). The graph is rebuilt from the database on every run — there's no separate serialized graph file.

### Offline development

```bash
python loadFixtures.py
```

Builds the database from saved HTML fixtures in `fixtures/` instead of hitting the live catalog. Useful when the site is unavailable or you don't want to make live requests while iterating.

---

## Running Tests

```bash
pytest                          # run all tests
pytest --cov=src                # with coverage report
pytest tests/scraping/          # run a specific module's tests
```

Tests use in-memory SQLite and saved HTML fixtures — no real network calls.

---

## Roadmap

1. Flask server (`/graph`, `/course/<code>`, `/search`, `/prerequisites/<code>` endpoints)
2. Frontend graph visualization (vis.js, color-coded by course level)
3. Search bar, clickable nodes, filter controls
4. Full-university data + polish
5. Demo prep
