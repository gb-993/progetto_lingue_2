
(function(){
  document.addEventListener('click', function(e){
    if (e.target.matches('.alert-close')) {
      e.target.closest('.alert')?.remove();
    }
  });

  document.querySelectorAll('.alert-success, .alert-info').forEach(function(el){
    const timer = setTimeout(() => el.remove(), 6000);
    el.addEventListener('mouseenter', () => clearTimeout(timer), { once: true });
  });
})();
