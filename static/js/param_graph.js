(function(){
  const CY_ID = "cy";
  const API_BASE = "/api/param-graph/";                           
  const btnReload = document.getElementById("btn-reload");
  const toggleRank = document.getElementById("toggle-rank");
  const metaBox = document.getElementById("meta");
  const langSelect = document.getElementById("lang-select");       

  let ro = null;
  let resizeHandler = null;

  function edgesToElements(edges) {
    return (edges || []).map(e => ({ data: { id: e.source + "->" + e.target, source: e.source, target: e.target }}));
  }

  function normalizeElements(payload) {
    if (payload.nodes && payload.nodes[0] && payload.nodes[0].data) {
      return { nodes: payload.nodes, edges: edgesToElements(payload.edges) };  
    }
    const nodes = (payload.nodes || []).map(n => ({
      data: {
        id: n.id, label: n.label, rank: n.rank,
        cond: n.cond, cond_human: n.cond_human
      }
    }));
    return { nodes, edges: edgesToElements(payload.edges) };
  }

  function layoutFor(cy, layered) {
    if (!layered) return cy.layout({ name: "cose", animate: true, fit: true });
    return cy.layout({
      name: "breadthfirst", directed: true, padding: 30,
      avoidOverlap: true, spacingFactor: 1.2, animate: true,
      roots: cy.nodes().filter(n => n.indegree() === 0).map(n => n.id()),
    });
  }

  function debounce(fn, wait){ let t; return () => { clearTimeout(t); t=setTimeout(fn,wait); }; }

  function endpointForCurrentLang() {
    const lang = langSelect && langSelect.value ? langSelect.value.trim() : "";
    return lang ? `${API_BASE}lang/${encodeURIComponent(lang)}/` : API_BASE;
  }

  async function render() {
    if (ro) { try{ ro.disconnect(); }catch{} ro = null; }
    if (resizeHandler) { window.removeEventListener("resize", resizeHandler); resizeHandler = null; }

    metaBox.textContent = "Loading…";
    const url = endpointForCurrentLang();                            
    const resp = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!resp.ok) { metaBox.textContent = "Error loading graph."; return; }
    const payload = await resp.json();

    const container = document.getElementById(CY_ID);
    container.innerHTML = "";


    const { nodes, edges } = normalizeElements(payload);

    const cy = cytoscape({
      container,
      elements: { nodes, edges },
      wheelSensitivity: 0.2,
      pixelRatio: 1, 
      style: [
        { selector: "node", style: {
            "label": "data(label)",
            "text-valign": "center",
            "color": "#222",                                
            "background-color": "data(color)",            
            "border-color": "#999", "border-width": 1,
            "width": "label", "height": "label",
            "padding": "6px", "shape": "round-rectangle",
            "font-size": 12
        }},
        { selector: "node[!color]", style: { "background-color": "#999" } },  
        { selector: "edge", style: {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#999",
            "line-color": "#999", "width": 1.2
        }},
        { selector: "node.highlight", style: { "background-color": "#f39c12" }},
        { selector: "edge.highlight-in",  style: { "line-color": "#3498db", "target-arrow-color": "#3498db", "width": 1.6 }},
        { selector: "node.highlight-in",  style: { "background-color": "#3498db" }},
        { selector: "edge.highlight-out", style: { "line-color": "#e67e22", "target-arrow-color": "#e67e22", "width": 1.6 }},
        { selector: "node.highlight-out", style: { "background-color": "#e67e22" }},
      ]
    });

    if (payload.meta && payload.meta.language) {
      const c = payload.meta.counts || {};
      metaBox.textContent = `${payload.meta.language.id} — ${c["+"]||0}\n “+”, ${c["-"]||0}\n “–”, ${c["0"]||0} \n“0”, ${c.unset||0} unset`;
    } else if (payload.meta) {
      metaBox.textContent = `${payload.meta.active_count} active parameters • ${payload.meta.has_edges ? 'with' : 'no'} relations`;
    } else {
      metaBox.textContent = "";
    }

    const doFit = () => { cy.resize(); cy.fit(cy.elements(), 30); };
    cy.once("layoutstop", () => setTimeout(doFit, 0));
    layoutFor(cy, toggleRank.checked).run();
    requestAnimationFrame(doFit);
    setTimeout(doFit, 0);

    const onResize = debounce(doFit, 120);
    window.addEventListener("resize", onResize);
    resizeHandler = onResize;
    if (window.ResizeObserver) {
      ro = new ResizeObserver(onResize);
      ro.observe(container);
    }

cy.on("tap", "node", (evt) => {
  const n = evt.target;
  const cond = n.data("cond_human") || n.data("cond") || "(no condition)";
  const hasLang = !!(payload.meta && payload.meta.language);

  if (!hasLang) {
    cy.elements().removeClass("highlight highlight-in highlight-out");
    n.addClass("highlight");
    n.outgoers("edge").addClass("highlight-out");
    n.outgoers("node").addClass("highlight-out");
    n.incomers("edge").addClass("highlight-in");
    n.incomers("node").addClass("highlight-in");
  } else {
    cy.elements().removeClass("highlight highlight-in highlight-out");
  }

  const val = n.data("value");
  if (hasLang) {
    metaBox.innerText = `${n.id()} — value: ${val || "unset"}`;
  } else {
    const fmt = (node) => node.id();
    const uniqSort = (arr) => Array.from(new Set(arr)).sort();
    const incoming = uniqSort(n.incomers("node").map(fmt));
    const outgoing = uniqSort(n.outgoers("node").map(fmt));
    const fromTxt = incoming.length ? incoming.join(", ") : "—";
    const toTxt   = outgoing.length ? outgoing.join(", ") : "—";
    metaBox.innerText = `${n.id()} — ${cond}\n← from: ${fromTxt}\n→ to: ${toTxt}`;
  }
});



    cy.on("dbltap", "node", (evt) => {
      const n = evt.target;
      cy.elements().removeClass("highlight highlight-in highlight-out");
      n.closedNeighborhood().addClass("highlight");
    });

    btnReload.onclick = render;
    toggleRank.onchange = () => {
      const l = layoutFor(cy, toggleRank.checked);
      cy.once("layoutstop", doFit);
      l.run();
    };
  }

  document.addEventListener("DOMContentLoaded", () => {
    render();
    if (langSelect) langSelect.addEventListener("change", render);  
  });
})();
