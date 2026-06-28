const container = document.getElementById("network");
const input = document.getElementById("course-code");
const button = document.getElementById("load-btn");

let network = null;

async function loadPrerequisites(courseCode) {
  const response = await fetch(`/api/prerequisites/${courseCode}`);
  if (!response.ok) {
    alert(`Course not found: ${courseCode}`);
    return;
  }
  render(await response.json());
}

function render(data) {
  const nodes = new vis.DataSet(data.nodes);
  const edges = new vis.DataSet(data.edges);

  if (network) {
    network.setData({ nodes, edges });
    return;
  }

  network = new vis.Network(container, { nodes, edges }, {
    edges: { arrows: "to" },
    layout: { hierarchical: { direction: "UD", sortMethod: "directed" } },
  });
}

button.addEventListener("click", () => loadPrerequisites(input.value.trim().toUpperCase()));

loadPrerequisites(input.value);
