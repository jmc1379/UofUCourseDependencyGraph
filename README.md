# UofU Course Dependency Graph

An interactive prerequisite explorer for University of Utah courses. It scrapes the course catalog, stores the data in SQLite, builds a prerequisite graph with NetworkX, and serves it through a Flask API to a vis.js frontend. Search for any course and see its full prerequisite tree, color-coded by level.

Built as a demo to pitch to University of Utah IT, either for internal adoption or for direct database access in place of scraping.

<!-- Add a screenshot of the graph UI here, e.g.:
![Prerequisite graph for CS 4400](docs/screenshot.png)
-->

---

## Features

- **Prerequisite graph:** pick a course and the app renders every direct and transitive prerequisite as a top-down hierarchical graph.
- **Live search:** results appear as you type, matching on course code or title, with code matches ranked first.
- **Filters:** toggle courses by level (1000s through 5000+) and by department without refetching from the server.
- **Course details:** click any node to see its units, department, status, description, and the catalog's prerequisite text.

## Highlights

- **Extensible scraper design.** Abstract `CatalogFetcher` and `CatalogParser` base classes with dependency injection, so supporting another university's catalog means writing a new fetcher and parser subclass rather than modifying existing code.
- **Resilient async scraping.** Concurrent requests through `aiohttp` with a configurable concurrency limit and delay, exponential backoff on HTTP 429, and an immediate clean stop on HTTP 403.
- **Server-side graph queries.** The API returns only the subgraph a view needs (a course and its prerequisite ancestors) instead of sending the whole graph to the browser.
- **Tested.** 271 tests with 92% line coverage, running entirely offline against in-memory SQLite and saved HTML fixtures.

---

## Architecture

```
Catalog HTML ──► Fetcher/Parser ──► SQLite (CacheManager) ──► CourseGraph (NetworkX)
                                                                   │
                                     vis.js frontend ◄── Flask API (GraphService)
```

- **Scraping** (`src/scraping/`) fetches catalog pages and parses them into `Course` objects.
- **Storage** (`src/storage/`) is the only place SQL lives. Scraped courses are cached and marked stale over time.
- **Graph** (`src/graph/`) builds a NetworkX `DiGraph` from the database. `GraphAnalyzer` adds traversal, prerequisite depth, chains, cycle detection, topological sort, and centrality.
- **Server** (`src/server/`) is a Flask app factory with a thin API blueprint. Graph queries live in `GraphService`, and `to_vis()` converts subgraphs to the JSON shape vis-network expects.

---

## Current Status

- **Done:** scraping pipeline, SQLite storage, graph layer, Flask API, and interactive frontend (search, filters, detail panel).
- **Scraped departments:** CS, MATH, ECE, and PHYS are configured for `--all`.
- **Known limitation:** the live catalog has previously blocked the scraper's requests. The fetcher now sends a realistic browser User-Agent, and a 403 response stops the run cleanly instead of hammering the server.

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
│   │   └── GraphAnalyzer.py        # traversal, depth, chains, cycles, centrality
│   ├── server/
│   │   ├── __init__.py             # create_app() — Flask app factory
│   │   ├── service.py              # GraphService — NetworkX queries for the API
│   │   ├── serialization.py        # to_vis() — DiGraph → vis-network JSON
│   │   ├── routes.py               # /api blueprint — thin endpoints
│   │   ├── templates/
│   │   │   └── index.html          # the page Flask serves
│   │   └── static/
│   │       ├── app.js              # vis.js graph, search, filters, detail panel
│   │       └── style.css
│   └── Pipeline.py                 # scrape orchestrator; wires everything together
├── tests/                          # mirrors src/; files named *Tests.py
│   ├── graph/  models/  scraping/  storage/
│   ├── server/
│   │   ├── conftest.py             # small fixture graph + Flask test app
│   │   ├── ServiceTests.py         # unit tests on GraphService (no Flask)
│   │   └── RoutesTests.py          # test_client tests on the endpoints
│   └── PipelineTests.py
├── fixtures/                       # saved HTML pages for parser tests + offline dev
├── data/                           # generated (git-ignored): UofUCourses.db, pipeline.log
├── main.py                         # CLI entry point for the scraping pipeline
├── run.py                          # starts the Flask server
├── loadFixtures.py                 # dev utility: build DB from saved HTML fixtures
├── dbViewer.py                     # dev utility: inspect the SQLite database
└── requirements.txt
```

---

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/jmc1379/UofUCourseDependencyGraph.git
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

### 1. Build the database

The web app reads from `data/UofUCourses.db`, so populate it first.

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

The graph is rebuilt from the database each time it's loaded. There's no separate serialized graph file.

**Offline alternative:** `python loadFixtures.py` builds a small database from the saved HTML pages in `fixtures/` without touching the live catalog. It only contains a handful of CS courses, so it's for development, not for exploring the full catalog.

### 2. Run the web app

```bash
python run.py
```

Then open http://127.0.0.1:5000.

### API

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{"ok": true}` liveness check |
| `GET /api/search?q=<text>` | up to 20 courses matching a code or title substring |
| `GET /api/prerequisites/<code>` | the course and all its prerequisites as vis-network `{nodes, edges}` |
| `GET /api/course/<code>` | full details for one course |

Course codes are case-insensitive and written without a space, for example `CS4400`. Unknown codes return 404.

---

## Running Tests

```bash
pytest                          # run all tests
pytest --cov=src                # with coverage report
pytest tests/scraping/          # run a specific module's tests
```

Tests use in-memory SQLite and saved HTML fixtures, so they make no network calls.

---

## Roadmap

1. Show what a course unlocks (dependents), not just what it requires
2. Course similarity graph based on course descriptions
3. Expand beyond the four configured departments to the full university catalog
4. Deploy a hosted demo
