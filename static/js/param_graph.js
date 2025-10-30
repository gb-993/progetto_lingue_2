// static/js/param_graph.js
(function () {
  const CY_ID = "cy";

  // Endpoint base (grafo generico attivi) e per lingua (valori + / - / 0)
  const API_BASE = `/api/param-graph/`;
  const API_LANG = (lang) => `/api/param-graph/${encodeURIComponent(lang)}/`;

  const btnReload = document.getElementById("btn-reload");
  const toggleRank = document.getElementById("toggle-rank");
  const metaBox = document.getElementById("meta");
  const langSelect = document.getElementById("lang-select");

  let cy = cytoscape({
    container: document.getElementById(CY_ID),
    elements: [],
    style: [
      // NODI: ripristina forma “round-rectangle” e dimensioni maggiori
      {
        selector: "node",
        style: {
          "shape": "round-rectangle",
          "background-color": "data(color)",   // lingua: dal backend; generico: calcolato client
          "label": "data(label)",
          "text-wrap": "wrap",
          "text-max-width": 96,
          "font-size": 11,
          "color": "#fff",
          "text-valign": "center",
          "text-halign": "center",
          "width": 72,
          "height": 36,
          "border-width": 1,
          "border-color": "#444"
        }
      },
      // ARCHI
      {
        selector: "edge",
        style: {
          "width": 1.5,
          "line-color": "#888",
          "target-arrow-color": "#888",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier"
        }
      },
      // Selezione
      {
        selector: "node:selected",
        style: { "border-width": 2, "border-color": "#000" }
      }
    ],
    wheelSensitivity: 0.2
  });

  // Layout
  function layoutFor(layered) {
    if (!layered) return cy.layout({ name: "cose", animate: true, fit: true });
    return cy.layout({
      name: "breadthfirst",
      directed: true,
      padding: 30,
      avoidOverlap: true,
      fit: true
    });
  }

  // Util: costruisce elementi Cytoscape dal payload LINGUA (nodi già con data.*)
  function toElementsLang(payload) {
    const nodes = payload.nodes.map((n) => ({ data: n.data }));
    const edges = payload.edges.map((e) => ({
      data: {
        id: e.data ? e.data.id : `${e.source}->${e.target}`,
        source: e.data ? e.data.source : e.source,
        target: e.data ? e.data.target : e.target
      }
    }));
    return { nodes, edges };
  }

  // Util: costruisce elementi Cytoscape dal payload GENERICO (nodi flat)
  // Colori: arancione = sorgenti (solo uscenti), blu = dipendenti (hanno entranti), grigio = isolati
  function toElementsGeneric(payload) {
    const nodesFlat = payload.nodes || [];
    const edgesFlat = payload.edges || [];

    // calcola in/out-degree
    const outDeg = Object.create(null);
    const inDeg = Object.create(null);
    for (const n of nodesFlat) { outDeg[n.id] = 0; inDeg[n.id] = 0; }
    for (const e of edgesFlat) {
      outDeg[e.source] = (outDeg[e.source] || 0) + 1;
      inDeg[e.target] = (inDeg[e.target] || 0) + 1;
      if (!(e.source in inDeg)) inDeg[e.source] = inDeg[e.source] || 0;
      if (!(e.target in outDeg)) outDeg[e.target] = outDeg[e.target] || 0;
    }

    // palette
    const ORANGE = "#ef6c00";
    const BLUE   = "#1565c0";
    const GREY   = "#6c757d";

    const nodes = nodesFlat.map((n) => {
      const color = (outDeg[n.id] > 0 && inDeg[n.id] === 0) ? ORANGE
                   : (inDeg[n.id] > 0) ? BLUE
                   : GREY;
      return {
        data: {
          id: n.id,
          label: n.label || n.id,
          color,
          cond: n.cond || "",
          cond_human: n.cond_human || ""
        }
      };
    });

    const edges = edgesFlat.map((e) => ({
      data: { id: `${e.source}->${e.target}`, source: e.source, target: e.target }
    }));

    return { nodes, edges };
  }

  function renderMeta(meta) {
    if (!meta) { metaBox.textContent = ""; return; }
    const parts = [];
    if (meta.language) parts.push(`${meta.language.id} — ${meta.language.name}`);
    if (meta.counts) {
      parts.push(`+ ${meta.counts["+"]}  – ${meta.counts["-"]}  0 ${meta.counts["0"]}  unset ${meta.counts.unset}`);
    } else if (meta.active_count != null) {
      parts.push(`active: ${meta.active_count}`);
    }
    metaBox.textContent = parts.join(" | ");
  }

  // Carica grafo GENERICO (nessuna lingua selezionata)
  async function loadGeneric() {
    const res = await fetch(API_BASE, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("Failed to load generic graph");
    const payload = await res.json();

    const { nodes, edges } = toElementsGeneric(payload);

    cy.elements().remove();
    cy.add(nodes);
    cy.add(edges);

    layoutFor(toggleRank?.checked ?? true).run();

    // Tooltip base
    cy.nodes().forEach((n) => {
      const d = n.data();
      const t = [d.label, d.cond_human].filter(Boolean).join("\n");
      n.data("title", t);
    });

    renderMeta(payload.meta);
  }

  // Carica grafo per LINGUA (colori + / - / 0 dal backend)
  async function loadForLanguage(lang) {
    if (!lang) { return loadGeneric(); }
    const res = await fetch(API_LANG(lang), { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("Failed to load graph");
    const payload = await res.json();

    const { nodes, edges } = toElementsLang(payload);

    cy.elements().remove();
    cy.add(nodes);
    cy.add(edges);

    layoutFor(toggleRank?.checked ?? true).run();

    // Tooltip base
    cy.nodes().forEach((n) => {
      const d = n.data();
      const t = [d.label, d.cond_human, d.value ? `value: ${d.value}` : ""].filter(Boolean).join("\n");
      n.data("title", t);
    });

    renderMeta(payload.meta);
  }

  // Eventi UI
  btnReload?.addEventListener("click", () => {
    const lang = langSelect?.value || "";
    (lang ? loadForLanguage(lang) : loadGeneric()).catch(console.error);
  });

  toggleRank?.addEventListener("change", () => {
    layoutFor(toggleRank.checked).run();
  });

  langSelect?.addEventListener("change", () => {
    const lang = langSelect.value || "";
    (lang ? loadForLanguage(lang) : loadGeneric()).catch(console.error);
  });

  // Init: se c'è una lingua usa lingua, altrimenti grafo generico
  const initialLang = (langSelect && langSelect.value) ? langSelect.value : "";
  (initialLang ? loadForLanguage(initialLang) : loadGeneric()).catch(console.error);
})();
