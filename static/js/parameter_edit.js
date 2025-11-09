

(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }

  var form = $("#param-edit-form");
  if (!form) return;

  var saveBtn = $("#saveBtn");
  var requiresNote = form.getAttribute("data-requires-change-note") === "true";

  var changeNoteName = form.getAttribute("data-change-note-name") || "change_note";
  var noteEl = form.elements[changeNoteName] || $("#id_change_note");
  var hint = $("#changeNoteHint");

  var externalDirty = form.getAttribute("data-external-dirty") === "true";

  function norm(val) {
    if (Array.isArray(val)) return JSON.stringify(val.slice().sort());
    if (val === true || val === false || val === null || val === undefined) return String(val);
    if (typeof val === "number") return String(val);
    return String(val);
  }

  function allByName(name) {
    var list = form.querySelectorAll('[name="' + CSS.escape(name) + '"]');
    return Array.prototype.slice.call(list);
  }

  function getValueByName(name) {
    var group = allByName(name);
    if (!group.length) return null;

    var type = (group[0].type || "").toLowerCase();
    var tag = (group[0].tagName || "").toLowerCase();

    if (type === "radio") {
      var checked = group.find(function (r) { return r.checked; });
      return checked ? checked.value : null;
    }


    if (type === "checkbox") {
      if (group.length === 1) return !!group[0].checked;
      return group.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    }

    if (tag === "select") {
      var sel = group[0];
      if (sel.multiple) {
        return Array.prototype.filter.call(sel.options, function (o) { return o.selected; })
          .map(function (o) { return o.value; });
      }
      return sel.value;
    }

    return group[0].value;
  }

  var names = [];

  (function buildNames() {
    var namesSet = new Set();

    var trackedAttr = form.getAttribute("data-tracked");
    if (trackedAttr) {
      try {
        var trackedFromData = JSON.parse(trackedAttr);
        if (Array.isArray(trackedFromData)) {
          trackedFromData.forEach(function (n) {
            if (typeof n === "string" && n && n !== changeNoteName) {
              namesSet.add(n);
            }
          });
        }
      } catch (e) {
      }
    }

    var all = form.querySelectorAll("input[name], select[name], textarea[name]");
    Array.prototype.forEach.call(all, function (el) {
      var n = el.name;
      if (!n) return;

      if (n === changeNoteName) return;
      if (n === "csrfmiddlewaretoken") return;
      if (n === "had_external_changes") return;

      namesSet.add(n);
    });

    names = Array.from(namesSet);
  })();

  var initial = {};
  names.forEach(function (n) {
    initial[n] = norm(getValueByName(n));
  });

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

  form.addEventListener("input", updateSaveState, true);
  form.addEventListener("change", updateSaveState, true);

  updateSaveState();
})();
