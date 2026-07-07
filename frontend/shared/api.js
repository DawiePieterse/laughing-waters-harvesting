// Shared API helpers used by the field, packhouse and admin views.
// Everything is served from the same origin as the backend, so API_BASE is relative.
const API_BASE = "";

const LW = {
  getDeviceId() { return localStorage.getItem("lw_device_id"); },
  setDeviceId(id) { localStorage.setItem("lw_device_id", id); },
  clearDeviceId() { localStorage.removeItem("lw_device_id"); },

  getToken() { return localStorage.getItem("lw_admin_token"); },
  setToken(t) { localStorage.setItem("lw_admin_token", t); },
  clearToken() { localStorage.removeItem("lw_admin_token"); },

  getLastReceivedBy() { return localStorage.getItem("lw_last_received_by") || ""; },
  setLastReceivedBy(name) { localStorage.setItem("lw_last_received_by", name); },

  async fetchDeviceConfig(deviceId) {
    const res = await fetch(`${API_BASE}/api/devices/${encodeURIComponent(deviceId)}`);
    if (!res.ok) throw new Error("Unknown device id");
    const config = await res.json();
    localStorage.setItem("lw_device_config", JSON.stringify(config));
    return config;
  },

  // Used by the field/packhouse apps so a device that was already set up
  // keeps working (offline) even when it can't reach the server to
  // re-confirm its config on reload - only a brand new/unknown device id
  // needs connectivity to complete setup.
  async fetchDeviceConfigOfflineTolerant(deviceId) {
    try {
      return await LW.fetchDeviceConfig(deviceId);
    } catch (e) {
      const cached = localStorage.getItem("lw_device_config");
      if (cached) {
        const config = JSON.parse(cached);
        if (config.id === deviceId) return config;
      }
      throw e;
    }
  },

  async login(username, password) {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/api/auth/login`, { method: "POST", body });
    if (!res.ok) throw new Error("Invalid username or password");
    const data = await res.json();
    LW.setToken(data.access_token);
    return data;
  },

  async api(path, { method = "GET", body, auth = false, isForm = false } = {}) {
    const headers = {};
    if (auth) {
      const token = LW.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    let payload = body;
    if (body && !isForm) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${text}`);
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return res.json();
    return res.blob();
  },

  toast(message) {
    let el = document.getElementById("lw-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "lw-toast";
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove("show"), 2200);
  },

  downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  },
};
