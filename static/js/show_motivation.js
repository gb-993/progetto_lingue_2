(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function toggleMotivationsCheckboxes(qid, show) {
    const block = document.querySelector('.mot-block[data-qid="' + qid + '"]');
    if (!block) return;

    if (show) {
      block.style.display = '';
      $all('input[type="checkbox"][name="mot_' + qid + '"]', block).forEach(chk => {
        chk.removeAttribute('disabled');
      });
    } else {
      block.style.display = 'none';
      $all('input[type="checkbox"][name="mot_' + qid + '"]', block).forEach(chk => {
        chk.checked = false;
        chk.disabled = false;
      });
    }
  }

  function applyExclusiveRuleCheckboxes(container) {
    if (!container) return;
    const qid = container.getAttribute('data-qid');
    const checks = $all('input[type="checkbox"][name="mot_' + qid + '"]', container);
    if (checks.length === 0) return;

    const mot1 = checks.find(c => c.dataset.exclusive === '1');

    const mot1Selected = !!(mot1 && mot1.checked);
    if (mot1 && mot1Selected) {
      checks.forEach(c => {
        if (c !== mot1) {
          c.checked = false;
          c.disabled = true;
        }
      });
    } else {
      checks.forEach(c => { c.disabled = false; });
      if (mot1) mot1.checked = false;
    }
  }

  function onRespChange(e) {
    const sel = e.currentTarget;
    const qid = sel.dataset.qid || sel.dataset.questionId; 
    if (!qid) return;
    const isNo = (sel.value === 'no');
    toggleMotivationsCheckboxes(qid, isNo);
  }

  function onMotivationClick(e) {
    const input = e.target.closest('input[type="checkbox"]');
    if (!input) return;
    const container = input.closest('.mot-checklist');
    if (!container) return;
    applyExclusiveRuleCheckboxes(container);
  }

  function init() {
    $all('select.resp-select[data-qid], select.resp-select[data-question-id]').forEach(sel => {
      sel.addEventListener('change', onRespChange);
      const qid = sel.dataset.qid || sel.dataset.questionId;
      toggleMotivationsCheckboxes(qid, sel.value === 'no');
    });

    document.addEventListener('click', function (e) {
      if (e.target && e.target.matches('.mot-checklist input[type="checkbox"]')) {
        onMotivationClick(e);
      }
    });

    $all('.mot-checklist').forEach(applyExclusiveRuleCheckboxes);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
