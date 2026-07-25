function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function timeOnly(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function badge(status) {
  return `<span class="badge ${escapeHtml(status || "pending")}">${escapeHtml(status || "pending")}</span>`;
}

function toast(message, type = "") {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function toastError(err) {
  toast(err.message || String(err), "error");
}

function openModal({ title, bodyHtml, footerHtml, onMount }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-overlay" id="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>${escapeHtml(title)}</h3>
          <button class="modal-close" id="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
      </div>
    </div>`;
  const overlay = document.getElementById("modal-overlay");
  const close = () => { root.innerHTML = ""; };
  document.getElementById("modal-close-btn").onclick = close;
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  if (onMount) onMount(close);
  return close;
}

function closeModal() {
  document.getElementById("modal-root").innerHTML = "";
}

function setTitle(title, actionsHtml = "") {
  document.getElementById("page-title").textContent = title;
  document.getElementById("topbar-actions").innerHTML = actionsHtml;
}
