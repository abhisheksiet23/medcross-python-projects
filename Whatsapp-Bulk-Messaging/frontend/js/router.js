// Views registry itself now lives in views-registry.js, loaded before this file.

function navigate() {
  const hash = window.location.hash.replace("#/", "") || "dashboard";
  const route = hash.split("?")[0];
  const view = Views[route] || Views.dashboard;

  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === route);
  });

  setTitle(view.title || route);
  const container = document.getElementById("view");
  container.innerHTML = `<div class="empty">Loading…</div>`;
  Promise.resolve(view.render(container)).catch((err) => {
    console.error(err);
    container.innerHTML = `<div class="empty">Something went wrong loading this page.</div>`;
    toastError(err);
  });
}

window.addEventListener("hashchange", navigate);
window.addEventListener("DOMContentLoaded", navigate);
