Views.dashboard = {
  title: "Dashboard",
  async render(container) {
    const s = await API.get("/api/dashboard/stats");

    const cards = [
      ["Total Contacts", s.total_contacts],
      ["Active Campaigns", s.active_campaigns],
      ["Messages Sent", s.messages_sent],
      ["Delivered", s.delivered],
      ["Read", s.read],
      ["Replies Received", s.replies_received],
      ["Failed Messages", s.failed_messages],
    ];

    container.innerHTML = `
      <div class="stat-grid">
        ${cards.map(([label, value]) => `
          <div class="stat-card">
            <div class="label">${label}</div>
            <div class="value">${value ?? 0}</div>
          </div>`).join("")}
      </div>

      <div class="panel">
        <div class="panel-header"><h3>Recent Activity</h3></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Contact</th><th>Phone</th><th>Direction</th><th>Message</th><th>Status</th><th>Time</th></tr></thead>
            <tbody>
              ${s.recent_activity.length ? s.recent_activity.map((m) => `
                <tr>
                  <td>${escapeHtml(m.contact_name || "Unknown")}</td>
                  <td>${escapeHtml(m.phone)}</td>
                  <td>${m.direction === "in" ? "⬅️ Received" : "➡️ Sent"}</td>
                  <td>${escapeHtml((m.body || "").slice(0, 60))}</td>
                  <td>${badge(m.status)}</td>
                  <td>${formatDate(m.created_at)}</td>
                </tr>`).join("") : `<tr><td colspan="6" class="empty">No activity yet</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },
};
