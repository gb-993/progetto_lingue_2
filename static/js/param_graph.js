// static/js/param_graph.js
(function(){
  const CY_ID = "cy";
  const API = "/api/param-graph/";
  const btnReload = document.getElementById("btn-reload");
  const toggleRank = document.getElementById("toggle-rank");
  const metaBox = document.getElementById("meta");

  // CHG: gestiamo un observer e handler globali per evitare leak tra reload
  let ro = null;               // ResizeObserver corrente
  let resizeHandler = null;    // listener window resize corrente

  function toElements(payload) {
    const nodes = payload.nodes.map(n => ({
      data: { id: n.id, label: n.label, rank: n.rank, cond: n.cond, cond_human: n.cond_human }
    }));
    const edges = payload.edges.map(e => ({
      data: { id: e.source + "->" + e.target, source: e.source, target: e.target }
    }));
    return { nodes, edges };
  }

  function layoutFor(cy, layered) {
    if (!layered) return cy.layout({ name: "cose", animate: true, fit: true });
    return cy.layout({
      name: "breadthfirst",
      directed: true,
      padding: 30,
      avoidOverlap: true,
      spacingFactor: 1.2,
      animate: true,
      roots: cy.nodes().filter(n => n.indegree() === 0).map(n => n.id()),
    });
  }

  // CHG: piccolo debounce per resize/observer
  function debounce(fn, wait) {
    let t; return function(){ clearTimeout(t); t = setTimeout(fn, wait); };
  }

  async function render() {
    // CHG: sgancia observer/handler precedenti per reload pulito
    if (ro) { try { ro.disconnect(); } catch(e) {} ro = null; }
    if (resizeHandler) { window.removeEventListener("resize", resizeHandler); resizeHandler = null; }

    metaBox.textContent = "Loading…";
    const resp = await fetch(API, { headers: { "Accept": "application/json" } });
    if (!resp.ok) { metaBox.textContent = "Errore nel caricamento del grafo."; return; }
    const payload = await resp.json();
    metaBox.textContent = `${payload.meta.active_count} parametri attivi • ${payload.meta.has_edges ? 'con' : 'senza'} relazioni`;

    const container = document.getElementById(CY_ID);
    container.innerHTML = "";

    const { nodes, edges } = toElements(payload);

    const cy = cytoscape({
      container,
      elements: { nodes, edges },
      wheelSensitivity: 0.2,
      style: [
        { selector: "node", style: {
            "label": "data(label)",
            "text-valign": "center",
            "color": "var(--text)",
            "background-color": "var(--surface-strong, #556)",
            "border-color": "var(--border, #999)",
            "border-width": 1,
            "width": "label",
            "height": "label",
            "padding": "6px",
            "shape": "round-rectangle",
            "font-size": 12
        }},
        { selector: "edge", style: {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "var(--border, #999)",
            "line-color": "var(--border, #999)",
            "width": 1.2
        }},
        { selector: "node.highlight", style: { "background-color": "#f39c12" }},
        { selector: "edge.highlight-in",  style: { "line-color": "#3498db", "target-arrow-color": "#3498db", "width": 1.6 }},
        { selector: "node.highlight-in",  style: { "background-color": "#3498db" }},
        { selector: "edge.highlight-out", style: { "line-color": "#e67e22", "target-arrow-color": "#e67e22", "width": 1.6 }},
        { selector: "node.highlight-out", style: { "background-color": "#e67e22" }},
      ]
    });

    // CHG: fit iniziale robusto (dopo layout + dopo paint)
    const doFit = () => { cy.resize(); cy.fit(cy.elements(), 30); }; // 30px padding
    cy.once("layoutstop", doFit);
    const layout = layoutFor(cy, toggleRank.checked);
    layout.run();
    requestAnimationFrame(doFit);

    // CHG: fit automatico su resize finestra e cambi dimensione contenitore
    resizeHandler = debounce(doFit, 120);
    window.addEventListener("resize", resizeHandler);
    if (window.ResizeObserver) {
      ro = new ResizeObserver(resizeHandler);
      ro.observe(container);
    }

    // Interazioni
    cy.on("tap", "node", (evt) => {
      const n = evt.target;
      const cond = n.data("cond_human") || n.data("cond") || "(no condition)";
      cy.elements().removeClass("highlight highlight-in highlight-out");
      n.addClass("highlight");
      n.outgoers("edge").addClass("highlight-out");
      n.outgoers("node").addClass("highlight-out");
      n.incomers("edge").addClass("highlight-in");
      n.incomers("node").addClass("highlight-in");
      metaBox.textContent = `${n.id()} — ${cond}`;
    });

    cy.on("dbltap", "node", (evt) => {
      const n = evt.target;
      cy.elements().removeClass("highlight highlight-in highlight-out");
      n.closedNeighborhood().addClass("highlight");
    });

    // Controls
    btnReload.onclick = () => render();
    toggleRank.onchange = () => {
      const l = layoutFor(cy, toggleRank.checked);
      cy.once("layoutstop", doFit); // CHG: rifit dopo cambio layout
      l.run();
    };
  }

  document.addEventListener("DOMContentLoaded", render);
})();
