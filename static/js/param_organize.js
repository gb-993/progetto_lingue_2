
document.addEventListener('DOMContentLoaded', () => {

  
  const navBtns = document.querySelectorAll('.param-btn');       
  const sections = document.querySelectorAll('.param-section');  

  
  function activate(id) {
    sections.forEach(s => s.classList.remove('active'));
    const tgt = document.getElementById(id);
    if (tgt) {
      tgt.classList.add('active');
      window.scrollTo({ top: tgt.offsetTop - 80, behavior: 'smooth' });
    }
  }

  
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      
      location.hash = '#' + target;
      activate(target);
    });
  });

  
  const hash = window.location.hash;
  const idFromHash = hash && hash.startsWith('#') ? hash.substring(1) : '';

  
  if (idFromHash && document.getElementById(idFromHash)) {
    activate(idFromHash);
  } else {
    
    sections.forEach(s => s.classList.remove('active'));
    window.scrollTo({ top: 0 });
  }

  
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
