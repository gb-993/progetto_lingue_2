(function () {
  function autoResize(el) {
    // resetta, poi adatta all'altezza del contenuto
    el.style.height = 'auto';
    // +2 per evitare tagli di line-height su alcuni browser
    el.style.height = (el.scrollHeight + 2) + 'px';
  }

  function initTextarea(el) {
    if (!el || el.dataset.autosizeInit === '1') return;
    el.dataset.autosizeInit = '1';
    autoResize(el);
    el.addEventListener('input', function () { autoResize(el); });
  }

  // Inizializza all'avvio
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('textarea[data-autosize="1"]').forEach(initTextarea);
  });

  // Se alcune textarea vengono mostrate dopo (es. cambia risposta YES/NO), inizializza quando entrano nel DOM/visibili
  // Delegato semplice su focus
  document.addEventListener('focusin', function (e) {
    if (e.target && e.target.matches('textarea[data-autosize="1"]')) {
      initTextarea(e.target);
    }
  });
})();
