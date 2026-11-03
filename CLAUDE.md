# Project Context for Claude

This file gives Claude Code the context it needs to work effectively on this project. It captures architecture decisions, conventions, and known issues that aren't obvious from the code alone.

---

## Project Overview

**UofU Course Dependency Graph** — a Python tool that scrapes the University of Utah course catalog, stores course data in SQLite, builds a prerequisite dependency graph plus a course similarity graph, and (eventually) serves them through a Flask web app with an interactive frontend.

**Goal:** A working demo with an interactive web UI by end of June 2026, intended to be shown to the developer's boss at U of U IT as a pitch for either internal adoption or direct database access in lieu of scraping.

**Current state:** Scraping pipeline, storage layer, graph layer, Flask server, and the interactive frontend are all built and tested (271 tests). The frontend renders a course's prerequisite tree with vis.js, color-coded by course level in the official U of U brand palette, with live search, level/department filters, and a click-through course detail panel. Remaining work is polish, full-university data, and demo prep — see **What's Left**.

---

## Architecture

The project uses dependency injection and abstract base classes to keep concerns separated. Each layer has a clear job and doesn't reach into the others.

```
src/
├── models/
│   └── Course.py              # frozen dataclass; full course data
├── storage/
│   ├── CacheManager.py        # SQLite read/write/cache
│   └── schema.sql             # tables: departments, courses, prerequisites
├── scraping/
│   ├── CatalogFetcher.py      # abstract; async HTTP w/ retry, backoff, 403 handling
│   ├── CatalogParser.py       # abstract; HTML → Course
│   ├── UofUCatalogFetcher.py  # U of U-specific URL construction
│   └── UofUCatalogParser.py   # U of U-specific HTML parsing
├── graph/
│   ├── CourseGraph.py         # NetworkX DiGraph wrapper, built from CacheManager
│   └── GraphAnalyzer.py       # traversal, depth, chains, cycle detection, topological sort, centrality
├── server/
│   ├── __init__.py            # create_app() — Flask app factory
│   ├── service.py             # GraphService — NetworkX queries for the API
│   ├── serialization.py       # to_vis() — DiGraph → vis-network JSON
│   ├── routes.py              # /api blueprint — thin endpoints
│   ├── templates/index.html   # the page Flask serves
│   └── static/                # app.js (vis.js graph, search, filters, detail panel), style.css
└── Pipeline.py                # orchestrator; wires everything together

main.py                        # CLI entry point for the scraping pipeline
run.py                         # starts the Flask server
loadFixtures.py                # dev utility: build DB from saved HTML fixtures
dbViewer.py                    # dev utility: inspect the SQLite database
fixtures/                      # saved HTML pages for parser tests + offline dev
tests/                         # mirrors src/ structure
data/                          # generated: UofUCourses.db, pipeline.log
```

### Layer responsibilities

- **`Course`**: frozen dataclass, fully immutable. `prerequisite_codes` is a `frozenset[str]` of course codes like `"CS2420"`. Placeholder IDs are `-1` until inserted.
- **`CacheManager`**: only place SQL lives. Two-pass insertion is split across `insert_course` (pass 1, no prereqs) and `insert_prerequisites` (pass 2, links). Accepts optional `db_path` for testing (`":memory:"`).
- **`CatalogFetcher`** (base): async HTTP via `aiohttp`, configurable semaphore + delay, retries with backoff, raises `BlockedError` on HTTP 403 to abort the whole run cleanly. Sets a realistic Chrome User-Agent.
- **`UofUCatalogFetcher`**: just URL construction. Three URLs: department list, course detail (with section), course sections list.
- **`CatalogParser`** (base): contract is `get_course_list`, `parse_course_detail`, `parse_prerequisites`, `is_course_page`, `get_section_number`.
- **`UofUCatalogParser`**: BS4 with structural selectors (cards by header text, `<td data-label="Section">`). Avoids regex on whole-page text — that was a source of bugs.
- **`CourseGraph`**: wraps a `networkx.DiGraph`. Nodes keyed by course code with the full `Course` stored as a node attribute. Edges point prerequisite → course ("this prerequisite unlocks the next course").
- **`GraphAnalyzer`**: precomputes depths and PageRank centrality once on init. Operations split between direct lookups (in `CourseGraph`) and algorithms (here).
- **`Pipeline`**: orchestrates fetch → parse → insert → link. Accepts factory injection for `cache_factory`, `fetcher_factory`, `parser_factory` for testing.
- **`GraphService`**: the only thing routes talk to. Wraps `CourseGraph` with query methods (`prereq_subgraph`, `search`, `course_detail`) that return plain dicts/subgraphs — no Flask or HTTP concerns.
- **`to_vis`**: converts a `CourseGraph` subgraph into the `{nodes, edges}` shape vis-network expects, including a `courseLevel` bucket (`"1000"`...`"5000+"`/`"other"`) and `department` per node for the frontend's coloring and filters.
- **`routes.py`**: thin `/api` blueprint — `health`, `search`, `prerequisites/<code>`, `course/<code>`. No logic beyond calling `GraphService` and shaping the HTTP response.

---

## Key Design Decisions

These came up during the project and matter for any new code:

- **Two-pass insertion** is non-negotiable. Insert all courses first, then link prerequisites. Otherwise foreign key constraints fail when a course references one not yet scraped.
- **`prerequisite_codes` is a `frozenset[str]`**, not a `set[int]`. Course codes are stable across scrapes; integer IDs aren't known at parse time.
- **Edge direction is prerequisite → course.** Always. Successors are dependents, predecessors are prerequisites. This convention is load-bearing.
- **The graph is rebuilt from the database every time** the application starts. No pickle/JSON serialization of the graph. SQLite is the source of truth.
- **Section 001 isn't always valid.** Some courses (e.g. CS 4400) use section 010 or other numbers. Pipeline tries 001 first, falls back to fetching the sections page and using its first row.
- **`is_course_page(html)` distinguishes real course pages from stub pages** by checking for an `<h1>` matching the course-code pattern (e.g. `CS 4400`). Stub pages have no such `<h1>`.
- **The polite scrape preset** (semaphore=1, delay=3s) exists because aggressive defaults got the IP rate-limited and then blocked. Default cadence is also conservative now (semaphore=2, delay=0.3s).
- **Jittered delays** (±20%) avoid perfectly-regular request cadence. See `CatalogFetcher._polite_delay`.
- **HTTP 403 raises `BlockedError`** which aborts the whole run without retrying. Treating 403 as a normal failure would hammer a server that's actively saying stop.
- **Never name a vis-network node field `level`.** vis-network reserves `level` on node data for its own hierarchical-layout positioning — a custom field with that name silently gets consumed by the layout engine instead of your app, flinging nodes to extreme off-canvas coordinates with no error. This is why the course-level bucket is called `courseLevel` in both `to_vis()` and `app.js`, not `level`.
- **Hierarchical layout runs with `physics: false`.** With physics on, vis-network's solver can fling small graphs to extreme coordinates (seen first-hand: two nodes landed at y=±75000) because the hierarchical algorithm already positions nodes deterministically — physics was fighting it, not helping. Don't re-enable physics for this layout without a specific reason.
- **The frontend uses the official University of Utah brand palette**, not approximated colors — looked up from brand.utah.edu rather than guessed. Primary: U Red `#BE0000`, Red Rocks `#890000` (dark accent), black, Salt Flat Grey `#E2E6E6`, Zion Cinder Cone `#707271`. Course-level node colors draw from the secondary palette (Great Salt Lake teal, Mountain Green, Wasatch Sunrise gold, Granite Peak blue-gray) — see the `:root` variables in `style.css` and the `LEVELS` array in `app.js`. Keep both in sync if either changes.

---

## Conventions

- **Python 3.13+** (project uses union syntax like `str | None`).
- **`frozen=True` dataclass** for `Course`.
- **BeautifulSoup with `lxml` backend** for HTML parsing.
- **`logging` module configured once** in `Pipeline._configure_logging`. Don't add per-module loggers. Don't print.
- **Tests use in-memory SQLite** (`":memory:"`) and saved HTML fixtures. No real network calls.
- **Async boundary lives in `Pipeline.run_scrape`** — that's where `asyncio.run` is called. Below that everything is async; above that everything is sync.
- **Dependency injection via factory parameters** on Pipeline. Default factories return real implementations; tests pass in mocks.

---

## Known Issues & Limitations

These are intentional limitations, not bugs to fix unprompted:

- **OR relationships in prerequisites aren't preserved.** A flat set of course codes can't represent "A OR B." All extracted codes become AND-style edges in the graph. Acceptable for visualization; documented as future work.
- **"Department carry-forward" in prereq strings isn't implemented.** "MATH 1050 OR 1060 OR 1080" only extracts MATH 1050 because the rest lack a department prefix. The parser doesn't infer that the bare numbers belong to MATH. Logs include spurious "OR1060" prerequisites that get skipped at insert time.
- **Single-department `--refresh` loses cross-department links.** Clearing CS removes prereq rows where CS courses appear on either side, including MATH courses that pointed at CS. Those links are only restored if MATH gets re-scraped. Documented in `CacheManager.clear_department`'s docstring.
- **Scraper currently blocked by U of U.** The original block was triggered by aiohttp's default User-Agent. The fix is in place but hasn't been verified post-block yet.
- **TF-IDF similarity on catalog descriptions doesn't work well.** Descriptions are too short. The right future direction is syllabus data (likely via Canvas API) plus Sentence-Transformers for embeddings, both planned post-demo.

---

## Workflow

### Running the pipeline

```bash
python main.py --department CS                 # scrape one department
python main.py --all                           # scrape all configured departments
python main.py --polite --department CS        # conservative speed (1 concurrent, 3s delay)
python main.py --department CS --refresh       # clear and re-scrape
python main.py --department CS --delay 5       # custom delay
```

### Running tests

```bash
pytest                                         # all tests (271 currently)
pytest tests/scraping/                         # one module
pytest --cov=src                               # with coverage
```

### Loading fixtures (offline development)

```bash
python loadFixtures.py
```

Reads `fixtures/*_detail.html`, parses them through the real parser, inserts into the database. Useful when the live site is unavailable.

### Running the web app

```bash
python run.py
```

Serves the Flask app at `http://127.0.0.1:5000`. Reads from `data/UofUCourses.db`, so populate it first via `main.py` or `loadFixtures.py`. The graph is rebuilt from the database on every app start — there's no separate serialized graph file.

### Inspecting the database

```bash
python dbViewer.py
```

Dev utility for poking at `data/UofUCourses.db` directly without writing throwaway SQL.

---

## What's Left

Done, per the original project timeline:

1. ~~**Flask server** (Week 4) — `src/server/`, endpoints for `/health`, `/search`, `/prerequisites/<code>`, `/course/<code>`~~
2. ~~**Frontend graph visualization** (Week 5) — vis.js, color-coded by course level~~
3. ~~**Search and detail panel** (Week 6) — search bar, clickable nodes, filter controls~~

Remaining:

4. **Polish + full-university data** (Week 7) — currently scrapes CS, MATH, ECE, PHYS only
5. **Demo prep** (Week 8)

Further out, from the README roadmap:

6. Show what a course unlocks (dependents), not just what it requires
7. Course similarity graph based on course descriptions (blocked on short catalog descriptions — see TF-IDF note below; likely needs syllabus data + embeddings)
8. Deploy a hosted demo

Don't proactively touch the existing scraping/storage/graph code unless asked — those layers are stable, tested, and settled. The server/frontend layers are also working end-to-end now, but still the active area — polish and small fixes there are fair game, bigger changes should go through the usual "suggest before doing" discussion.

---

## How to be useful here

- **Respect the layered architecture.** Don't put SQL outside CacheManager. Don't put network code outside CatalogFetcher. Don't put graph algorithms in CourseGraph.
- **Match the existing style.** Sectional comment dividers (`# ─── Section ───`), descriptive docstrings, type hints, conservative formatting.
- **Suggest before doing.** The developer prefers discussing design tradeoffs before implementation, especially for non-trivial changes. Ask clarifying questions when scope is ambiguous.
- **Be direct about bugs and tradeoffs.** This project has benefited from honest pushback on bad ideas. Don't gloss over real problems.
- **Don't add features beyond what was asked.** The scope of this project is deliberately bounded.