// static/js/show_motivation.js
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  // Mostra/nasconde il blocco motivazioni per una domanda + reset se si passa a YES
  function toggleMotivationsCheckboxes(qid, show) {
    const block = document.querySelector('.mot-block[data-qid="' + qid + '"]');
    if (!block) return;

    if (show) {
      block.style.display = '';
      // abilita tutti i checkbox
      $all('input[type="checkbox"][name="mot_' + qid + '"]', block).forEach(chk => {
        chk.removeAttribute('disabled');
      });
    } else {
      block.style.display = 'none';
      // passando a YES: deseleziona e riabilita tutti
      $all('input[type="checkbox"][name="mot_' + qid + '"]', block).forEach(chk => {
        chk.checked = false;
        chk.disabled = false;
      });
    }
  }

  // Regola esclusiva per MOT1: se MOT1 è selezionato, disabilita tutte le altre; se selezioni un'altra, deseleziona MOT1
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
      // se MOT1 non è selezionata, assicurati che le altre siano abilitate
      checks.forEach(c => { c.disabled = false; });
      // Se un'altra è stata selezionata, garantisci che MOT1 non resti checked
      if (mot1) mot1.checked = false;
    }
  }

  function onRespChange(e) {
    const sel = e.currentTarget;
    const qid = sel.dataset.qid || sel.dataset.questionId; // compat
    if (!qid) return;
    const isNo = (sel.value === 'no');
    toggleMotivationsCheckboxes(qid, isNo);
  }

  function onMotivationClick(e) {
    const input = e.target.closest('input[type="checkbox"]');
    if (!input) return;
    const container = input.closest('.mot-checklist');
    if (!container) return;
    // Applica la regola dopo ogni click
    applyExclusiveRuleCheckboxes(container);
  }

  function init() {
    // Collega handler ai select YES/NO
    $all('select.resp-select[data-qid], select.resp-select[data-question-id]').forEach(sel => {
      sel.addEventListener('change', onRespChange);
      const qid = sel.dataset.qid || sel.dataset.questionId;
      toggleMotivationsCheckboxes(qid, sel.value === 'no');
    });

    // Delegato: click sulle checkbox motivazioni
    document.addEventListener('click', function (e) {
      if (e.target && e.target.matches('.mot-checklist input[type="checkbox"]')) {
        onMotivationClick(e);
      }
    });

    // All’avvio, applica la regola esclusiva a tutti i blocchi esistenti (dati già salvati)
    $all('.mot-checklist').forEach(applyExclusiveRuleCheckboxes);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
