/* parameter_edit.js
   - Change tracking dei campi chiave del form
   - Blocca il tasto "Save" se:
        a) ci sono modifiche ai campi tracciati, OPPURE
        b) la pagina è marcata come "external dirty" (domande / motivations cambiate altrove),
     E in entrambi i casi la change note è vuota.
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

  // elenco dei nomi campo da tracciare (array JSON in stringa)
  var trackedAttr = form.getAttribute("data-tracked") || "[]";
  var tracked;
  try { tracked = JSON.parse(trackedAttr); } catch (e) { tracked = []; }

  // flag esterno (es. sei rientrato dopo aver aggiunto/modificato/eliminato domande/motivations)
  var externalDirty = form.getAttribute("data-external-dirty") === "true";

  function getValByName(name) {
    var els = form.elements[name];
    if (!els) return null;
    var el = (typeof els.length === "number") ? els[0] : els;
    if (!el) return null;
    if (el.type === "checkbox") return el.checked;
    return el.value;
  }

  // Snapshot iniziale dei campi del parametro
  var initial = {};
  tracked.forEach(function (n) {
    initial[n] = getValByName(n);
  });

  function hasInternalChanges() {
    return tracked.some(function (n) {
      return getValByName(n) !== initial[n];
    });
  }

  function pageIsDirty() {
    // sporca se:
    // - hai cambiato i campi del parametro
    // - OPPURE sei tornato con externalDirty=true (cioè hai toccato domande/motivations)
    return externalDirty || hasInternalChanges();
  }

  function updateSaveState() {
    if (!saveBtn) return;

    var dirty = pageIsDirty();
    var missingNote = requiresNote && dirty && (!noteEl || !noteEl.value || !noteEl.value.trim());

    saveBtn.disabled = !!missingNote;
    if (missingNote) {
      saveBtn.classList.add("btn--disabled");
      saveBtn.setAttribute("aria-disabled", "true");
      saveBtn.title = "Impossibile salvare finché non inserisci le note delle modifiche.";
      if (hint) hint.classList.add("b-bad");
    } else {
      saveBtn.classList.remove("btn--disabled");
      saveBtn.setAttribute("aria-disabled", "false");
      saveBtn.title = "";
      if (hint) hint.classList.remove("b-bad");
    }
  }

  // Riascolta input e change sul form, così se scrivi la nota sblocca
  form.addEventListener("input", updateSaveState);
  form.addEventListener("change", updateSaveState);

  // Init stato
  updateSaveState();
})();
