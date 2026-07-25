const API = (() => {
  const BASE = ""; // served from the same origin as the API

  async function handle(resp) {
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const data = await resp.json();
        detail = data.detail || JSON.stringify(data);
      } catch (_) {}
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (resp.status === 204) return null;
    return resp.json();
  }

  function get(path) {
    return fetch(BASE + path).then(handle);
  }
  function post(path, body) {
    return fetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(handle);
  }
  function put(path, body) {
    return fetch(BASE + path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(handle);
  }
  function del(path) {
    return fetch(BASE + path, { method: "DELETE" }).then(handle);
  }
  function upload(path, formData) {
    return fetch(BASE + path, { method: "POST", body: formData }).then(handle);
  }

  return { get, post, put, del, upload };
})();
