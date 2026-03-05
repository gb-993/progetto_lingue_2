
(function () {
  function disableGroup(groupEl, disabled) {
    
    groupEl.querySelectorAll('input, select, textarea, button').forEach(el => {
      
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

    
    const pageInput = formEl.querySelector('input[name="page"]');
    if (pageInput) pageInput.value = '1';
  }

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form[role="search"]');
    if (!form) return;

    const datasetSelect = form.querySelector('select[name="dataset"]');
    if (!datasetSelect) return;

    
    onDatasetChange(form, datasetSelect);

    
    datasetSelect.addEventListener('change', function () {
      onDatasetChange(form, datasetSelect);
    });
  });
})();
