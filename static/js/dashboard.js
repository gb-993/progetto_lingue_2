

document.addEventListener("DOMContentLoaded", function () {
  const newsBox = document.querySelector(".news-box");
  const toggleBtn = document.querySelector(".news-toggle-btn");

  if (!newsBox || !toggleBtn) return;

  toggleBtn.addEventListener("click", function () {
    const isCollapsed = newsBox.classList.contains("collapsed");

    if (isCollapsed) {
      
      newsBox.classList.remove("collapsed");
      newsBox.classList.add("expanded");
      toggleBtn.textContent = "Show less";
      toggleBtn.setAttribute("aria-expanded", "true");
    } else {
      
      newsBox.classList.remove("expanded");
      newsBox.classList.add("collapsed");
      toggleBtn.textContent = "Show more";
      toggleBtn.setAttribute("aria-expanded", "false");
    }
  });
});
