/* parameter_edit.js
   Controllo del pulsante "Save":
   - Se NON ci sono modifiche (né interne né esterne) -> il bottone resta abilitato sempre.
     (Nessuna nota richiesta, perché non stai cambiando niente.)
   - Se CI SONO modifiche (campi del parametro cambiati oppure externalDirty=true),
     allora la nota di modifica (change_note) diventa obbligatoria:
        - finché la nota è vuota -> bottone Save disabilitato
        - quando la nota è compilata -> bottone Save abilitato
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

  // elenco campi tracciati dal parametro
  var trackedAttr = form.getAttribute("data-tracked") || "[]";
  var tracked;
  try { tracked = JSON.parse(trackedAttr); } catch (e) { tracked = []; }

  // flag esterno (domande/motivations modificate)
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

  // Pagina "dirty" = qualcosa è cambiato e quindi serve la nota prima di poter salvare
  function pageIsDirty() {
    return externalDirty || hasInternalChanges();
  }

  function updateSaveState() {
    if (!saveBtn) return;

    var dirty = pageIsDirty();

    // nota mancante = devo bloccare il salvataggio
    var noteText = (noteEl && noteEl.value) ? noteEl.value.trim() : "";
    var missingNote = requiresNote && dirty && !noteText;

    // stato aria / visivo / reale
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

  // Ogni volta che cambia un campo tracciato, ricalcoliamo dirty e quindi se la nota diventa obbligatoria
  form.addEventListener("input", updateSaveState);
  form.addEventListener("change", updateSaveState);

  // Init immediata: se arrivo da una modifica esterna (q_changed=1) il pulsante partirà già disabilitato
  updateSaveState();
})();
