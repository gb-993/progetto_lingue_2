// static/js/examples.js
(function () {
  "use strict";

  // ===============================
  // Helpers: numerazione prossimi #
  // ===============================
  function nextLinear(nums) {
    const ints = nums.map(n => {
      const m = n.match(/^(\d+)$/);
      return m ? parseInt(m[1], 10) : 0;
    });
    const max = Math.max(0, ...ints);
    return String(max + 1);
  }

  function nextPaired(nums) {
    // 1a,1b,2a,2b...
    let lastN = 0, lastSfx = "b";
    nums.forEach(n => {
      const m = n.match(/^(\d+)([ab])$/i);
      if (m) {
        const ni = parseInt(m[1], 10);
        const s = m[2].toLowerCase();
        if (ni > lastN || (ni === lastN && s > lastSfx)) {
          lastN = ni; lastSfx = s;
        }
      }
    });
    if (lastN === 0 && lastSfx === "b") return "1a";
    if (lastSfx === "a") return `${lastN}b`;
    return `${lastN + 1}a`;
  }

  function nextDecimal(nums) {
    // 1.1,1.2,2.1,2.2...
    let lastI = 0, lastJ = 2;
    nums.forEach(n => {
      const m = n.match(/^(\d+)\.(\d+)$/);
      if (m) {
        const i = parseInt(m[1], 10), j = parseInt(m[2], 10);
        if (i > lastI || (i === lastI && j > lastJ)) {
          lastI = i; lastJ = j;
        }
      }
    });
    if (lastI === 0 && lastJ === 2) return "1.1";
    if (lastJ === 1) return `${lastI}.2`;
    return `${lastI + 1}.1`;
  }

  function computeNextNumber(templateType, existing) {
    const vals = Array.from(existing)
      .map(el => (el.value || "").trim())
      .filter(Boolean);
    switch ((templateType || "").toLowerCase()) {
      case "numbered":
      case "linear":
      case "plain":
      case "glossed":
        return nextLinear(vals);
      case "paired":
        return nextPaired(vals);
      case "decimal":
        return nextDecimal(vals);
      default:
        return nextLinear(vals);
    }
  }

  // ===============================
  // Helpers: contesto domanda/QID
  // ===============================
  function getQidFrom(el) {
    // prova: attributo data-qid su bottone
    let qid = el && el.getAttribute && el.getAttribute("data-qid");
    if (qid) return qid;
    // prova: wrapper .examples-block
    const block = el && el.closest && el.closest(".examples-block");
    if (block && block.getAttribute) {
      qid = block.getAttribute("data-qid");
      if (qid) return qid;
    }
    // prova: lista .examples-list
    const list = el && el.closest && el.closest(".examples-list");
    if (list && list.getAttribute) {
      qid = list.getAttribute("data-qid");
      if (qid) return qid;
    }
    return null;
  }

  function getTemplateTypeForQid(qid) {
    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    return block ? (block.getAttribute("data-template") || "").toLowerCase() : "";
  }

  function getForm(el) {
    return (el && el.closest && el.closest("form")) || document.querySelector("form");
  }

  // ===============================
  // Rinumerazione
  // ===============================
  function renumberExamplesForQuestion(qid) {
    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    if (!block) return;
    const templateType = (block.getAttribute("data-template") || "").toLowerCase();
    const list = block.querySelector(`.examples-list[data-qid="${qid}"]`);
    if (!list) return;

    // prendi SOLO le righe NON marcate per delete (nuovi/vecchi ancora visibili)
    const rows = Array.from(list.querySelectorAll(".example-row"))
      .filter(r => !r.classList.contains("is-marked-delete"));

    rows.forEach((row, idx) => {
      let label = "";
      if (templateType === "paired") {
        const n = Math.floor(idx / 2) + 1;
        const sfx = (idx % 2 === 0) ? "a" : "b";
        label = `${n}${sfx}`;
      } else if (templateType === "decimal") {
        const n = Math.floor(idx / 2) + 1;
        const sub = (idx % 2) + 1; // 1 o 2
        label = `${n}.${sub}`;
      } else {
        label = String(idx + 1); // linear di default
      }

      // esistente: ex_<id>_number | nuovo: newex_<qid>_<uid>_number
      const numInput = row.querySelector('input[name$="_number"]');
      if (numInput) numInput.value = label;
    });
  }

  // ===============================
  // Show/hide blocco examples
  // ===============================
  function toggleExamplesBlock(selectEl) {
    const qid = selectEl.getAttribute("data-question-id");
    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    if (!block) return;
    const show = (selectEl.value === "yes"); // NB: se vuoi esempi anche su "no", cambiare qui.
    block.style.display = show ? "" : "none";
    const sr = block.querySelector(".examples-hint");
    if (sr) sr.textContent = show ? "Examples section shown." : "Examples section hidden.";
  }

  // ===============================
  // Costruzione riga NUOVO esempio
  // ===============================
  function buildExampleRow(qid, uid, numberValue) {
    const wrapper = document.createElement("div");
    wrapper.className = "card example-row";
    wrapper.setAttribute("data-qid", qid);
    wrapper.setAttribute("data-uid", uid);
    wrapper.style.marginBottom = ".5rem";
    wrapper.innerHTML = `
      <div class="grid">
        <div>
          <label>Number</label>
          <input name="newex_${qid}_${uid}_number" value="${numberValue}" readonly>
        </div>
        <div>
          <label>Data</label>
          <input name="newex_${qid}_${uid}_textarea" value="">
        </div>
        <div>
          <label>Transliteration</label>
          <input name="newex_${qid}_${uid}_transliteration" value="">
        </div>
        <div>
          <label>Gloss</label>
          <input name="newex_${qid}_${uid}_gloss" value="">
        </div>
        <div>
          <label>English translation</label>
          <input name="newex_${qid}_${uid}_translation" value="">
        </div>
        <div>
          <label>Reference</label>
          <input name="newex_${qid}_${uid}_reference" value="">
        </div>
      </div>
      <div class="toolbar" style="margin-top:.25rem">
        <button class="btn btn-newex-delete" type="button" data-qid="${qid}" data-uid="${uid}">Delete</button>
        <span class="sr-only" aria-live="polite"></span>
      </div>`;
    return wrapper;
  }

  // ===============================
  // Inizializzazione
  // ===============================
  document.addEventListener("DOMContentLoaded", function () {
    // show/hide blocco examples al cambio risposta
    document.querySelectorAll(".resp-select").forEach(sel => {
      sel.addEventListener("change", () => toggleExamplesBlock(sel));
      toggleExamplesBlock(sel);
    });

    // Add example
    document.querySelectorAll(".add-example-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.preventDefault();
        if (btn.hasAttribute("disabled")) return;

        const qid = btn.getAttribute("data-qid") || getQidFrom(btn);
        if (!qid) return;

        const container = document.querySelector(`.examples-list[data-qid="${qid}"]`);
        const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
        if (!container || !block) return;

        const templateType = block.getAttribute("data-template") || "";
        const existingNumberInputs = container.querySelectorAll('input[name$="_number"]');
        const nextNum = computeNextNumber(templateType, existingNumberInputs);
        const uid = String(Date.now()) + "_" + Math.floor(Math.random() * 10000);

        const row = buildExampleRow(qid, uid, nextNum);
        container.appendChild(row);

        // focus + rinumerazione completa (garantisce sequenza contigua)
        const firstInput = row.querySelector(`input[name="newex_${qid}_${uid}_textarea"]`);
        if (firstInput) firstInput.focus();
        renumberExamplesForQuestion(qid);
      });
    });

    // Delegated clicks (robusto anche se il click parte da un figlio del bottone)
    document.addEventListener("click", function (e) {
      // -----------------------------
      // Delete NUOVO esempio (non salvato): rimuovi dal DOM + renumera
      // -----------------------------
      const delNewBtn = e.target.closest(".btn-newex-delete");
      if (delNewBtn) {
        e.preventDefault();
        if (delNewBtn.hasAttribute("disabled")) return;

        const row = delNewBtn.closest(".example-row");
        const qid = delNewBtn.getAttribute("data-qid") || getQidFrom(delNewBtn);
        if (row) row.remove();
        if (qid) renumberExamplesForQuestion(qid);
        return;
      }

      // -----------------------------
      // Delete ESEMPIO ESISTENTE: hard-remove
      // - crea/sposta input hidden nel FORM: del_ex_<ID>=1
      // - rimuovi SUBITO la riga dal DOM
      // - rinumerazione visiva
      // -----------------------------
      const toggleBtn = e.target.closest(".btn-ex-toggle-delete");
      if (toggleBtn) {
        e.preventDefault();
        if (toggleBtn.hasAttribute("disabled")) return;

        const row  = toggleBtn.closest(".example-row");
        const exid = toggleBtn.getAttribute("data-exid");
        if (!row || !exid) return;

        const qid  = toggleBtn.getAttribute("data-qid") || getQidFrom(toggleBtn);
        const form = getForm(toggleBtn);
        if (!form) return;

        // Hidden flag nel FORM (non nella riga che stiamo per rimuovere)
        let hidden = form.querySelector(`input[type="hidden"][name="del_ex_${exid}"]`);
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = `del_ex_${exid}`;
          form.appendChild(hidden);
        }
        hidden.value = "1";

        // Rimuovi SUBITO la riga (scompare immediatamente)
        row.remove();

        // Rinumerazione residua
        if (qid) renumberExamplesForQuestion(qid);
        return;
      }
    });
  });
})();
