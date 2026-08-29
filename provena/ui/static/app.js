// Provena frontend: render the claim-to-source graph and reflect live cascade flags.
// Polls /api/graph; stale claims render red. Click a node to inspect its provenance.

const COLORS = (() => {
  const dark = matchMedia("(prefers-color-scheme: light)").matches === false;
  return dark
    ? { claim: "#8985ff", source: "#2dc79a", stale: "#ff5c5c", edge: "#3a3a44", ink: "#f5f5f7", muted: "#a1a1a8" }
    : { claim: "#5e5ce6", source: "#10a37f", stale: "#d63333", edge: "#c9c9d0", ink: "#1d1d1f", muted: "#6e6e73" };
})();

let network = null;
const nodes = new vis.DataSet([]);
const edges = new vis.DataSet([]);

function initNetwork() {
  const container = document.getElementById("graph");
  network = new vis.Network(container, { nodes, edges }, {
    autoResize: true,
    layout: { hierarchical: { direction: "LR", sortMethod: "hubsize", levelSeparation: 160 } },
    physics: { enabled: false },
    interaction: { hover: true, tooltipDelay: 120 },
    edges: {
      arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      smooth: { type: "cubicBezier", forceDirection: "horizontal", roundness: 0.5 },
      color: { color: COLORS.edge, highlight: COLORS.claim },
    },
    nodes: { shape: "box", margin: 12, font: { face: "Inter, sans-serif", size: 13 } },
  });
  network.on("click", (params) => {
    const id = params.nodes[0];
    if (id) renderTrace(id);
  });
}

function claimColor(status) {
  return status === "stale" ? COLORS.stale : COLORS.claim;
}

function renderGraph(data) {
  const claimIds = new Set(data.claims.map((c) => c.id));
  const nextNodes = [];

  for (const c of data.claims) {
    const color = claimColor(c.status);
    nextNodes.push({
      id: c.id,
      label: c.text.length > 60 ? c.text.slice(0, 57) + "…" : c.text,
      group: "claim",
      color: { background: color, border: color, highlight: { background: color, border: color } },
      font: { color: "#ffffff", face: "Inter, sans-serif", size: 13 },
      title: `${c.id}\n[${c.status}] ${c.text}`,
    });
  }
  for (const s of data.sources) {
    nextNodes.push({
      id: s.source_id,
      label: s.summary,
      group: "source",
      shape: "ellipse",
      color: { background: COLORS.source, border: COLORS.source },
      font: { color: "#ffffff", face: "Inter, sans-serif", size: 12 },
      title: `${s.kind} source\n${s.summary}\nhash ${s.content_hash.slice(0, 10)}`,
    });
  }

  const nextEdges = [];
  for (const e of data.edges.grounded_on) {
    nextEdges.push({ from: e.claim, to: e.source, id: `g:${e.claim}:${e.source}`,
                     dashes: false, color: { color: COLORS.source, opacity: 0.7 } });
  }
  for (const e of data.edges.depends_on) {
    nextEdges.push({ from: e.from, to: e.to, id: `d:${e.from}:${e.to}`,
                     dashes: true, color: { color: COLORS.edge } });
  }

  // Full re-sync (simple and correct at demo scale).
  nodes.clear();
  edges.clear();
  nodes.add(nextNodes);
  edges.add(nextEdges);
}

async function fetchGraph() {
  const res = await fetch("/api/graph");
  return res.json();
}

async function tick() {
  try {
    const data = await fetchGraph();
    renderGraph(data);
    const stale = data.claims.filter((c) => c.status === "stale").length;
    document.getElementById("status-text").textContent =
      stale > 0 ? `${stale} stale claim(s)` : "live";
    document.querySelector("header .dot").style.background =
      stale > 0 ? COLORS.stale : COLORS.source;
  } catch (err) {
    document.getElementById("status-text").textContent = "disconnected";
  }
}

async function renderTrace(claimId) {
  const aside = document.getElementById("trace");
  aside.innerHTML = '<h2>Inspect</h2><div class="trace-empty">loading…</div>';
  try {
    const res = await fetch(`/api/trace/${encodeURIComponent(claimId)}`);
    if (!res.ok) throw new Error(String(res.status));
    const t = await res.json();
    const badge = t.claim.status === "stale"
      ? '<span class="badge stale">stale</span>'
      : '<span class="badge fresh">fresh</span>';
    let html = `<h2>Inspect ${badge}</h2>`;
    html += `<div class="trace-claim">${escapeHtml(t.claim.text)}</div>`;
    html += `<div class="trace-row">id: ${escapeHtml(t.claim.id)}</div>`;
    html += `<div class="trace-row"><b>grounded_on</b> (${t.grounded_sources.length})</div>`;
    for (const s of t.grounded_sources) {
      html += `<div class="trace-row">· ${escapeHtml(s.kind)} ${escapeHtml(s.summary)} <span class="trace-row">hash ${s.content_hash.slice(0, 10)}</span></div>`;
    }
    html += `<div class="trace-row"><b>depends_on</b> (${t.depends_on.length})</div>`;
    for (const d of t.depends_on) {
      html += `<div class="trace-row">· ${escapeHtml(d.id)} [${d.status}] ${escapeHtml(d.text)}</div>`;
    }
    aside.innerHTML = html;
  } catch (e) {
    aside.innerHTML = `<h2>Inspect</h2><div class="trace-empty">no provenance for ${escapeHtml(claimId)}</div>`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

initNetwork();
tick();
setInterval(tick, 1500);
