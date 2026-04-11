# UofU Course Dependency Graph

An extensible tool for scraping university course catalogs, building prerequisite dependency graphs and course similarity graphs, and rendering them as interactive visualizations.

Currently targets the **University of Utah** catalog, with architecture designed to support additional universities by adding new parser subclasses.

---

## Features

- Scrapes all courses for any department (or the entire university) from the U of U class schedule
- Parses prerequisite strings including AND/OR logic and cross-department references
- Builds a **prerequisite dependency graph** using a sparse adjacency matrix
- Builds a **course similarity graph** using TF-IDF cosine similarity on course descriptions
- Renders both as interactive, filterable HTML visualizations
- Caches scraped data in SQLite to avoid redundant network requests
- Concurrent scraping with rate limiting and per-course error tolerance

---

## Project Structure

```
UofUCourseDependencyGraph/
├── src/
│   ├── graph/
│   │   ├── CourseGraph.py          # sparse adjacency matrix graph structure
│   │   └── GraphAnalyzer.py        # traversal, similarity, and ranking algorithms
│   ├── models/
│   │   └── Course.py               # Course dataclass
│   ├── output/
│   │   └── WebsiteBuilder.py       # HTML graph renderer
│   ├── scraping/
│   │   ├── CatalogFetcher.py       # async HTTP fetching with rate limiting
│   │   └── CatalogParser.py        # abstract base + UofU concrete parser
│   └── storage/
│       ├── CacheManager.py         # SQLite read/write/invalidation
│       └── schema.sql              # database schema
├── tests/                          # mirrors src/ structure
├── fixtures/                       # saved HTML for parser unit tests
├── data/                           # generated: SQLite db, serialized graphs
├── output/                         # generated: HTML visualization files
├── main.py
├── requirements.txt
└── README.md
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
# Scrape and build graphs for all CS courses (uses cache if available)
python main.py --department CS

# Force re-scrape, ignoring cache
python main.py --department CS --refresh

# Run for the entire university (slow on first run)
python main.py --all

# Specify a custom output directory
python main.py --department CS --output ./my-output
```

Output files will appear in `output/`:
- `prerequisite_graph.html` — open in any browser
- `similarity_graph.html` — open in any browser

---

## Running Tests

```bash
pytest                          # run all tests
pytest --cov=src                # with coverage report
pytest tests/scraping/          # run a specific module's tests
```

---

## Adding Support for a New University

1. Create a new subclass of `CatalogParser` in `src/scraping/CatalogParser.py`
2. Implement the required interface methods (`get_course_list`, `parse_course_detail`, `parse_prerequisites`)
3. Save HTML fixture files for the new catalog in `fixtures/`
4. Write unit tests in `tests/scraping/`
5. Wire the new parser into `main.py` via a `--university` flag

No existing classes need to be modified.

---

## Contributing

See `CONTRIBUTING.md` for coding standards, branch naming conventions, and PR guidelines.

---

## License

MIT
