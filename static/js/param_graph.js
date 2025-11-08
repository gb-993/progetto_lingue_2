(function () {
  const langSelect = document.getElementById("lang-select");
  const reloadBtn = document.getElementById("reloadBtn");
  const modeGraph = document.getElementById("graph-mode");
  const modeLang = document.getElementById("lang-mode");
  if (!modeGraph) return;

  function swapMode(useLang) {
    modeGraph.hidden = !!useLang;
    modeLang.hidden = !useLang;
  }
  swapMode(!!langSelect.value);

  langSelect.addEventListener("change", () => {
    const hasLang = !!langSelect.value;
    swapMode(hasLang);
    if (hasLang) window.ParamLangView.load(langSelect.value);
  });
  reloadBtn.addEventListener("click", () => {
    if (langSelect.value) window.ParamLangView.load(langSelect.value, true);
    else fetchGraph(true);
  });

  const recapName = document.getElementById("recap-name");
  const recapUp = document.getElementById("recap-up");
  const recapDown = document.getElementById("recap-down");
  let cy;

  function fetchGraph(force) {
    if (cy && !force) return;
    fetch("/graphs/api/graph.json", { credentials: "same-origin" })
      .then(r => r.json())
      .then(initCytoscape)
      .catch(console.error);
  }

  function initCytoscape(data) {
    const container = document.getElementById("cy-container");
    if (!container) return;
    if (cy) { cy.destroy(); cy = null; }

    cy = cytoscape({
      container,
      elements: { nodes: data.nodes, edges: data.edges },
      wheelSensitivity: 0.15,
      pixelRatio: 1,
      layout: { name: "breadthfirst", directed: true, spacingFactor: 1.2, padding: 20 },

      style: [
        { selector: "node", style: {
            "background-color": "#90a4ae",
            "label": "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 120,
            "font-size": 12,
            "text-valign": "center",
            "text-halign": "center",
            "color": "#000",
            "width": "label",
            "height": "label",
            "padding": "8px",
            "shape": "round-rectangle",
            "border-width": 1,
            "border-color": "#455a64",
        }},
        { selector: "edge", style: {
            "line-color": "#90a4ae",
            "target-arrow-color": "#90a4ae",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "width": 1.5
        }},
        { selector: ".focus",  style: { "background-color": "#ffdd66", "border-color": "#b18a00" } },
        { selector: ".up",     style: { "background-color": "#8bb6ff", "border-color": "#2c6bed" } },
        { selector: ".down",   style: { "background-color": "#ffcaa6", "border-color": "#e57a2e" } },
        { selector: ".dimmed", style: { "opacity": 0.2 } }
      ]
    });

    const ro = new ResizeObserver(() => cy.resize());
    ro.observe(container);

    function clearHL() { cy.elements().removeClass("focus up down dimmed"); }
    function updateRecap(title, upIds, downIds) {
      recapName.textContent = title || "None";
      recapUp.innerHTML = "";
      recapDown.innerHTML = "";
      const add = (ul, id) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = "#"; a.textContent = id; a.className = "recap-link";
        a.addEventListener("click", e => {
          e.preventDefault();
          const n = cy.getElementById(id);
          if (n.nonempty()) { cy.center(n); cy.animate({ fit: { eles: n, padding: 60 }, duration: 250 }); selectNode(n); }
        });
        li.appendChild(a); ul.appendChild(li);
      };
      upIds.forEach(id => add(recapUp, id));
      downIds.forEach(id => add(recapDown, id));
    }

    function selectNode(node) {
      clearHL();
      const up = node.incomers("node");
      const down = node.outgoers("node");
      node.addClass("focus"); up.addClass("up"); down.addClass("down");
      const others = cy.nodes().not(up).not(down).not(node);
      others.addClass("dimmed");
      cy.edges().forEach(e => {
        const src = e.source(), trg = e.target();
        if (!(src.hasClass("focus") || src.hasClass("up") || src.hasClass("down")
           || trg.hasClass("focus") || trg.hasClass("up") || trg.hasClass("down"))) e.addClass("dimmed");
      });
      updateRecap(node.id(), up.map(n=>n.id()).sort(), down.map(n=>n.id()).sort());
    }

    cy.on("tap", "node", evt => selectNode(evt.target));
    cy.on("tap", evt => { if (evt.target === cy) { clearHL(); updateRecap("None", [], []); }});

    cy.fit(undefined, 5);              // usa quasi tutto il canvas
    cy.zoom(cy.zoom() * 1.6);    }

  fetchGraph(false);
})();
