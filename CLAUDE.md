# Project Context for Claude

This file gives Claude Code the context it needs to work effectively on this project. It captures architecture decisions, conventions, and known issues that aren't obvious from the code alone.

---

## Project Overview

**UofU Course Dependency Graph** — a Python tool that scrapes the University of Utah course catalog, stores course data in SQLite, builds a prerequisite dependency graph plus a course similarity graph, and (eventually) serves them through a Flask web app with an interactive frontend.

**Goal:** A working demo with an interactive web UI by end of June 2026, intended to be shown to the developer's boss at U of U IT as a pitch for either internal adoption or direct database access in lieu of scraping.

**Current state:** Scraping pipeline, storage layer, and graph layer are complete and tested. The next major chunk is the Flask server and frontend. The live catalog is currently blocking the developer's User-Agent (the scraper sends a realistic Chrome User-Agent now to work around this).

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
│   └── GraphAnalyzer.py       # traversal, depth, centrality, chains
└── Pipeline.py                # orchestrator; wires everything together

main.py                        # CLI entry point
load_fixtures.py               # dev utility: build DB from saved HTML fixtures
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
pytest                                         # all tests
pytest tests/scraping/                         # one module
pytest --cov=src                               # with coverage
```

### Loading fixtures (offline development)

```bash
python load_fixtures.py
```

Reads `fixtures/*_detail.html`, parses them through the real parser, inserts into the database. Useful when the live site is unavailable.

---

## What's Left

According to the project timeline:

1. **Flask server** (Week 4) — `src/server/`, endpoints for `/graph`, `/course/<code>`, `/search`, `/prerequisites/<code>`
2. **Frontend graph visualization** (Week 5) — vis.js, color-coded by course level
3. **Search and detail panel** (Week 6) — search bar, clickable nodes, filter controls
4. **Polish + full-university data** (Week 7)
5. **Demo prep** (Week 8)

Don't proactively touch the existing scraping/storage/graph code unless asked — those layers are stable, tested, and the developer wants to focus on the web layer.

---

## How to be useful here

- **Respect the layered architecture.** Don't put SQL outside CacheManager. Don't put network code outside CatalogFetcher. Don't put graph algorithms in CourseGraph.
- **Match the existing style.** Sectional comment dividers (`# ─── Section ───`), descriptive docstrings, type hints, conservative formatting.
- **Suggest before doing.** The developer prefers discussing design tradeoffs before implementation, especially for non-trivial changes. Ask clarifying questions when scope is ambiguous.
- **Be direct about bugs and tradeoffs.** This project has benefited from honest pushback on bad ideas. Don't gloss over real problems.
- **Don't add features beyond what was asked.** The scope of this project is deliberately bounded.