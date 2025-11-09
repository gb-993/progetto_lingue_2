
(function () {
  'use strict';

  function onSubmitCreate(ev) {
    const form = ev.currentTarget;
    const btn = form.querySelector('button[type="submit"][data-once="true"]');

    if (btn && btn.dataset.submitting === '1') {
      ev.preventDefault();
      return;
    }

    
    const mustConfirm = form.dataset.confirmMissing === '1';
    const msg = form.dataset.confirmMessage ||
      'Attenzione: ci sono risposte mancanti. Vuoi creare comunque la submission?';
    if (mustConfirm) {
      const ok = window.confirm(msg);
      if (!ok) {
        ev.preventDefault();
        return;
      }
    }

    
    if (btn) {
      btn.dataset.submitting = '1';
      btn.setAttribute('aria-busy', 'true');
      btn.disabled = true;
      
      const originalText = btn.textContent;
      btn.dataset.originalText = originalText;
      btn.textContent = 'Creazione…';
    }
  }

  function init() {
    const form = document.getElementById('submission-create-form');
    if (!form) return;
    form.addEventListener('submit', onSubmitCreate, { once: false });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
