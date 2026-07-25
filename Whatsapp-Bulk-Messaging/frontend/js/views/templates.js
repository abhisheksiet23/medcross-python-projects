Views.templates = {
  title: "Templates",

  async render(container) {
    this.container = container;
    setTitle("Templates", `<button class="btn" id="btn-new-template">+ Add Template</button>`);
    await this.load();
    document.getElementById("btn-new-template").onclick = () => this.openForm();
  },

  async load() {
    const templates = await API.get("/api/templates");
    this.container.innerHTML = `
      <p class="text-dim" style="margin-bottom:16px">
        These records mirror the templates you've had approved in Meta Business Manager. The <b>name</b> must match exactly —
        this app doesn't submit templates to Meta for approval, it just tracks and uses the ones you've already got approved.
      </p>
      <div class="panel">
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Category</th><th>Language</th><th>Preview</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${templates.length ? templates.map((t) => `
              <tr>
                <td>${escapeHtml(t.name)}</td>
                <td>${escapeHtml(t.category)}</td>
                <td>${escapeHtml(t.language_code)}</td>
                <td class="text-dim">${escapeHtml((t.body_preview || "").slice(0, 60))}</td>
                <td>${badge(t.status)}</td>
                <td>
                  <button class="btn ghost small" data-edit="${t.id}">Edit</button>
                  <button class="btn ghost small" data-del="${t.id}">Delete</button>
                </td>
              </tr>`).join("") : `<tr><td colspan="6" class="empty">No templates yet — add the ones approved in Meta Business Manager.</td></tr>`}
          </tbody>
        </table></div>
      </div>
    `;
    document.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.onclick = () => this.openForm(templates.find((t) => t.id == btn.dataset.edit));
    });
    document.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Delete this template record?")) return;
        await API.del(`/api/templates/${btn.dataset.del}`);
        toast("Template deleted", "success");
        this.load();
      };
    });
  },

  openForm(t) {
    openModal({
      title: t ? "Edit Template" : "Add Template",
      bodyHtml: `
        <div class="field"><label>Template name (must match Meta exactly)</label><input id="t-name" value="${escapeHtml(t?.name || "")}"></div>
        <div class="form-row">
          <div class="field"><label>Category</label>
            <select id="t-category">
              ${["MARKETING", "UTILITY", "AUTHENTICATION"].map((c) => `<option ${t?.category === c ? "selected" : ""}>${c}</option>`).join("")}
            </select>
          </div>
          <div class="field"><label>Language code</label><input id="t-lang" value="${escapeHtml(t?.language_code || "en_US")}"></div>
        </div>
        <div class="field"><label>Body preview (use {{1}}, {{2}}… for variables)</label>
          <textarea id="t-body" rows="3">${escapeHtml(t?.body_preview || "")}</textarea></div>
        <div class="form-row">
          <div class="field"><label>Variable count</label><input id="t-varcount" type="number" min="0" value="${t?.variable_count ?? 0}"></div>
          <div class="field"><label>Status</label>
            <select id="t-status">${["approved", "pending", "rejected"].map((s) => `<option ${t?.status === s ? "selected" : ""}>${s}</option>`).join("")}</select>
          </div>
        </div>
      `,
      footerHtml: `<button class="btn secondary" id="cancel-t">Cancel</button><button class="btn" id="save-t">Save</button>`,
      onMount: (close) => {
        document.getElementById("cancel-t").onclick = close;
        document.getElementById("save-t").onclick = async () => {
          const name = document.getElementById("t-name").value.trim();
          if (!name) return toast("Template name is required", "error");
          const body = {
            name,
            category: document.getElementById("t-category").value,
            language_code: document.getElementById("t-lang").value || "en_US",
            body_preview: document.getElementById("t-body").value,
            variable_count: Number(document.getElementById("t-varcount").value) || 0,
            status: document.getElementById("t-status").value,
          };
          try {
            if (t) await API.put(`/api/templates/${t.id}`, body);
            else await API.post("/api/templates", body);
            toast("Template saved", "success");
            close();
            this.load();
          } catch (err) { toastError(err); }
        };
      },
    });
  },
};
