const API = (() => {
  // Derive the base path from where this script itself was loaded — works whether the
  // app is hosted at the domain root (http://server/) or under an IIS virtual path
  // (http://server/somepath/). Root-relative "/api/..." paths break under a subpath;
  // this doesn't, because it's computed from the actual URL the browser used to fetch
  // this very file, not from a hardcoded assumption about where the site lives.
  const BASE = (() => {
    try {
      const src = document.currentScript && document.currentScript.src;
      if (src) {
        const path = new URL(src).pathname;
        return path.replace(/js\/api\.js$/, "").replace(/\/$/, "");
      }
    } catch (_) {}
    return "";
  })();

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

  return { get, post, put, del, upload, BASE };
})();