// static/js/change_queries.js
(function () {
  function disableGroup(groupEl, disabled) {
    // disabilita/enabled tutti i controlli nel gruppo
    groupEl.querySelectorAll('input, select, textarea, button').forEach(el => {
      // non disabilitare il pulsante "Cerca"/"Reset" che NON sono dentro i fieldset
      el.disabled = !!disabled;
    });
    groupEl.hidden = !!disabled;
    groupEl.setAttribute('aria-hidden', disabled ? 'true' : 'false');
    groupEl.classList.toggle('d-none', !!disabled);
  }

  function onDatasetChange(formEl, selectEl) {
    const ds = selectEl.value;
    const groups = formEl.querySelectorAll('.filters-group');

    groups.forEach(g => {
      const isActive = g.getAttribute('data-ds') === ds;
      disableGroup(g, !isActive);
    });

    // azzera la pagina a 1 (evita di restare su pagine alte cambiando filtri)
    const pageInput = formEl.querySelector('input[name="page"]');
    if (pageInput) pageInput.value = '1';
  }

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form[role="search"]');
    if (!form) return;

    const datasetSelect = form.querySelector('select[name="dataset"]');
    if (!datasetSelect) return;

    // Inizializza lo stato attivo in base al valore corrente
    onDatasetChange(form, datasetSelect);

    // Al cambio dataset: aggiorna i gruppi (no submit, no reload)
    datasetSelect.addEventListener('change', function () {
      onDatasetChange(form, datasetSelect);
    });
  });
})();
