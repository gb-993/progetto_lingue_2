// static/js/examples.js
(function () {
  function nextLinear(nums) {
    const ints = nums.map(n => {
      const m = n.match(/^(\d+)$/);
      return m ? parseInt(m[1], 10) : 0;
    });
    const max = Math.max(0, ...ints);
    return String(max + 1);
  }

  function nextPaired(nums) {
    // sequence: 1a,1b,2a,2b,...
    // find last valid "Xa"/"Xb"
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
    // sequence: 1.1,1.2,2.1,2.2,...
    let lastI = 0, lastJ = 2;
    nums.forEach(n => {
      const m = n.match(/^(\d+)\.(\d+)$/);
      if (m) {
        const i = parseInt(m[1], 10);
        const j = parseInt(m[2], 10);
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
    const vals = Array.from(existing).map(el => el.value.trim()).filter(Boolean);
    switch ((templateType || "").toLowerCase()) {
      case "plain":      // manteniamo compatibilità: plain => lineare
      case "numbered":
      case "linear":
        return nextLinear(vals);
      case "glossed":    // se vuoi, glossed può ancora essere lineare
        return nextLinear(vals);
      case "paired":
        return nextPaired(vals);
      case "decimal":
        return nextDecimal(vals);
      // mapping dei tuoi placeholder attuali ai tre tipi richiesti:
      // "Plain text" => lineare; "Glossed line" => lineare; "Numbered list" => lineare
      default:
        return nextLinear(vals);
    }
  }

  function buildExampleRow(qid, uid, numberValue) {
    // Ritorna un <div> con inputs per un nuovo esempio (nuovi nomi newex_<qid>_<uid>_*)
    const wrapper = document.createElement("div");
    wrapper.className = "card example-row";
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
      </div>`;
    return wrapper;
  }

  function toggleExamplesBlock(selectEl) {
    const qid = selectEl.getAttribute("data-question-id");
    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    if (!block) return;
    const show = (selectEl.value === "yes");
    block.style.display = show ? "" : "none";
    // ARIA live hint
    const sr = block.querySelector(".examples-hint");
    if (sr) sr.textContent = show ? "Examples section shown." : "Examples section hidden.";
  }

  // on load: wire select changes
  document.addEventListener("DOMContentLoaded", function () {
    // attach to answer selects
    document.querySelectorAll(".resp-select").forEach(sel => {
      sel.addEventListener("change", () => toggleExamplesBlock(sel));
      // init state
      toggleExamplesBlock(sel);
    });

    // Add example buttons
    document.querySelectorAll(".add-example-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.preventDefault();
        const qid = btn.getAttribute("data-qid");
        const container = document.querySelector(`.examples-list[data-qid="${qid}"]`);
        const templateType = btn.getAttribute("data-template") || "";
        const existingNumberInputs = container.querySelectorAll('input[name$="_number"]');
        const nextNum = computeNextNumber(templateType, existingNumberInputs);
        const uid = String(Date.now()) + "_" + Math.floor(Math.random() * 10000);
        const row = buildExampleRow(qid, uid, nextNum);
        container.appendChild(row);
        // focus sul primo campo “Data” del nuovo esempio
        const firstInput = row.querySelector(`input[name="newex_${qid}_${uid}_textarea"]`);
        if (firstInput) firstInput.focus();
      });
    });
  });
})();
