(function () {
  function autoResize(el) {
    
    el.style.height = 'auto';
    
    el.style.height = (el.scrollHeight + 2) + 'px';
  }

  function initTextarea(el) {
    if (!el || el.dataset.autosizeInit === '1') return;
    el.dataset.autosizeInit = '1';
    autoResize(el);
    el.addEventListener('input', function () { autoResize(el); });
  }

  
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('textarea[data-autosize="1"]').forEach(initTextarea);
  });

  
  
  document.addEventListener('focusin', function (e) {
    if (e.target && e.target.matches('textarea[data-autosize="1"]')) {
      initTextarea(e.target);
    }
  });
})();
