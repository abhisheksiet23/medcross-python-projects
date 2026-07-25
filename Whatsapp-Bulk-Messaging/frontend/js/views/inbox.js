Views.inbox = {
  title: "Inbox",
  state: { activeContactId: null, conversations: [] },

  async render(container) {
    this.container = container;
    setTitle("Inbox");
    container.innerHTML = `
      <div class="inbox-layout">
        <div class="conv-list">
          <div class="conv-search"><input id="inbox-search" placeholder="Search conversations…"></div>
          <div id="conv-items"><div class="empty">Loading…</div></div>
        </div>
        <div class="thread-pane" id="thread-pane">
          <div class="thread-empty">Select a conversation to view messages</div>
        </div>
      </div>
    `;
    document.getElementById("inbox-search").oninput = (e) => this.loadConversations(e.target.value);
    await this.loadConversations();
  },

  async loadConversations(q) {
    const params = q ? `?q=${encodeURIComponent(q)}` : "";
    const conversations = await API.get(`/api/inbox/conversations${params}`);
    this.state.conversations = conversations;
    const wrap = document.getElementById("conv-items");
    wrap.innerHTML = conversations.length ? conversations.map((c) => `
      <div class="conv-item ${c.contact_id === this.state.activeContactId ? "active" : ""}" data-contact="${c.contact_id}">
        <div class="name">
          <span>${escapeHtml(c.name || c.phone)}</span>
          ${c.unread_count > 0 ? `<span class="unread-dot">${c.unread_count}</span>` : ""}
        </div>
        <div class="preview">${c.last_direction === "out" ? "You: " : ""}${escapeHtml((c.last_message || "").slice(0, 50))}</div>
      </div>`).join("") : `<div class="empty">No conversations yet</div>`;

    wrap.querySelectorAll("[data-contact]").forEach((el) => {
      el.onclick = () => this.openThread(Number(el.dataset.contact));
    });
  },

  async openThread(contactId) {
    this.state.activeContactId = contactId;
    document.querySelectorAll(".conv-item").forEach((el) => {
      el.classList.toggle("active", Number(el.dataset.contact) === contactId);
    });

    const data = await API.get(`/api/inbox/conversations/${contactId}`);
    const pane = document.getElementById("thread-pane");
    pane.innerHTML = `
      <div class="thread-header">${escapeHtml(data.contact.name || data.contact.phone)} <span class="text-dim">${escapeHtml(data.contact.phone)}</span></div>
      <div class="thread-messages" id="thread-messages">
        ${data.messages.length ? data.messages.map((m) => `
          <div class="bubble ${m.direction}">
            ${escapeHtml(m.body)}
            <span class="meta">${m.direction === "out" ? badge(m.status) : ""} ${timeOnly(m.created_at)}</span>
          </div>`).join("") : `<div class="empty">No messages yet</div>`}
      </div>
      <div class="thread-input">
        <input id="reply-text" placeholder="Type a message…">
        <button class="btn" id="send-reply">Send</button>
      </div>
    `;
    const messagesEl = document.getElementById("thread-messages");
    messagesEl.scrollTop = messagesEl.scrollHeight;

    const send = async () => {
      const input = document.getElementById("reply-text");
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      try {
        await API.post(`/api/inbox/conversations/${contactId}/reply`, { text });
        this.openThread(contactId);
        this.loadConversations();
      } catch (err) { toastError(err); }
    };
    document.getElementById("send-reply").onclick = send;
    document.getElementById("reply-text").addEventListener("keydown", (e) => {
      if (e.key === "Enter") send();
    });

    // clear unread indicator locally
    const item = this.state.conversations.find((c) => c.contact_id === contactId);
    if (item) item.unread_count = 0;
    this.loadConversations();
  },
};
