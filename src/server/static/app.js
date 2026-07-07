const container = document.getElementById("network");
const input = document.getElementById("course-code");
const button = document.getElementById("load-btn");
const searchResults = document.getElementById("search-results");

let network = null;
let searchTimeout = null;

async function loadPrerequisites(courseCode) {
  const response = await fetch(`/api/prerequisites/${courseCode}`);
  if (!response.ok) {
    alert(`Course not found: ${courseCode}`);
    return;
  }
  render(await response.json());
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

function render(data) {
  const nodes = new vis.DataSet(data.nodes);
  const edges = new vis.DataSet(data.edges);

  if (network) {
    network.setData({ nodes, edges });
    return;
  }

  network = new vis.Network(container, { nodes, edges }, {
    layout: { hierarchical: { direction: "UD", sortMethod: "directed" } },
    nodes: {
      shape: "box",
      shapeProperties: { borderRadius: 6 },
      margin: 8,
      color: {
        background: "#CC0000",
        border: "#990000",
        highlight: { background: "#990000", border: "#660000" },
      },
      font: { color: "#ffffff", face: "Arial", size: 14 },
    },
    edges: {
      arrows: "to",
      color: { color: "#444444", highlight: "#CC0000" },
    },
  });
}

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

loadPrerequisites(input.value);
