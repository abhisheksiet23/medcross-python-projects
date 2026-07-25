Views.campaigns = {
  title: "Campaigns",
  state: { view: "list", selectedId: null },

  async render(container) {
    this.container = container;
    if (this.state.view === "detail" && this.state.selectedId) {
      return this.renderDetail();
    }
    return this.renderList();
  },

  async renderList() {
    setTitle("Campaigns", `<button class="btn" id="btn-new-campaign">+ Create Campaign</button>`);
    const campaigns = await API.get("/api/campaigns");

    this.container.innerHTML = `
      <div class="panel">
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Template</th><th>Group</th><th>Status</th><th>Sent</th><th>Delivered</th><th>Read</th><th>Replied</th><th>Created</th><th></th></tr></thead>
          <tbody>
            ${campaigns.length ? campaigns.map((c) => `
              <tr style="cursor:pointer" data-open="${c.id}">
                <td>${escapeHtml(c.name)}</td>
                <td>${escapeHtml(c.template_name || "—")}</td>
                <td>${escapeHtml(c.group_name || "—")}</td>
                <td>${badge(c.status)}</td>
                <td>${c.stats.sent}</td>
                <td>${c.stats.delivered}</td>
                <td>${c.stats.read}</td>
                <td>${c.stats.replied}</td>
                <td>${formatDate(c.created_at)}</td>
                <td>
                  ${c.status === "draft" || c.status === "scheduled" ? `<button class="btn small" data-send="${c.id}">Send Now</button>` : ""}
                  ${c.status === "sending" ? `<button class="btn secondary small" data-pause="${c.id}">Pause</button>` : ""}
                  ${c.status === "paused" ? `<button class="btn small" data-resume="${c.id}">Resume</button>` : ""}
                  <button class="btn ghost small" data-dup="${c.id}">Duplicate</button>
                </td>
              </tr>`).join("") : `<tr><td colspan="10" class="empty">No campaigns yet — create one to get started.</td></tr>`}
          </tbody>
        </table></div>
      </div>
    `;

    document.getElementById("btn-new-campaign").onclick = () => this.openCreate();
    document.querySelectorAll("[data-open]").forEach((el) => {
      el.onclick = (e) => {
        if (e.target.closest("button")) return;
        this.state.view = "detail";
        this.state.selectedId = el.dataset.open;
        this.renderDetail();
      };
    });
    document.querySelectorAll("[data-send]").forEach((btn) => btn.onclick = async (e) => {
      e.stopPropagation();
      await API.post(`/api/campaigns/${btn.dataset.send}/send`);
      toast("Campaign sending started", "success");
      this.renderList();
    });
    document.querySelectorAll("[data-pause]").forEach((btn) => btn.onclick = async (e) => {
      e.stopPropagation();
      await API.post(`/api/campaigns/${btn.dataset.pause}/pause`);
      toast("Campaign paused", "success");
      this.renderList();
    });
    document.querySelectorAll("[data-resume]").forEach((btn) => btn.onclick = async (e) => {
      e.stopPropagation();
      await API.post(`/api/campaigns/${btn.dataset.resume}/resume`);
      toast("Campaign resumed", "success");
      this.renderList();
    });
    document.querySelectorAll("[data-dup]").forEach((btn) => btn.onclick = async (e) => {
      e.stopPropagation();
      await API.post(`/api/campaigns/${btn.dataset.dup}/duplicate`);
      toast("Campaign duplicated as draft", "success");
      this.renderList();
    });
  },

  async renderDetail() {
    const c = await API.get(`/api/campaigns/${this.state.selectedId}`);
    setTitle(c.name, `<button class="btn secondary" id="btn-back">← Back to Campaigns</button>`);

    const s = c.stats;
    this.container.innerHTML = `
      <div class="stat-grid">
        <div class="stat-card"><div class="label">Recipients</div><div class="value">${s.recipients}</div></div>
        <div class="stat-card"><div class="label">Sent</div><div class="value">${s.sent}</div></div>
        <div class="stat-card"><div class="label">Delivered</div><div class="value">${s.delivered}</div></div>
        <div class="stat-card"><div class="label">Read</div><div class="value">${s.read}</div></div>
        <div class="stat-card"><div class="label">Failed</div><div class="value">${s.failed}</div></div>
        <div class="stat-card"><div class="label">Replied</div><div class="value">${s.replied}</div></div>
      </div>
      <div class="stat-grid" style="grid-template-columns:repeat(3,1fr)">
        <div class="stat-card"><div class="label">Delivery Rate</div><div class="value">${s.delivery_rate}%</div></div>
        <div class="stat-card"><div class="label">Read Rate</div><div class="value">${s.read_rate}%</div></div>
        <div class="stat-card"><div class="label">Response Rate</div><div class="value">${s.response_rate}%</div></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h3>Recipients</h3>${badge(c.status)}</div>
        <div class="table-wrap"><table>
          <thead><tr><th>Contact</th><th>Phone</th><th>Status</th><th>Sent</th><th>Delivered</th><th>Read</th><th>Failed reason</th></tr></thead>
          <tbody>
            ${c.recipients.length ? c.recipients.map((r) => `
              <tr>
                <td>${escapeHtml(r.contact_name || "—")}</td>
                <td>${escapeHtml(r.phone)}</td>
                <td>${badge(r.status)}</td>
                <td>${formatDate(r.sent_at)}</td>
                <td>${formatDate(r.delivered_at)}</td>
                <td>${formatDate(r.read_at)}</td>
                <td class="text-dim">${escapeHtml(r.failed_reason || "")}</td>
              </tr>`).join("") : `<tr><td colspan="7" class="empty">No recipients yet — click Send Now on the campaign list.</td></tr>`}
          </tbody>
        </table></div>
      </div>
    `;
    document.getElementById("btn-back").onclick = () => {
      this.state.view = "list";
      this.renderList();
    };
  },

  async openCreate() {
    const [templates, groups] = await Promise.all([API.get("/api/templates"), API.get("/api/groups")]);
    if (!templates.length) return toast("Create a template first (Templates page)", "error");
    if (!groups.length) return toast("Create a contact group first (Contacts page)", "error");

    openModal({
      title: "Create Campaign",
      bodyHtml: `
        <div class="field"><label>Campaign name</label><input id="c-name" placeholder="e.g. Diabetes Awareness Follow-up"></div>
        <div class="field"><label>Template</label>
          <select id="c-template">${templates.map((t) => `<option value="${t.id}">${escapeHtml(t.name)} (${escapeHtml(t.category)})</option>`).join("")}</select>
        </div>
        <div class="field"><label>Send to group</label>
          <select id="c-group">${groups.map((g) => `<option value="${g.id}">${escapeHtml(g.name)} (${g.contact_count} contacts)</option>`).join("")}</select>
        </div>
        <div class="field">
          <label><input type="checkbox" id="c-schedule-toggle" style="width:auto;display:inline-block;margin-right:6px">Schedule for later</label>
          <input type="datetime-local" id="c-schedule-at" style="display:none;margin-top:8px">
        </div>
      `,
      footerHtml: `<button class="btn secondary" id="cancel-c">Cancel</button><button class="btn" id="save-c">Create Campaign</button>`,
      onMount: (close) => {
        document.getElementById("cancel-c").onclick = close;
        document.getElementById("c-schedule-toggle").onchange = (e) => {
          document.getElementById("c-schedule-at").style.display = e.target.checked ? "block" : "none";
        };
        document.getElementById("save-c").onclick = async () => {
          const name = document.getElementById("c-name").value.trim();
          if (!name) return toast("Campaign name is required", "error");
          const scheduled = document.getElementById("c-schedule-toggle").checked;
          const scheduledAt = document.getElementById("c-schedule-at").value;
          if (scheduled && !scheduledAt) return toast("Pick a schedule date/time", "error");
          try {
            const res = await API.post("/api/campaigns", {
              name,
              template_id: Number(document.getElementById("c-template").value),
              group_id: Number(document.getElementById("c-group").value),
              scheduled_at: scheduled ? new Date(scheduledAt).toISOString() : null,
            });
            toast(scheduled ? "Campaign scheduled" : "Campaign created as draft — click Send Now when ready", "success");
            close();
            this.renderList();
          } catch (err) { toastError(err); }
        };
      },
    });
  },
};
