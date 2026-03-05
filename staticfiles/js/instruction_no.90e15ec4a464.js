



(function () {
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $all(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function toggleInstruction(qid, show) {
    const block = document.querySelector(
      '.no-instruction-block[data-qid="' + qid + '"]'
    );
    if (!block) return;
    block.style.display = show ? "" : "none";
  }

  function onRespChange(e) {
    const sel = e.currentTarget;
    const qid = sel.dataset.qid || sel.dataset.questionId;
    if (!qid) return;

    const value = (sel.value || "").toLowerCase();
    toggleInstruction(qid, value === "no");
  }

  function init() {
    
    $all('select.resp-select[data-qid], select.resp-select[data-question-id]').forEach(
      (sel) => {
        sel.addEventListener("change", onRespChange);

        
        const qid = sel.dataset.qid || sel.dataset.questionId;
        const value = (sel.value || "").toLowerCase();
        toggleInstruction(qid, value === "no");
      }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
