/* parameter_edit.js
   - Change tracking dei campi chiave del form
   - Blocca il tasto "Save" se ci sono modifiche ma la change note è vuota (solo in edit)
*/

(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  var form = $("#param-edit-form");
  if (!form) return;

  var saveBtn = $("#saveBtn");
  var requiresNote = form.getAttribute("data-requires-change-note") === "true";
  var changeNoteName = form.getAttribute("data-change-note-name") || "change_note";
  var noteEl = form.elements[changeNoteName] || $("#id_change_note");
  var hint = $("#changeNoteHint");

  // elenco dei nomi campo da tracciare, iniettato dal template come JSON nello stesso form
  var trackedAttr = form.getAttribute("data-tracked") || "[]";
  var tracked;
  try { tracked = JSON.parse(trackedAttr); } catch (e) { tracked = []; }

  function getValByName(name) {
    var els = form.elements[name];
    if (!els) return null;
    // Se è una RadioNodeList o HTMLCollection, prendi il primo (per i nostri campi basta)
    var el = (typeof els.length === "number") ? els[0] : els;
    if (!el) return null;
    if (el.type === "checkbox") return el.checked;
    return el.value;
  }

  // Snapshot iniziale
  var initial = {};
  tracked.forEach(function (n) {
    initial[n] = getValByName(n);
  });

  function hasChanges() {
    return tracked.some(function (n) {
      return getValByName(n) !== initial[n];
    });
  }

  function updateSaveState() {
    if (!saveBtn) return;
    var changed = hasChanges();
    var needsNote = requiresNote && changed && (!noteEl || !noteEl.value || !noteEl.value.trim());

    saveBtn.disabled = !!needsNote;
    saveBtn.classList.toggle("btn--disabled", !!needsNote);
    saveBtn.setAttribute("aria-disabled", needsNote ? "true" : "false");
    if (hint) hint.classList.toggle("b-bad", !!needsNote);
    saveBtn.title = needsNote
      ? "Impossibile salvare finché non inserisci le note delle modifiche."
      : "";
  }

  // Ascoltatori
  form.addEventListener("input", updateSaveState);
  form.addEventListener("change", updateSaveState);

  // Init
  updateSaveState();
})();
