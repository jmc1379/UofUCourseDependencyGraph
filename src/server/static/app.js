const container = document.getElementById("network");
const input = document.getElementById("course-code");
const button = document.getElementById("load-btn");
const searchResults = document.getElementById("search-results");
const levelFilterGroup = document.getElementById("level-filters");
const deptFilterGroup = document.getElementById("department-filters");

const detailPanel = document.getElementById("detail-panel");
const detailClose = document.getElementById("detail-close");
const detailCode = document.getElementById("detail-code");
const detailName = document.getElementById("detail-name");
const detailUnits = document.getElementById("detail-units");
const detailDepartment = document.getElementById("detail-department");
const detailStatus = document.getElementById("detail-status");
const detailDescription = document.getElementById("detail-description");
const detailPrereqs = document.getElementById("detail-prereqs");

// Course-level palette, matched to the U of U secondary brand colors.
const LEVELS = [
  { key: "1000", label: "1000s", color: "#3ABFC0" },
  { key: "2000", label: "2000s", color: "#6CC24A" },
  { key: "3000", label: "3000s", color: "#FFB81D" },
  { key: "4000", label: "4000s", color: "#708E99" },
  { key: "5000+", label: "5000+", color: "#890000" },
  { key: "other", label: "Other", color: "#707271" },
];
const LEVEL_COLOR = Object.fromEntries(LEVELS.map(l => [l.key, l.color]));

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let searchTimeout = null;

// Raw graph last fetched from the API, used to recompute filters without a refetch.
let rawNodes = [];
let activeLevels = new Set(LEVELS.map(l => l.key));
let activeDepartments = new Set();

// ─── Data loading ────────────────────────────────────────────────────────────

async function loadPrerequisites(courseCode) {
  searchResults.innerHTML = "";
  const response = await fetch(`/api/prerequisites/${courseCode}`);
  if (!response.ok) {
    alert(`Course not found: ${courseCode}`);
    return;
  }
  const data = await response.json();
  rawNodes = data.nodes;
  activeDepartments = new Set(rawNodes.map(n => n.department).filter(Boolean));
  renderDepartmentFilters();
  render(data);
  hideDetailPanel();
}

async function loadCourseDetail(courseCode) {
  const response = await fetch(`/api/course/${courseCode}`);
  if (!response.ok) return;
  showDetailPanel(await response.json());
}

async function runSearch(query) {
  const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  renderSearchResults(await response.json());
}

function renderSearchResults(courses) {
  searchResults.innerHTML = "";
  for (const course of courses) {
    const item = document.createElement("div");
    item.className = "search-result";
    item.textContent = `${course.code} — ${course.name}`;
    item.addEventListener("click", () => {
      searchResults.innerHTML = "";
      input.value = course.code;
      loadPrerequisites(course.code);
    });
    searchResults.appendChild(item);
  }
}

// ─── Graph rendering ─────────────────────────────────────────────────────────

function nodeColor(level) {
  const bg = LEVEL_COLOR[level] || LEVEL_COLOR.other;
  return { background: bg, border: bg, highlight: { background: bg, border: darken(bg) } };
}

function darken(hex) {
  // Cheap darken for the highlight border — good enough for a handful of brand hexes.
  const n = parseInt(hex.slice(1), 16);
  const r = Math.max(0, (n >> 16) - 40);
  const g = Math.max(0, ((n >> 8) & 0xff) - 40);
  const b = Math.max(0, (n & 0xff) - 40);
  return `rgb(${r}, ${g}, ${b})`;
}

function isNodeVisible(node) {
  return activeLevels.has(node.courseLevel) && activeDepartments.has(node.department);
}

function render(data) {
  const nodes = data.nodes.map(node => ({
    ...node,
    color: nodeColor(node.courseLevel),
    font: { color: "#ffffff", face: "Arial", size: 14 },
    hidden: !isNodeVisible(node),
  }));

  nodesDataSet = new vis.DataSet(nodes);
  edgesDataSet = new vis.DataSet(data.edges);

  if (network) {
    network.setData({ nodes: nodesDataSet, edges: edgesDataSet });
  } else {
    network = new vis.Network(container, { nodes: nodesDataSet, edges: edgesDataSet }, {
      layout: { hierarchical: { direction: "UD", sortMethod: "directed" } },
      // Hierarchical layout already positions nodes deterministically; physics
      // left on can fling small graphs to extreme coordinates off-canvas.
      physics: false,
      nodes: {
        shape: "box",
        shapeProperties: { borderRadius: 6 },
        margin: 8,
      },
      edges: {
        arrows: "to",
        color: { color: "#444444", highlight: "#BE0000" },
      },
    });
    network.on("click", params => {
      if (params.nodes.length) {
        loadCourseDetail(params.nodes[0]);
      } else {
        hideDetailPanel();
      }
    });
  }
}

function applyFilters() {
  if (!nodesDataSet) return;
  nodesDataSet.update(rawNodes.map(node => ({ id: node.id, hidden: !isNodeVisible(node) })));
}

// ─── Filter chips ────────────────────────────────────────────────────────────

function renderLevelFilters() {
  for (const level of LEVELS) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `<span class="swatch" style="background:${level.color}"></span>${level.label}`;
    chip.addEventListener("click", () => {
      if (activeLevels.has(level.key)) {
        activeLevels.delete(level.key);
      } else {
        activeLevels.add(level.key);
      }
      chip.classList.toggle("off", !activeLevels.has(level.key));
      applyFilters();
    });
    levelFilterGroup.appendChild(chip);
  }
}

function renderDepartmentFilters() {
  deptFilterGroup.querySelectorAll(".dept-chip").forEach(el => el.remove());
  const departments = [...new Set(rawNodes.map(n => n.department).filter(Boolean))].sort();

  for (const dept of departments) {
    const chip = document.createElement("span");
    chip.className = "chip dept-chip active";
    chip.textContent = dept;
    chip.addEventListener("click", () => {
      if (activeDepartments.has(dept)) {
        activeDepartments.delete(dept);
      } else {
        activeDepartments.add(dept);
      }
      chip.classList.toggle("active", activeDepartments.has(dept));
      applyFilters();
    });
    deptFilterGroup.appendChild(chip);
  }
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function showDetailPanel(course) {
  detailCode.textContent = course.code;
  detailName.textContent = course.name;
  detailUnits.textContent = course.units;
  detailDepartment.textContent = course.department;
  detailStatus.textContent = course.is_active ? "Active" : "Inactive";
  detailDescription.textContent = course.description || "No description available.";
  detailPrereqs.textContent = course.raw_prerequisites || "None";
  detailPanel.hidden = false;
}

function hideDetailPanel() {
  detailPanel.hidden = true;
}

// ─── Wiring ──────────────────────────────────────────────────────────────────

detailClose.addEventListener("click", hideDetailPanel);

button.addEventListener("click", () => loadPrerequisites(input.value.trim().toUpperCase()));

input.addEventListener("input", () => {
  clearTimeout(searchTimeout);
  const query = input.value.trim();
  if (!query) {
    searchResults.innerHTML = "";
    return;
  }
  searchTimeout = setTimeout(() => runSearch(query), 200);
});

renderLevelFilters();
loadPrerequisites(input.value);
