(function() {
  function toggle() {
    if (!btn) return;
    if (window.scrollY > 200) {
      btn.classList.remove('is-hidden');
    } else {
      btn.classList.add('is-hidden');
    }
  }

  var btn = document.getElementById('backToTop');
  if (!btn) return;

  // Click → scroll liscio in alto
  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Aggiorna stato SUBITO all’avvio
  toggle();

  // Aggiorna su scroll (con micro throttle via requestAnimationFrame)
  var ticking = false;
  window.addEventListener('scroll', function () {
    if (!ticking) {
      window.requestAnimationFrame(function () {
        toggle();
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
})();
