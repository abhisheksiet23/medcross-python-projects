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

  previewIcon(type) {
    return { image: "📷 ", video: "🎥 ", audio: "🎤 ", document: "📄 ", sticker: "🌟 ", reaction: "" }[type] || "";
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
        <div class="preview">${c.last_direction === "out" ? "You: " : ""}${this.previewIcon(c.last_message_type)}${escapeHtml((c.last_message || "").slice(0, 50))}</div>
      </div>`).join("") : `<div class="empty">No conversations yet</div>`;

    wrap.querySelectorAll("[data-contact]").forEach((el) => {
      el.onclick = () => this.openThread(Number(el.dataset.contact));
    });
  },

  renderMessageBody(m) {
    // media_url is only present once the file was successfully downloaded from
    // WhatsApp's Media API; if it's missing (download failed, or it's not a media
    // message at all) we fall back to whatever text/placeholder is in `body`.
    // media_url from the backend is root-relative (e.g. "/media/xxx.jpg") — prefix
    // it with the same subpath-safe base api.js uses, or it 404s under IIS when the
    // app is hosted under a virtual path instead of the domain root.
    const mediaSrc = m.media_url ? API.BASE + m.media_url : null;
    if (m.message_type === "reaction") {
      return `<div style="font-size:22px">${escapeHtml(m.reaction_emoji || "👍")}</div><div class="text-dim" style="font-size:11px">reacted to a message</div>`;
    }
    if (mediaSrc) {
      if (m.message_type === "image" || m.message_type === "sticker") {
        return `<img src="${escapeHtml(mediaSrc)}" style="max-width:260px;border-radius:8px;display:block">${m.body ? `<div style="margin-top:6px">${escapeHtml(m.body)}</div>` : ""}`;
      }
      if (m.message_type === "video") {
        return `<video src="${escapeHtml(mediaSrc)}" controls style="max-width:260px;border-radius:8px;display:block">${m.body ? `<div style="margin-top:6px">${escapeHtml(m.body)}</div>` : ""}`;
      }
      if (m.message_type === "audio") {
        return `<audio src="${escapeHtml(mediaSrc)}" controls style="max-width:260px"></audio>`;
      }
      if (m.message_type === "document") {
        const filename = m.body || "Document";
        return `<a href="${escapeHtml(mediaSrc)}" target="_blank" rel="noopener" style="display:flex;align-items:center;gap:8px;text-decoration:underline">📄 ${escapeHtml(filename)}</a>`;
      }
    }
    if (["image", "video", "audio", "document", "sticker"].includes(m.message_type)) {
      // A media message where the download failed or hasn't completed
      return `<span class="text-dim">${this.previewIcon(m.message_type)}${escapeHtml(m.body || "Media unavailable")}</span>`;
    }
    return escapeHtml(m.body);
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
            ${this.renderMessageBody(m)}
            <span class="meta">${m.direction === "out" ? badge(m.status) : ""} ${timeOnly(m.created_at)}</span>
          </div>`).join("") : `<div class="empty">No messages yet</div>`}
      </div>
      <div class="thread-input">
        <button class="btn secondary" id="attach-media" title="Attach image, document, audio, or video">📎</button>
        <input type="file" id="media-file-input" style="display:none">
        <input id="reply-text" placeholder="Type a message… (or attach a file below)">
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

    document.getElementById("attach-media").onclick = () => {
      document.getElementById("media-file-input").click();
    };
    document.getElementById("media-file-input").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const captionInput = document.getElementById("reply-text");
      const caption = captionInput.value.trim();
      const fd = new FormData();
      fd.append("file", file);
      if (caption) fd.append("caption", caption);
      const btn = document.getElementById("attach-media");
      btn.disabled = true;
      btn.textContent = "…";
      try {
        await API.upload(`/api/inbox/conversations/${contactId}/send-media`, fd);
        captionInput.value = "";
        this.openThread(contactId);
        this.loadConversations();
      } catch (err) {
        toastError(err);
        btn.disabled = false;
        btn.textContent = "📎";
      } finally {
        e.target.value = "";
      }
    };

    // clear unread indicator locally
    const item = this.state.conversations.find((c) => c.contact_id === contactId);
    if (item) item.unread_count = 0;
    this.loadConversations();
  },
};