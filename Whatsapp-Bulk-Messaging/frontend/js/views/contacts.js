Views.contacts = {
  title: "Contacts",
  state: { page: 1, q: "", group_id: "", groups: [] },

  async render(container) {
    const st = this.state;
    st.groups = await API.get("/api/groups");

    setTitle("Contacts", `
      <button class="btn secondary" id="btn-groups">Manage Groups</button>
      <button class="btn secondary" id="btn-import">Import CSV</button>
      <button class="btn" id="btn-add-contact">+ Add Contact</button>
    `);

    container.innerHTML = `
      <div class="toolbar">
        <input id="search" placeholder="Search name / phone / email" value="${escapeHtml(st.q)}">
        <select id="group-filter">
          <option value="">All groups</option>
          ${st.groups.map((g) => `<option value="${g.id}" ${String(g.id) === String(st.group_id) ? "selected" : ""}>${escapeHtml(g.name)} (${g.contact_count})</option>`).join("")}
        </select>
      </div>
      <div class="panel">
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Group</th><th>Tags</th><th>Updated</th><th></th></tr></thead>
          <tbody id="contacts-tbody"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody>
        </table></div>
      </div>
      <div id="pagination" class="toolbar" style="margin-top:14px"></div>
    `;

    document.getElementById("btn-add-contact").onclick = () => this.openForm();
    document.getElementById("btn-groups").onclick = () => this.openGroups();
    document.getElementById("btn-import").onclick = () => this.openImport();
    document.getElementById("search").oninput = (e) => { st.q = e.target.value; st.page = 1; this.load(); };
    document.getElementById("group-filter").onchange = (e) => { st.group_id = e.target.value; st.page = 1; this.load(); };

    await this.load();
  },

  async load() {
    const st = this.state;
    const params = new URLSearchParams({ page: st.page, limit: 20 });
    if (st.q) params.set("q", st.q);
    if (st.group_id) params.set("group_id", st.group_id);
    const res = await API.get(`/api/contacts?${params}`);

    document.getElementById("contacts-tbody").innerHTML = res.data.length ? res.data.map((c) => `
      <tr>
        <td>${escapeHtml(c.name || "—")}</td>
        <td>${escapeHtml(c.phone)}</td>
        <td>${escapeHtml(c.email || "—")}</td>
        <td>${escapeHtml(c.group_name || "—")}</td>
        <td>${escapeHtml(c.tags || "—")}</td>
        <td>${formatDate(c.updated_at)}</td>
        <td>
          <button class="btn ghost small" data-edit="${c.id}">Edit</button>
          <button class="btn ghost small" data-del="${c.id}">Delete</button>
        </td>
      </tr>`).join("") : `<tr><td colspan="7" class="empty">No contacts found</td></tr>`;

    document.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.onclick = () => this.openForm(res.data.find((c) => c.id == btn.dataset.edit));
    });
    document.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Delete this contact?")) return;
        await API.del(`/api/contacts/${btn.dataset.del}`);
        toast("Contact deleted", "success");
        this.load();
      };
    });

    const totalPages = Math.max(1, Math.ceil(res.total / res.limit));
    document.getElementById("pagination").innerHTML = `
      <button class="btn secondary small" ${st.page <= 1 ? "disabled" : ""} id="prev-page">← Prev</button>
      <span class="text-dim">Page ${st.page} of ${totalPages} (${res.total} contacts)</span>
      <button class="btn secondary small" ${st.page >= totalPages ? "disabled" : ""} id="next-page">Next →</button>
    `;
    const prev = document.getElementById("prev-page"), next = document.getElementById("next-page");
    if (prev) prev.onclick = () => { st.page--; this.load(); };
    if (next) next.onclick = () => { st.page++; this.load(); };
  },

  openForm(contact) {
    const st = this.state;
    const groupOptions = st.groups.map((g) => `<option value="${g.id}" ${contact?.group_id === g.id ? "selected" : ""}>${escapeHtml(g.name)}</option>`).join("");
    openModal({
      title: contact ? "Edit Contact" : "Add Contact",
      bodyHtml: `
        <div class="field"><label>Name</label><input id="f-name" value="${escapeHtml(contact?.name || "")}"></div>
        <div class="field"><label>Phone (with country code)</label><input id="f-phone" value="${escapeHtml(contact?.phone || "")}" placeholder="e.g. 919876543210"></div>
        <div class="field"><label>Email</label><input id="f-email" value="${escapeHtml(contact?.email || "")}"></div>
        <div class="field"><label>Group</label><select id="f-group"><option value="">No group</option>${groupOptions}</select></div>
        <div class="field"><label>Tags (comma separated)</label><input id="f-tags" value="${escapeHtml(contact?.tags || "")}" placeholder="vip, diabetes"></div>
      `,
      footerHtml: `<button class="btn secondary" id="cancel-btn">Cancel</button><button class="btn" id="save-btn">Save</button>`,
      onMount: (close) => {
        document.getElementById("cancel-btn").onclick = close;
        document.getElementById("f-group").value = contact?.group_id || "";
        document.getElementById("save-btn").onclick = async () => {
          const body = {
            name: document.getElementById("f-name").value || null,
            phone: document.getElementById("f-phone").value,
            email: document.getElementById("f-email").value || null,
            group_id: document.getElementById("f-group").value ? Number(document.getElementById("f-group").value) : null,
            tags: document.getElementById("f-tags").value || null,
          };
          if (!body.phone) return toast("Phone number is required", "error");
          try {
            if (contact) await API.put(`/api/contacts/${contact.id}`, body);
            else await API.post("/api/contacts", body);
            toast("Contact saved", "success");
            close();
            this.load();
          } catch (err) { toastError(err); }
        };
      },
    });
  },

  openGroups() {
    const st = this.state;
    const render = () => `
      <div class="field"><label>New group name</label>
        <div class="flex gap-8"><input id="g-name" placeholder="e.g. Diabetes Patients"><button class="btn small" id="g-add">Add</button></div>
      </div>
      <div class="checkbox-list">
        ${st.groups.length ? st.groups.map((g) => `
          <div class="flex items-center" style="justify-content:space-between;padding:6px 0">
            <span>${escapeHtml(g.name)} <span class="text-dim">(${g.contact_count})</span></span>
            <button class="btn ghost small" data-del-group="${g.id}">Delete</button>
          </div>`).join("") : `<div class="text-dim">No groups yet</div>`}
      </div>`;

    const close = openModal({
      title: "Manage Groups",
      bodyHtml: render(),
      footerHtml: `<button class="btn secondary" id="close-groups">Close</button>`,
      onMount: (closeFn) => this.wireGroups(closeFn, render),
    });
  },

  wireGroups(closeFn, render) {
    document.getElementById("close-groups").onclick = closeFn;
    document.getElementById("g-add").onclick = async () => {
      const name = document.getElementById("g-name").value.trim();
      if (!name) return;
      try {
        await API.post("/api/groups", { name });
        this.state.groups = await API.get("/api/groups");
        document.querySelector(".modal-body").innerHTML = render();
        this.wireGroups(closeFn, render);
        this.load();
      } catch (err) { toastError(err); }
    };
    document.querySelectorAll("[data-del-group]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Delete this group? Contacts will be unassigned, not deleted.")) return;
        await API.del(`/api/groups/${btn.dataset.delGroup}`);
        this.state.groups = await API.get("/api/groups");
        document.querySelector(".modal-body").innerHTML = render();
        this.wireGroups(closeFn, render);
        this.load();
      };
    });
  },

  openImport() {
    const st = this.state;
    openModal({
      title: "Import Contacts (CSV)",
      bodyHtml: `
        <p class="text-dim">CSV columns: <b>name, phone, email, tags</b> (only phone is required). Existing contacts with the same phone number will be updated.</p>
        <div class="field"><label>CSV file</label><input type="file" id="csv-file" accept=".csv"></div>
        <div class="field"><label>Assign to group (optional)</label>
          <select id="csv-group"><option value="">No group</option>${st.groups.map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join("")}</select>
        </div>
        <div id="import-result"></div>
      `,
      footerHtml: `<button class="btn secondary" id="cancel-import">Cancel</button><button class="btn" id="do-import">Import</button>`,
      onMount: (close) => {
        document.getElementById("cancel-import").onclick = close;
        document.getElementById("do-import").onclick = async () => {
          const file = document.getElementById("csv-file").files[0];
          if (!file) return toast("Choose a CSV file first", "error");
          const fd = new FormData();
          fd.append("file", file);
          const groupId = document.getElementById("csv-group").value;
          const qs = groupId ? `?group_id=${groupId}` : "";
          try {
            const res = await API.upload(`/api/contacts/import${qs}`, fd);
            document.getElementById("import-result").innerHTML = `
              <p class="text-dim">Imported/updated: <b>${res.imported_or_updated}</b>, skipped: <b>${res.skipped}</b></p>
              ${res.errors.length ? `<pre style="white-space:pre-wrap;font-size:12px">${res.errors.map(escapeHtml).join("\n")}</pre>` : ""}`;
            toast("Import complete", "success");
            this.load();
          } catch (err) { toastError(err); }
        };
      },
    });
  },
};
