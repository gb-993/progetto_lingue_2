/*
   - Se NON ci sono modifiche (né interne né esterne) -> Save abilitato.
   - Se CI SONO modifiche o externalDirty=true -> change_note obbligatoria, Save disabilitato finché vuota.
*/

(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }

  var form = $("#param-edit-form");
  if (!form) return;

  var saveBtn = $("#saveBtn");
  var requiresNote = form.getAttribute("data-requires-change-note") === "true";

  var changeNoteName = form.getAttribute("data-change-note-name") || "change_note";
  var noteEl = form.elements[changeNoteName] || $("#id_change_note");
  var hint = $("#changeNoteHint");

  // external dirty (domande/motivations)
  var externalDirty = form.getAttribute("data-external-dirty") === "true";

  // --- Helper: normalizzazione valori per confronto robusto ---
  function norm(val) {
    if (Array.isArray(val)) return JSON.stringify(val.slice().sort());
    if (val === true || val === false || val === null || val === undefined) return String(val);
    // normalizza numeri rappresentati come stringhe "10" vs 10
    if (typeof val === "number") return String(val);
    return String(val);
  }

  // Ritorna tutti gli elementi con lo stesso name (NodeList -> Array)
  function allByName(name) {
    var list = form.querySelectorAll('[name="' + CSS.escape(name) + '"]');
    return Array.prototype.slice.call(list);
  }

  // Valore logico di un "gruppo" di controlli con lo stesso name
  function getValueByName(name) {
    var group = allByName(name);
    if (!group.length) return null;

    var type = (group[0].type || "").toLowerCase();
    var tag = (group[0].tagName || "").toLowerCase();

    // Radio group -> valore della radio selezionata o null
    if (type === "radio") {
      var checked = group.find(function (r) { return r.checked; });
      return checked ? checked.value : null;
    }

    // Checkbox: due casi
    // 1) una sola checkbox -> boolean
    // 2) più checkbox con stesso name -> array dei valori spuntati
    if (type === "checkbox") {
      if (group.length === 1) return !!group[0].checked;
      return group.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    }

    // Select (one/multiple)
    if (tag === "select") {
      var sel = group[0];
      if (sel.multiple) {
        return Array.prototype.filter.call(sel.options, function (o) { return o.selected; })
          .map(function (o) { return o.value; });
      }
      return sel.value;
    }

    // Input/textarea generici
    return group[0].value;
  }

  // --- Costruzione elenco dei nomi da monitorare ---
  var names = [];
  (function buildNames() {
    var trackedAttr = form.getAttribute("data-tracked") || "[]";
    var tracked = [];
    try { tracked = JSON.parse(trackedAttr); } catch (e) { tracked = []; }

    if (Array.isArray(tracked) && tracked.length) {
      names = tracked.slice();
    } else {
      // fallback: tutti i controlli con name, esclusa la change_note
      var all = form.querySelectorAll("input[name], select[name], textarea[name]");
      names = Array.prototype.slice.call(all)
        .map(function (el) { return el.name; })
        .filter(function (n) { return n && n !== changeNoteName; });
      // de-duplica
      names = Array.from(new Set(names));
    }
  })();

  // Snapshot iniziale
  var initial = {};
  names.forEach(function (n) { initial[n] = norm(getValueByName(n)); });

  function hasInternalChanges() {
    for (var i = 0; i < names.length; i++) {
      var n = names[i];
      var curr = norm(getValueByName(n));
      if (curr !== initial[n]) return true;
    }
    return false;
  }

  function pageIsDirty() {
    return externalDirty || hasInternalChanges();
  }

  function updateSaveState() {
    if (!saveBtn) return;

    var dirty = pageIsDirty();
    var noteText = (noteEl && noteEl.value) ? noteEl.value.trim() : "";
    var missingNote = requiresNote && dirty && !noteText;

    // Stato visivo + accessibile
    saveBtn.disabled = !!missingNote;
    saveBtn.setAttribute("aria-disabled", missingNote ? "true" : "false");

    if (missingNote) {
      saveBtn.classList.add("btn--disabled", "btn--locked");
      saveBtn.title = "You must describe your changes before saving.";
      if (hint) hint.classList.add("b-bad");
    } else {
      saveBtn.classList.remove("btn--disabled", "btn--locked");
      saveBtn.title = "";
      if (hint) hint.classList.remove("b-bad");
    }
  }

  // Event delegation: copre text, number, checkbox, radio, select(one/multiple), textarea
  form.addEventListener("input", updateSaveState, true);
  form.addEventListener("change", updateSaveState, true);

  // Stato iniziale coerente (abilitato se nessuna modifica; disabilitato se dirty senza nota)
  updateSaveState();
})();
