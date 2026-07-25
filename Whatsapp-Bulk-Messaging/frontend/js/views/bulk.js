Views.bulk = {
  title: "Bulk Replies",
  state: { results: [], selected: new Set() },

  async render(container) {
    this.container = container;
    setTitle("Bulk Replies");
    const [campaigns, groups] = await Promise.all([API.get("/api/campaigns"), API.get("/api/groups")]);

    container.innerHTML = `
      <div class="panel" style="margin-bottom:20px">
        <div class="panel-body">
          <div class="form-row">
            <div class="field">
              <label>Campaign</label>
              <select id="f-campaign"><option value="">Any campaign</option>${campaigns.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}</select>
            </div>
            <div class="field">
              <label>Reply contains</label>
              <input id="f-response" placeholder="e.g. YES">
            </div>
            <div class="field">
              <label>Group</label>
              <select id="f-group"><option value="">Any group</option>${groups.map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join("")}</select>
            </div>
          </div>
          <button class="btn" id="btn-filter">Filter Contacts</button>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h3>Matching Contacts</h3>
          <div>
            <button class="btn ghost small" id="btn-select-all">Select All</button>
            <button class="btn ghost small" id="btn-select-none">Clear</button>
          </div>
        </div>
        <div class="panel-body">
          <div id="results-list" class="checkbox-list"><div class="text-dim">Run a filter to see matching contacts.</div></div>
        </div>
      </div>

      <div class="panel" style="margin-top:20px">
        <div class="panel-body">
          <div class="field"><label>Message to send to all selected contacts</label>
            <textarea id="bulk-text" rows="3" placeholder="Type your message once…"></textarea>
          </div>
          <button class="btn" id="btn-send-bulk">Send to Selected (<span id="selected-count">0</span>)</button>
        </div>
      </div>
    `;

    document.getElementById("btn-filter").onclick = () => this.runFilter();
    document.getElementById("btn-select-all").onclick = () => this.selectAll(true);
    document.getElementById("btn-select-none").onclick = () => this.selectAll(false);
    document.getElementById("btn-send-bulk").onclick = () => this.sendBulk();
  },

  async runFilter() {
    const campaign_id = document.getElementById("f-campaign").value;
    const response_contains = document.getElementById("f-response").value.trim();
    const group_id = document.getElementById("f-group").value;
    const params = new URLSearchParams();
    if (campaign_id) params.set("campaign_id", campaign_id);
    if (response_contains) params.set("response_contains", response_contains);
    if (group_id) params.set("group_id", group_id);

    const results = await API.get(`/api/bulk/filter?${params}`);
    this.state.results = results;
    this.state.selected = new Set();
    this.renderResults();
  },

  renderResults() {
    const wrap = document.getElementById("results-list");
    const results = this.state.results;
    wrap.innerHTML = results.length ? results.map((c) => `
      <label>
        <input type="checkbox" data-id="${c.id}" ${this.state.selected.has(c.id) ? "checked" : ""}>
        ${escapeHtml(c.name || c.phone)} <span class="text-dim">${escapeHtml(c.phone)}${c.tags ? " · " + escapeHtml(c.tags) : ""}</span>
      </label>`).join("") : `<div class="text-dim">No contacts matched this filter.</div>`;

    wrap.querySelectorAll("[data-id]").forEach((cb) => {
      cb.onchange = () => {
        const id = Number(cb.dataset.id);
        if (cb.checked) this.state.selected.add(id); else this.state.selected.delete(id);
        this.updateCount();
      };
    });
    this.updateCount();
  },

  selectAll(value) {
    if (value) this.state.results.forEach((c) => this.state.selected.add(c.id));
    else this.state.selected.clear();
    this.renderResults();
  },

  updateCount() {
    document.getElementById("selected-count").textContent = this.state.selected.size;
  },

  async sendBulk() {
    const text = document.getElementById("bulk-text").value.trim();
    if (!text) return toast("Type a message first", "error");
    if (this.state.selected.size === 0) return toast("Select at least one contact", "error");
    if (!confirm(`Send this message to ${this.state.selected.size} contact(s)?`)) return;

    try {
      const res = await API.post("/api/bulk/send", { contact_ids: [...this.state.selected], text });
      toast(`Sent to ${res.sent} contact(s)${res.failed.length ? `, ${res.failed.length} failed` : ""}`,
            res.failed.length ? "error" : "success");
      document.getElementById("bulk-text").value = "";
    } catch (err) { toastError(err); }
  },
};
