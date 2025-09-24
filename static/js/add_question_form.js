(function() {
  const addBtn = document.getElementById('add-question');
  if (!addBtn) return;

  function updateFormIndex(formEl, prefix, newIndex) {
    const findAttrs = ['name','id','for'];
    findAttrs.forEach(attr => {
      formEl.querySelectorAll('['+attr+'*="'+prefix+'-"]').forEach(node => {
        node.setAttribute(attr, node.getAttribute(attr).replace(new RegExp(prefix+'-(\\d+)-'), prefix+'-'+newIndex+'-'));
      });
    });
  }

  addBtn.addEventListener('click', function() {
    const total = document.getElementById('id_questions-TOTAL_FORMS');
    const max = document.getElementById('id_questions-MAX_NUM_FORMS');
    const container = document.getElementById('questions-list');
    const empty = document.getElementById('empty-form-template');

    if (max && parseInt(total.value,10) >= parseInt(max.value||'1000',10)) return;

    const newIndex = parseInt(total.value,10);
    const clone = empty.content.firstElementChild.cloneNode(true);
    updateFormIndex(clone, 'questions', newIndex);
    container.appendChild(clone);
    total.value = newIndex + 1;
  });
})();
