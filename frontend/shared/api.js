// Shared API helpers used by the field, packhouse and admin views.
// Everything is served from the same origin as the backend, so API_BASE is relative.
const API_BASE = "";

const LW = {
  // Bump on every deploy that touches frontend code. Shown in each screen's
  // header so it's obvious at a glance whether a device's cached copy is
  // actually up to date - especially useful given the service workers'
  // cache-first strategy (see field/packhouse/admin service-worker.js).
  // Reset to 1.0 on 2026-08-06 to mark the first stable release.
  VERSION: "1.0",

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

  // Maps backend/weather.py's fixed condition strings to a Font Awesome
  // icon class - update both places together if a new condition is added.
  weatherIcon(condition) {
    const icons = {
      "Clear": "fa-sun",
      "Partly Cloudy": "fa-cloud-sun",
      "Overcast": "fa-cloud",
      "Cloudy": "fa-cloud",
      "Foggy": "fa-smog",
      "Drizzle": "fa-cloud-rain",
      "Rain": "fa-cloud-rain",
      "Heavy Rain": "fa-cloud-showers-heavy",
      "Showers": "fa-cloud-rain",
      "Heavy Showers": "fa-cloud-showers-heavy",
      "Snow": "fa-snowflake",
      "Heavy Snow": "fa-snowflake",
      "Storm": "fa-bolt",
    };
    return icons[condition] || "fa-cloud";
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

  // Short synthesized tones (no audio files needed, works fully offline).
  // Two distinct patterns so a worker can tell them apart by ear:
  // a single beep for a QR match, a two-note rising chime for a saved crate.
  _tone(frequency, duration, delay = 0) {
    try {
      const ctx = LW._audioCtx || (LW._audioCtx = new (window.AudioContext || window.webkitAudioContext)());
      if (ctx.state === "suspended") ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = frequency;
      const startAt = ctx.currentTime + delay;
      gain.gain.setValueAtTime(0.2, startAt);
      gain.gain.exponentialRampToValueAtTime(0.001, startAt + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(startAt);
      osc.stop(startAt + duration);
    } catch (e) { /* audio isn't critical - never block the capture flow on it */ }
  },
  beepScanned() { LW._tone(880, 0.12); },
  beepSaved() { LW._tone(660, 0.09); LW._tone(988, 0.14, 0.1); },

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
