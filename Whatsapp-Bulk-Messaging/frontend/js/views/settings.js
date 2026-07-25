Views.settings = {
  title: "Settings",

  async render(container) {
    this.container = container;
    setTitle("Settings");
    const s = await API.get("/api/settings");

    container.innerHTML = `
      <div class="panel" style="max-width:640px">
        <div class="panel-header"><h3>WhatsApp API Credentials</h3></div>
        <div class="panel-body">
          <div class="field"><label>Access Token</label><input id="s-token" placeholder="${escapeHtml(s.whatsapp_token) || "Not set"}"></div>
          <div class="field"><label>Phone Number ID</label><input id="s-phone-id" value="${escapeHtml(s.whatsapp_phone_number_id)}"></div>
          <div class="field"><label>WhatsApp Business Account ID</label><input id="s-waba-id" value="${escapeHtml(s.whatsapp_business_account_id)}"></div>
          <div class="field"><label>API Version</label><input id="s-api-version" value="${escapeHtml(s.whatsapp_api_version)}"></div>
          <p class="text-dim" style="font-size:12px">Leave Access Token blank to keep the currently saved value — it's masked here for security.</p>
        </div>
      </div>

      <div class="panel" style="max-width:640px;margin-top:20px">
        <div class="panel-header"><h3>Webhook</h3></div>
        <div class="panel-body">
          <div class="field"><label>Verify Token</label><input id="s-verify-token" value="${escapeHtml(s.whatsapp_verify_token)}"></div>
          <p class="text-dim" style="font-size:12px">
            In Meta Developer Console, set the Callback URL to <code>https://your-domain.com/webhook</code>
            and use this Verify Token during the subscription handshake.
          </p>
        </div>
      </div>

      <div class="panel" style="max-width:640px;margin-top:20px">
        <div class="panel-header"><h3>Business Account</h3></div>
        <div class="panel-body">
          <div class="field"><label>Business Name</label><input id="s-business-name" value="${escapeHtml(s.business_name)}"></div>
        </div>
      </div>

      <button class="btn" id="btn-save-settings" style="margin-top:20px">Save Settings</button>
    `;

    document.getElementById("btn-save-settings").onclick = async () => {
      const body = {
        whatsapp_phone_number_id: document.getElementById("s-phone-id").value,
        whatsapp_business_account_id: document.getElementById("s-waba-id").value,
        whatsapp_api_version: document.getElementById("s-api-version").value,
        whatsapp_verify_token: document.getElementById("s-verify-token").value,
        business_name: document.getElementById("s-business-name").value,
      };
      const token = document.getElementById("s-token").value.trim();
      if (token) body.whatsapp_token = token;
      try {
        await API.put("/api/settings", body);
        toast("Settings saved", "success");
        this.render(this.container);
      } catch (err) { toastError(err); }
    };
  },
};
