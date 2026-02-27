
(function () {
  "use strict";

  
  
  
  function nextLinear(nums) {
    const ints = nums.map(n => {
      const m = n.match(/^(\d+)$/);
      return m ? parseInt(m[1], 10) : 0;
    });
    const max = Math.max(0, ...ints);
    return String(max + 1);
  }

  function nextPaired(nums) {
    
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

  
  
  
  function getQidFrom(el) {
    
    let qid = el && el.getAttribute && el.getAttribute("data-qid");
    if (qid) return qid;
    
    const block = el && el.closest && el.closest(".examples-block");
    if (block && block.getAttribute) {
      qid = block.getAttribute("data-qid");
      if (qid) return qid;
    }
    
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

  
  
  
  function renumberExamplesForQuestion(qid) {
    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    if (!block) return;
    const templateType = (block.getAttribute("data-template") || "").toLowerCase();
    const list = block.querySelector(`.examples-list[data-qid="${qid}"]`);
    if (!list) return;

    
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
        const sub = (idx % 2) + 1; 
        label = `${n}.${sub}`;
      } else {
        label = String(idx + 1); 
      }

      
      const numInput = row.querySelector('input[name$="_number"]');
      if (numInput) numInput.value = label;
    });
  }

  
  
  
  function toggleExamplesBlock(selectEl) {
    
    

    
    const qid = selectEl.getAttribute("data-qid");

    const block = document.querySelector(`.examples-block[data-qid="${qid}"]`);
    if (!block) return;

    const v = (selectEl.value || "").toLowerCase();
    const show = (v === "yes" || v === "no"); 
    block.style.display = show ? "" : "none";

    const sr = block.querySelector(".examples-hint");
    if (sr) sr.textContent = show ? "Examples section shown." : "Examples section hidden.";
  }



  
  
  function buildExampleRow(qid, uid, numberValue) {
  const wrapper = document.createElement("div");
  wrapper.className = "card example-row";
  wrapper.setAttribute("data-qid", qid);
  wrapper.setAttribute("data-uid", uid);
  wrapper.style.marginBottom = "1rem";

  // Nota: ho messo rows="1" agli altri campi per farli partire compatti come input,
  // ma col vantaggio che si espandono se l'utente scrive molto.
  wrapper.innerHTML = `
    <input type="hidden" name="newex_${qid}_${uid}_number" value="${numberValue}">
    
    <div class="grid">
      <div>
        <label>Example text</label>
        <textarea name="newex_${qid}_${uid}_textarea" rows="3" style="width:100%; resize:vertical;"></textarea>
      </div>
      <div>
        <label>Transliteration</label>
        <textarea name="newex_${qid}_${uid}_transliteration" rows="1" style="width:100%; resize:vertical;"></textarea>
      </div>
      <div>
        <label>Gloss</label>
        <textarea name="newex_${qid}_${uid}_gloss" rows="1" style="width:100%; resize:vertical;"></textarea>
      </div>
      <div>
        <label>English translation</label>
        <textarea name="newex_${qid}_${uid}_translation" rows="1" style="width:100%; resize:vertical;"></textarea>
      </div>
      <div>
        <label>Reference</label>
        <textarea name="newex_${qid}_${uid}_reference" rows="1" style="width:100%; resize:vertical;"></textarea>
      </div>
    </div>
    <div class="toolbar" style="margin-top: .5rem; display: flex; justify-content: flex-end;">
      <button class="btn btn-newex-delete" type="button" data-qid="${qid}" data-uid="${uid}">Delete</button>
      <span class="sr-only" aria-live="polite"></span>
    </div>`;
  return wrapper;
}

  
  
  
  document.addEventListener("DOMContentLoaded", function () {
    
    document.querySelectorAll(".resp-select").forEach(sel => {
      sel.addEventListener("change", () => toggleExamplesBlock(sel));
      toggleExamplesBlock(sel);
    });


    
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

        
        const firstInput = row.querySelector(`textarea[name="newex_${qid}_${uid}_textarea"]`);
        if (firstInput) firstInput.focus();
        renumberExamplesForQuestion(qid);
      });
    });

    
    document.addEventListener("click", function (e) {
      
      
      
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

        
        let hidden = row.querySelector(`input[type="hidden"][name="del_ex_${exid}"]`)
                  || form.querySelector(`input[type="hidden"][name="del_ex_${exid}"]`);
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = `del_ex_${exid}`;
        }
        hidden.value = "1";

        
        if (hidden.parentElement !== form) form.appendChild(hidden);

        
        row.remove();

        if (qid) renumberExamplesForQuestion(qid);
        return;
      }

    });
  });
})();



document.addEventListener("DOMContentLoaded", function () {
  const blocks = document.querySelectorAll(".examples-block[data-qid]");
  blocks.forEach(block => {
    const qid = block.getAttribute("data-qid");
    
    if (typeof window.renumberExamplesForQuestion === "function") {
      window.renumberExamplesForQuestion(qid);
    } else {
      
      
    }
  });
});


document.addEventListener("DOMContentLoaded", function () {
  
  const forms = document.querySelectorAll('form[action*="parameter_save"]');
  forms.forEach(form => {
    form.addEventListener("submit", function (e) {
      
      form.querySelectorAll(".js-yes-examples-error").forEach(n => {
        n.style.display = "none";
        n.textContent = "";
      });

      let invalid = false;

      
      const selects = form.querySelectorAll('[name^="resp_"][data-qid]');
      selects.forEach(selectEl => {
        const qid = selectEl.getAttribute("data-qid");
        if (!qid) return;
        if ((selectEl.value || "").toLowerCase() !== "yes") return;

        const list = form.querySelector(`.examples-list[data-qid="${qid}"]`);
        if (!list) return;


        let nonEmptyCount = 0;

        // Cerca gli esempi già presenti (o nuovi rigenerati)
        const rows = list.querySelectorAll('.example-row');
        for (const row of rows) {
          const delHidden = row.querySelector('input[type="hidden"][name^="del_ex_"]');
          const isDeleted = delHidden && delHidden.value === "1";
          if (isDeleted) continue;

          const txt = row.querySelector('[name$="_textarea"]');
          if (txt && txt.value.trim()) { nonEmptyCount++; }
        }

        // Cerca tra gli input appena generati via JS (aggiungiamo al contatore)
        const newInputs = list.querySelectorAll(`[name^="newex_${qid}_"][name$="_textarea"]`);
        for (const inp of newInputs) {
          if ((inp.value || "").trim()) { nonEmptyCount++; }
        }

        // Se il contatore è minore di 2, blocca il form
        if (nonEmptyCount < 2) {
          invalid = true;
          const err = form.querySelector(`.js-yes-examples-error[data-qid="${qid}"]`);
          if (err) {
            err.textContent = "With YES you must add at least two examples with a non-empty Example text.";
            err.style.display = "";
          }
        }

      });

      if (invalid) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, { capture: true });
  });
});
