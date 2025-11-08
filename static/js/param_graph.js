(function () {
  const langSelect = document.getElementById("lang-select");
  const reloadBtn = document.getElementById("reloadBtn");
  const modeGraph = document.getElementById("graph-mode");
  const modeLang = document.getElementById("lang-mode");
  if (!modeGraph) return;

  const recapName = document.getElementById("recap-name");
  const recapUp = document.getElementById("recap-up");
  const recapDown = document.getElementById("recap-down");

  let cy;
  // lingua attualmente selezionata (null = nessuna lingua)
  let currentLangId = langSelect && langSelect.value ? langSelect.value : null;
  // valori della lingua corrente, usati per colorare i nodi
  let latestLangValues = null;

  // pulisce gli highlight implicazionali
  function clearHL() {
    if (!cy) return;
    cy.elements().removeClass("focus up down dimmed");
  }

  // aggiorna pannello "Selection"
  function updateRecap(title, upIds, downIds) {
    if (!recapName || !recapUp || !recapDown) return;
    recapName.textContent = title || "None";
    recapUp.innerHTML = "";
    recapDown.innerHTML = "";
    const add = (ul, id) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#";
      a.textContent = id;
      a.className = "recap-link";
      a.addEventListener("click", e => {
        e.preventDefault();
        if (!cy) return;
        const n = cy.getElementById(id);
        if (n.nonempty()) {
          cy.center(n);
          cy.animate({ fit: { eles: n, padding: 60 }, duration: 250 });
          selectNode(n);
        }
      });
      li.appendChild(a);
      ul.appendChild(li);
    };
    upIds.forEach(id => add(recapUp, id));
    downIds.forEach(id => add(recapDown, id));
  }

  // carica i valori per una lingua e applica i colori ai nodi
  function loadLangValues(langId) {
    if (!langId) return;
    fetch(`/graphs/api/lang-values.json?lang=${encodeURIComponent(langId)}`, {
      credentials: "same-origin",
    })
      .then(r => r.json())
      .then(payload => {
        latestLangValues = payload.values || [];
        applyLangColors();
      })
      .catch(console.error);
  }

  // applica le classi colore ai nodi in base a latestLangValues
  function applyLangColors() {
    if (!cy) return;

    cy.nodes().removeClass("val-plus val-minus val-zero val-unset");

    if (!currentLangId || !latestLangValues) {
      // nessuna lingua selezionata -> nessun colore speciale
      return;
    }

    const map = Object.create(null);
    latestLangValues.forEach(v => {
      map[v.id] = v.final || "";
    });

    cy.nodes().forEach(n => {
      const v = map[n.id()] || "";
      if (v === "+") n.addClass("val-plus");
      else if (v === "-") n.addClass("val-minus");
      else if (v === "0") n.addClass("val-zero");
      else n.addClass("val-unset");
    });
  }

  // cambio lingua: aggiorna visibilità card + colori grafico
  langSelect.addEventListener("change", () => {
    const hasLang = !!langSelect.value;
    currentLangId = hasLang ? langSelect.value : null;

    // mostra/nasconde la griglia a card sotto
    if (modeLang) modeLang.hidden = !hasLang;

    // reset highlight implicazionale
    clearHL();
    updateRecap("None", [], []);

    if (hasLang) {
      if (window.ParamLangView) {
        window.ParamLangView.load(currentLangId);
      }
      loadLangValues(currentLangId);
    } else {
      latestLangValues = null;
      applyLangColors(); // rimuove val-*
    }
  });

  // pulsante reload
  reloadBtn.addEventListener("click", () => {
    if (currentLangId) {
      if (window.ParamLangView) {
        window.ParamLangView.load(currentLangId, true);
      }
      loadLangValues(currentLangId);
    } else {
      fetchGraph(true);
    }
  });

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
    if (cy) {
      cy.destroy();
      cy = null;
    }

    cy = cytoscape({
      container,
      elements: { nodes: data.nodes, edges: data.edges },
      wheelSensitivity: 0.15,
      pixelRatio: 1,
      layout: { name: "breadthfirst", directed: true, spacingFactor: 1.2, padding: 20 },

      style: [
        {
          selector: "node",
          style: {
            "background-color": "#ECEFF1",      // default (nessuna lingua)
            "label": "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 120,
            "font-size": 14,
            "text-valign": "center",
            "text-halign": "center",
            "color": "#000000",               
            "width": "label",
            "height": "label",
            "padding": "8px",
            "shape": "round-rectangle",
            "border-width": 1,
            "border-color": "#000000",       
          },
        },
        {
          selector: "edge",
          style: {
            "line-color": "#90A4AE",
            "target-arrow-color": "#90A4AE",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "width": 1.5,
          },
        },

        {
          selector: "edge",
          style: {
            "line-color": "#90a4ae",
            "target-arrow-color": "#90a4ae",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "width": 1.5,
          },
        },

        { 
          selector: ".val-plus",
          style: {
            "background-color": "#1B5E20",   
            "border-color": "#0B3D13",
            "color": "#FFFFFF"
          }
        },
        {
          selector: ".val-minus",
          style: {
            "background-color": "#B71C1C",  
            "border-color": "#7F0000",
            "color": "#FFFFFF"
          }
        },
        {
          selector: ".val-zero",
          style: {
            "background-color": "#0D47A1",  
            "border-color": "#002171",
            "color": "#FFFFFF"
          }
        },
        {
          selector: ".val-unset",
          style: {
            "background-color": "#FAFAFA",   
            "border-color": "#BDBDBD",
            "color": "#000000"
          }
        },

        // highlight implicazionale (solo quando non c'è lingua selezionata)
        {
          selector: ".focus",
          style: {
            "background-color": "#FFEB3B",   
            "border-color": "#F57F17",
            "color": "#000000"
          }
        },
        {
          selector: ".up",
          style: {
            "background-color": "#4CAF50",   
            "border-color": "#1B5E20",
            "color": "#FFFFFF"
          }
        },
        {
          selector: ".down",
          style: {
            "background-color": "#FF9800",   
            "border-color": "#EF6C00",
            "color": "#FFFFFF"
          }
        },
        {
          selector: ".dimmed",
          style: { "opacity": 0.2 }
        },

      ],
    });

    const ro = new ResizeObserver(() => cy.resize());
    ro.observe(container);

    function selectNode(node) {
      clearHL();

      if (currentLangId) {
        // con lingua selezionata: niente implicants/implicated,
        updateRecap(node.id(), [], []);
        return;
      }

      const up = node.incomers("node");
      const down = node.outgoers("node");
      node.addClass("focus");
      up.addClass("up");
      down.addClass("down");
      const others = cy.nodes().not(up).not(down).not(node);
      others.addClass("dimmed");
      cy.edges().forEach(e => {
        const src = e.source(),
          trg = e.target();
        if (
          !(
            src.hasClass("focus") ||
            src.hasClass("up") ||
            src.hasClass("down") ||
            trg.hasClass("focus") ||
            trg.hasClass("up") ||
            trg.hasClass("down")
          )
        )
          e.addClass("dimmed");
      });
      updateRecap(
        node.id(),
        up.map(n => n.id()).sort(),
        down.map(n => n.id()).sort()
      );
    }

    cy.on("tap", "node", evt => selectNode(evt.target));
    cy.on("tap", evt => {
      if (evt.target === cy) {
        clearHL();
        updateRecap("None", [], []);
      }
    });

    cy.fit(undefined, 5);
    cy.zoom(cy.zoom() * 1.6);

    // se c'è già una lingua selezionata applica subito i colori
    if (currentLangId && latestLangValues) {
      applyLangColors();
    }
  }

  // inizializza:
  // - grafo
  // - eventuale lingua pre-selezionata
  fetchGraph(false);

  if (currentLangId) {
    if (modeLang) modeLang.hidden = false;
    if (window.ParamLangView) {
      window.ParamLangView.load(currentLangId);
    }
    loadLangValues(currentLangId);
  } else {
    if (modeLang) modeLang.hidden = true;
  }
})();
