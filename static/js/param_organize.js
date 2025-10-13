// Gestione navigazione tra parametri e visibilità dinamica motivazioni/esempi
document.addEventListener('DOMContentLoaded', () => {

  // --- ELEMENTI ---
  const navBtns = document.querySelectorAll('.param-btn');       // i "quadratini" di navigazione
  const sections = document.querySelectorAll('.param-section');  // le sezioni dei parametri

  /**
   * Attiva una sezione per ID, disattivando le altre.
   * @param {string} id - l'ID della sezione da attivare
   */
  function activate(id) {
    sections.forEach(s => s.classList.remove('active'));
    const tgt = document.getElementById(id);
    if (tgt) {
      tgt.classList.add('active');
      window.scrollTo({ top: tgt.offsetTop - 80, behavior: 'smooth' });
    }
  }

  // --- CLICK sui bottoni di navigazione ---
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      // Aggiorna l'hash (per back/forward browser)
      location.hash = '#' + target;
      activate(target);
    });
  });

  // --- GESTIONE HASH iniziale ---
  const hash = window.location.hash;
  const idFromHash = hash && hash.startsWith('#') ? hash.substring(1) : '';

  // Se c'è un hash valido, apri la sezione corrispondente
  if (idFromHash && document.getElementById(idFromHash)) {
    activate(idFromHash);
  } else {
    // Altrimenti: non attivare nulla, resta all'inizio della pagina
    sections.forEach(s => s.classList.remove('active'));
    window.scrollTo({ top: 0 });
  }

  // --- TOGGLE motivazioni / esempi ---
  document.querySelectorAll('.resp-select').forEach(sel => {
    sel.addEventListener('change', () => {
      const qid = sel.dataset.qid;
      const mot = document.querySelector(`.mot-block[data-qid='${qid}']`);
      const exb = document.querySelector(`.examples-block[data-qid='${qid}']`);

      if (sel.value === 'no') {
        if (mot) mot.style.display = 'block';
        if (exb) exb.style.display = 'none';
      } else if (sel.value === 'yes') {
        if (mot) mot.style.display = 'none';
        if (exb) exb.style.display = 'block';
      } else {
        if (mot) mot.style.display = 'none';
        if (exb) exb.style.display = 'none';
      }
    });
  });
});
