(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  // Mostra/nasconde e abilita/disabilita il blocco motivazioni per una domanda
  function toggleMotivations(questionId, show) {
    const block = document.querySelector('.mot-block[data-qid="' + questionId + '"]');
    if (!block) return;
    const select = $('#mot_' + questionId, block);
    if (show) {
      block.style.display = '';
      if (select) select.removeAttribute('disabled');
    } else {
      block.style.display = 'none';
      if (select) {
        // puliamo la selezione quando si passa a YES
        select.setAttribute('disabled', 'disabled');
        $all('option', select).forEach(opt => { opt.selected = false; opt.disabled = false; });
      }
    }
  }

  // Applica la regola "Motivazione1 esclusiva"
  function applyExclusiveRule(selectEl) {
    if (!selectEl) return;
    const opts = $all('option', selectEl);
    const exclusive = opts.find(o => o.dataset.exclusive === '1');
    if (!exclusive) return;

    if (exclusive.selected) {
      // se hai selezionato Motivazione1, tutte le altre vengono deselezionate e disabilitate
      opts.forEach(o => {
        if (o !== exclusive) {
          o.selected = false;
          o.disabled = true;
        }
      });
    } else {
      // se non è selezionata, riabilita tutte
      opts.forEach(o => { o.disabled = false; });
    }
  }

  function onRespChange(e) {
    const sel = e.currentTarget;
    const qid = sel.dataset.questionId;
    if (!qid) return;
    const isNo = (sel.value === 'no');
    toggleMotivations(qid, isNo);
  }

  function onMotivationChange(e) {
    const selectEl = e.currentTarget;
    applyExclusiveRule(selectEl);
  }

  function init() {
    // Collega handler ai select YES/NO
    $all('select.resp-select[data-question-id]').forEach(sel => {
      sel.addEventListener('change', onRespChange);
      toggleMotivations(sel.dataset.questionId, sel.value === 'no');

    });

    // Collega handler ai select delle motivazioni
    $all('.mot-block select[multiple][data-question-id]').forEach(sel => {
      sel.addEventListener('change', onMotivationChange);
      // Applica la regola una volta all'avvio (in caso di dati già salvati)
      applyExclusiveRule(sel);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
