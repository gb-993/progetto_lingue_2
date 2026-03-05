(function () {
  const modeLang = document.getElementById("lang-mode");
  if (!modeLang) return;
  const grid = document.getElementById("param-grid");
  const title = document.getElementById("lang-title");

  function cls(v, active) {
    if (!active) return "card-inactive";
    switch (String(v)) {
      case "+":
        return "card-plus";
      case "-":
        return "card-minus";
      case "0":
        return "card-zero";
      default:
        return "card-unset";
    }
  }


  function render(language, values) {
    title.textContent = `${language.id} — ${language.name}`;
    grid.innerHTML = "";
    const frag = document.createDocumentFragment();
    values.forEach(item => {
      const el = document.createElement("div");
      el.className = `param-card ${cls(item.final, item.active)}`;
      el.setAttribute("role", "listitem");
      el.innerHTML = `
        <div class="pid" style="font-weight:600;">${item.id}</div>
        <span class="label" style="display:block;font-size:.9rem;color:var(--muted,#555);">${item.label || ""}</span>
        <div class="status" style="font-variant-numeric:tabular-nums;"><strong>final:</strong> ${item.final || "unset"}${item.active ? "" : " • inactive"}</div>
      `;
      frag.appendChild(el);
    });
    grid.appendChild(frag);
  }

  function load(langId) {
    if (!langId) return;
    fetch(`/graphs/api/lang-values.json?lang=${encodeURIComponent(langId)}`, { credentials: "same-origin" })
      .then(r => r.json())
      .then(payload => render(payload.language, payload.values))
      .catch(console.error);
  }

  window.ParamLangView = { load };
})();
