Views.logs = {
  title: "Message Logs",
  state: { page: 1 },

  async render(container) {
    this.container = container;
    setTitle("Message Logs");
    const campaigns = await API.get("/api/campaigns");

    container.innerHTML = `
      <div class="toolbar">
        <input id="f-phone" placeholder="Phone number">
        <select id="f-campaign"><option value="">All campaigns</option>${campaigns.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}</select>
        <select id="f-status">
          <option value="">All statuses</option>
          ${["sent", "delivered", "read", "failed", "received"].map((s) => `<option value="${s}">${s}</option>`).join("")}
        </select>
        <input id="f-template" placeholder="Template name">
        <input id="f-from" type="date">
        <input id="f-to" type="date">
        <button class="btn" id="btn-filter-logs">Filter</button>
      </div>
      <div class="panel">
        <div class="table-wrap"><table>
          <thead><tr><th>Time</th><th>Contact</th><th>Phone</th><th>Direction</th><th>Message</th><th>Template</th><th>Campaign</th><th>Status</th></tr></thead>
          <tbody id="logs-tbody"><tr><td colspan="8" class="empty">Loading…</td></tr></tbody>
        </table></div>
      </div>
      <div id="logs-pagination" class="toolbar" style="margin-top:14px"></div>
    `;
    document.getElementById("btn-filter-logs").onclick = () => { this.state.page = 1; this.load(); };
    await this.load();
  },

  async load() {
    const params = new URLSearchParams({ page: this.state.page, limit: 50 });
    const phone = document.getElementById("f-phone").value.trim();
    const campaign_id = document.getElementById("f-campaign").value;
    const status = document.getElementById("f-status").value;
    const template_name = document.getElementById("f-template").value.trim();
    const dateFrom = document.getElementById("f-from").value;
    const dateTo = document.getElementById("f-to").value;
    if (phone) params.set("phone", phone);
    if (campaign_id) params.set("campaign_id", campaign_id);
    if (status) params.set("status", status);
    if (template_name) params.set("template_name", template_name);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo + "T23:59:59");

    const res = await API.get(`/api/logs?${params}`);
    document.getElementById("logs-tbody").innerHTML = res.data.length ? res.data.map((m) => `
      <tr>
        <td>${formatDate(m.created_at)}</td>
        <td>${escapeHtml(m.contact_name || "—")}</td>
        <td>${escapeHtml(m.phone)}</td>
        <td>${m.direction === "in" ? "Received" : "Sent"}</td>
        <td>${escapeHtml((m.body || "").slice(0, 60))}</td>
        <td>${escapeHtml(m.template_name || "—")}</td>
        <td>${escapeHtml(m.campaign_name || "—")}</td>
        <td>${badge(m.status)}</td>
      </tr>`).join("") : `<tr><td colspan="8" class="empty">No messages match these filters</td></tr>`;

    const totalPages = Math.max(1, Math.ceil(res.total / res.limit));
    document.getElementById("logs-pagination").innerHTML = `
      <button class="btn secondary small" ${this.state.page <= 1 ? "disabled" : ""} id="logs-prev">← Prev</button>
      <span class="text-dim">Page ${this.state.page} of ${totalPages} (${res.total} messages)</span>
      <button class="btn secondary small" ${this.state.page >= totalPages ? "disabled" : ""} id="logs-next">Next →</button>
    `;
    const prev = document.getElementById("logs-prev"), next = document.getElementById("logs-next");
    if (prev) prev.onclick = () => { this.state.page--; this.load(); };
    if (next) next.onclick = () => { this.state.page++; this.load(); };
  },
};
