/* account_languages.js
   - filtro client-side sulle checkbox delle lingue
   - aggiornamento in tempo reale del riepilogo selezionati
*/
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function normalize(s) { return (s || "").toLowerCase().trim(); }

  var search = $("#lang-search");
  var list = $("#lang-list");
  var items = list ? $all(".checkbox-item", list) : [];
  var selectedUl = $("#lang-selected");

  function filter() {
    if (!list) return;
    var q = normalize(search.value);
    items.forEach(function (it) {
      var hay = it.getAttribute("data-search") || "";
      var show = !q || hay.indexOf(q) !== -1;
      it.style.display = show ? "flex" : "none";
    });
  }

  function refreshSelected() {
    if (!list || !selectedUl) return;
    // ricostruisce la lista
    selectedUl.innerHTML = "";
    var checked = $all('input[type="checkbox"]:checked', list);
    if (checked.length === 0) {
      selectedUl.insertAdjacentHTML("beforeend", "Nessuna lingua selezionata.");
      return;
    }
    checked.forEach(function (chk) {
      var label = chk.closest(".checkbox-item");
      var text = label ? label.querySelector("span").textContent : chk.value;
      var li = document.createElement("li");
      li.textContent = text;
      li.setAttribute("data-id", chk.value);
      selectedUl.appendChild(li);
    });
  }

  if (search) search.addEventListener("input", filter);
  if (list) {
    list.addEventListener("change", function (e) {
      if (e.target && e.target.matches('input[type="checkbox"]')) {
        refreshSelected();
      }
    });
  }

  // inizializza all'apertura
  if (list) {
    filter();
    // refreshSelected solo se esiste già una selezione pre-render
    refreshSelected();
  }
})();
