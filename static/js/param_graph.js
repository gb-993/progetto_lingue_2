// static/js/param_graph.js
(function () {
  const CY_ID = "cy";
  // endpoint nuovo: /api/param-graph/<lang_id>/
  const API_LANG = (lang) => `/api/param-graph/${encodeURIComponent(lang)}/`;

  const btnReload = document.getElementById("btn-reload");
  const toggleRank = document.getElementById("toggle-rank");
  const metaBox = document.getElementById("meta");
  const langSelect = document.getElementById("lang-select");

  let cy = cytoscape({
    container: document.getElementById(CY_ID),
    elements: [],
    style: [
      {
        selector: "node",
        style: {
          "background-color": "data(color)", // [NUOVO] colore deciso dal backend
          "label": "data(label)",
          "text-wrap": "wrap",
          "text-max-width": 80,
          "font-size": 10,
          "color": "#fff",
          "text-valign": "center",
          "text-halign": "center",
          "width": 36,
          "height": 24,
          "border-width": 1,
          "border-color": "#444"
        }
      },
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
      {
        selector: "node:selected",
        style: { "border-width": 2, "border-color": "#000" }
      }
    ],
  });

  function toElements(payload) {
    const nodes = payload.nodes.map((n) => ({
      data: n.data
    }));
    const edges = payload.edges.map((e) => ({
      data: { id: e.data ? e.data.id : `${e.source}->${e.target}`, source: e.data ? e.data.source : e.source, target: e.data ? e.data.target : e.target }
    }));
    return { nodes, edges };
  }

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

  function renderMeta(meta) {
    if (!meta) { metaBox.textContent = ""; return; }
    const parts = [];
    if (meta.language) parts.push(`${meta.language.id} — ${meta.language.name}`);
    if (meta.counts) {
      parts.push(`+: ${meta.counts["+"]}`);
      parts.push(`–: ${meta.counts["-"]}`);
      parts.push(`0: ${meta.counts["0"]}`);
      if (meta.counts.unset) parts.push(`unset: ${meta.counts.unset}`);
    }
    metaBox.textContent = parts.join(" · ");
  }

  async function loadForLanguage(lang) {
    if (!lang) {
      cy.elements().remove();
      renderMeta(null);
      return;
    }
    const res = await fetch(API_LANG(lang), { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("Failed to load graph");
    const payload = await res.json();

    const { nodes, edges } = toElements(payload);

    cy.elements().remove();
    cy.add(nodes);
    cy.add(edges);

    // layout
    layoutFor(toggleRank.checked).run();

    // tooltips semplici via title (accessibile)
    cy.nodes().forEach((n) => {
      const d = n.data();
      const parts = [];
      parts.push(`${d.id} — ${d.name || ""}`);
      if (d.value) parts.push(`value: ${d.value}`);
      if (d.cond_human) parts.push(`cond: ${d.cond_human}`);
      n.qtip && n.qtip.destroy && n.qtip.destroy(); // no-op se non presente
      n.data("title", parts.join("\n"));
    });

    renderMeta(payload.meta);
  }

  // eventi UI
  btnReload?.addEventListener("click", () => {
    const lang = langSelect?.value || "";
    loadForLanguage(lang).catch(console.error);
  });

  toggleRank?.addEventListener("change", () => {
    layoutFor(toggleRank.checked).run();
  });

  langSelect?.addEventListener("change", () => {
    loadForLanguage(langSelect.value).catch(console.error);
  });

  // init: se c'è una lingua preselezionata
  if (langSelect && langSelect.value) {
    loadForLanguage(langSelect.value).catch(console.error);
  }
})();
