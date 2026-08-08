// Owner View: read-only dashboard, no login - access is a single token in
// the URL (?key=...). See backend/routers/owner_view.py.

const OWNER_KEY = new URLSearchParams(location.search).get("key") || "";
let _systemSettings = null;

function showDenied() {
  document.getElementById("deniedScreen").classList.remove("hidden");
  document.getElementById("app").classList.add("hidden");
}

function updateBannerFarmName() {
  const el = document.getElementById("headerFarmName");
  if (el) el.textContent = (_systemSettings && _systemSettings.farm_name) || "Laughing Waters";
}

function updateBannerClock() {
  const el = document.getElementById("headerDateTime");
  if (!el) return;
  const now = new Date();
  const dateStr = now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const timeStr = now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  el.textContent = `${dateStr}  ·  ${timeStr}`;
}

async function updateBannerWeather() {
  const el = document.getElementById("headerWeather");
  if (!el) return;
  try {
    const w = await LW.api("/api/weather/current");
    if (w && w.temp !== undefined && w.temp !== null) {
      const icon = LW.weatherIcon(w.condition);
      el.innerHTML = `<i class="fa-solid ${icon}"></i> ${Math.round(w.temp)}°C · ${w.condition}${w.humidity != null ? ` · ${w.humidity}% humidity` : ""}`;
    }
  } catch (e) { /* nice-to-have only */ }
}

function bindCollapsibles() {
  document.querySelectorAll(".collapsible-header").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(btn.dataset.target).classList.toggle("hidden");
      const icon = btn.querySelector(".fa-chevron-down, .fa-chevron-up");
      if (icon) { icon.classList.toggle("fa-chevron-down"); icon.classList.toggle("fa-chevron-up"); }
    });
  });
}

function bindDashboard() {
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById("dashStart").value = today;
  document.getElementById("dashEnd").value = today;

  document.getElementById("dashRefreshBtn").addEventListener("click", refreshDashboard);
  document.getElementById("dashTodayBtn").addEventListener("click", () => {
    const t = new Date().toISOString().slice(0, 10);
    document.getElementById("dashStart").value = t;
    document.getElementById("dashEnd").value = t;
    refreshDashboard();
  });
  document.getElementById("dashWeekBtn").addEventListener("click", () => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 6);
    document.getElementById("dashStart").value = start.toISOString().slice(0, 10);
    document.getElementById("dashEnd").value = end.toISOString().slice(0, 10);
    refreshDashboard();
  });
  document.getElementById("dashSeasonBtn").addEventListener("click", () => {
    if (_systemSettings) {
      const year = _systemSettings.current_harvest_year || new Date().getFullYear();
      document.getElementById("dashStart").value = `${year}-01-01`;
      document.getElementById("dashEnd").value = `${year}-12-31`;
    }
    refreshDashboard();
  });
  document.getElementById("dashSupplierFilter").addEventListener("change", refreshDashboard);
}

async function loadSuppliers() {
  const select = document.getElementById("dashSupplierFilter");
  try {
    const suppliers = await LW.api("/api/suppliers");
    select.innerHTML = `<option value="">All farms / suppliers</option>` +
      suppliers.filter((s) => s.active).map((s) => `<option value="${s.id}">${s.name}${s.is_own_farm ? " (Own Farm)" : ""}</option>`).join("");
  } catch (e) { /* filter just stays on "All" if this fails */ }
}

function _lotTotals(lots) {
  return {
    crates: lots.reduce((s, l) => s + l.total_crates, 0),
    kg: lots.reduce((s, l) => s + l.total_kg, 0),
  };
}

async function refreshDashboard() {
  const start = document.getElementById("dashStart").value;
  const end = document.getElementById("dashEnd").value;
  const supplierId = document.getElementById("dashSupplierFilter").value;
  const supplierParam = supplierId ? `&supplier_id=${supplierId}` : "";
  const qs = `period_start=${start}&period_end=${end}${supplierParam}`;

  let harvesting, inTransit, received, summary;
  try {
    [harvesting, inTransit, received, summary] = await Promise.all([
      LW.api(`/api/lots/pending?${qs}`),
      LW.api(`/api/lots/in-transit?${qs}`),
      LW.api(`/api/lots/received?${qs}`),
      LW.api(`/api/owner-view/summary?token=${encodeURIComponent(OWNER_KEY)}&${qs}`),
    ]);
  } catch (e) {
    // A network failure is NOT an invalid key - show the offline banner and
    // keep whatever data is already on screen. Only a real HTTP rejection
    // (bad/expired key) gets the denied screen.
    if (e instanceof TypeError) {
      LW.setOffline(true);
      return;
    }
    showDenied();
    return;
  }
  LW.setOffline(false);

  renderDashboardKpis(harvesting, inTransit, received, summary);
  renderDashboardLists(harvesting, inTransit, received, summary);
}

function renderDashboardKpis(harvesting, inTransit, received, summary) {
  const h = _lotTotals(harvesting);
  const t = _lotTotals(inTransit);
  const r = _lotTotals(received);
  const allLots = [...harvesting, ...inTransit, ...received];
  const totalCrates = h.crates + t.crates + r.crates;
  const totalKg = h.kg + t.kg + r.kg;
  const avgKgPerLot = allLots.length ? totalKg / allLots.length : 0;
  const avgKgPerCrate = totalCrates ? totalKg / totalCrates : 0;

  const cards = [
    ["Teams Active", `${summary.active_teams} teams`],
    ["Workers Active", `${summary.active_workers} workers`],
    ["Blocks Active", `${summary.active_blocks} blocks`],
    ["Total Kg", `${totalKg.toFixed(1)} kg`],
    ["Total Crates", `${totalCrates} crates`],
    ["Avg Kg/Lot", avgKgPerLot.toFixed(1)],
    ["Avg Kg/Crate", avgKgPerCrate.toFixed(1)],
    ["Harvesting", `${h.crates} crates / ${h.kg.toFixed(1)} kg`],
    ["In Transit", `${t.crates} crates / ${t.kg.toFixed(1)} kg`],
    ["Received", `${r.crates} crates / ${r.kg.toFixed(1)} kg`],
  ];
  document.getElementById("dashKpiGrid").innerHTML = cards.map(([label, value]) => `
    <div class="bg-white rounded-xl shadow p-4">
      <div class="text-xs text-slate-500">${label}</div>
      <div class="text-xl font-bold">${value}</div>
    </div>
  `).join("");
}

function renderDashboardLists(harvesting, inTransit, received, summary) {
  const h = _lotTotals(harvesting);
  const t = _lotTotals(inTransit);
  const r = _lotTotals(received);

  document.getElementById("dash-harvesting-title").textContent = `Harvesting - ${h.crates} crates / ${h.kg.toFixed(1)} kg`;
  document.getElementById("dash-harvesting-body").innerHTML = harvesting.map((l) => `
    <div class="p-3 urgency-${l.urgency}">
      <div class="font-semibold text-sm">${l.slip_number} <span class="text-xs font-normal text-slate-500">${l.supplier_name}</span></div>
      <div class="text-sm">${l.total_crates} crates / ${l.total_kg} kg - ${l.age_minutes} min ago</div>
    </div>
  `).join("") || `<div class="p-3 text-sm text-slate-400">Nothing currently being harvested</div>`;

  document.getElementById("dash-intransit-title").textContent = `In transit - ${t.crates} crates / ${t.kg.toFixed(1)} kg`;
  document.getElementById("dash-intransit-body").innerHTML = inTransit.map((l) => `
    <div class="p-3 urgency-${l.urgency}">
      <div class="font-semibold text-sm">${l.slip_number} <span class="text-xs font-normal text-slate-500">${l.supplier_name}</span></div>
      <div class="text-sm">${l.total_crates} crates / ${l.total_kg} kg - ${l.age_minutes} min ago</div>
    </div>
  `).join("") || `<div class="p-3 text-sm text-slate-400">Nothing currently in transit</div>`;

  document.getElementById("dash-received-title").textContent = `Received - ${r.crates} crates / ${r.kg.toFixed(1)} kg`;
  document.getElementById("dash-received-body").innerHTML = received.map((l) => `
    <div class="p-3">
      <div class="font-semibold text-sm">${l.slip_number} <span class="text-xs font-normal text-slate-500">${l.supplier_name}</span></div>
      <div class="text-sm">${l.total_crates} crates / ${l.total_kg} kg - received ${new Date(l.received_at).toLocaleString()}</div>
    </div>
  `).join("") || `<div class="p-3 text-sm text-slate-400">Nothing received in this period</div>`;

  document.getElementById("dash-blocks-title").textContent = `Blocks - ${summary.blocks.length} blocks`;
  document.getElementById("dash-blocks-rows").innerHTML = summary.blocks.map((b) => `
    <tr class="border-b">
      <td class="p-2">${b.name}</td>
      <td class="p-2">${b.crates}</td>
      <td class="p-2">${b.total_kg}</td>
      <td class="p-2">${b.avg_kg_crate}</td>
      <td class="p-2">${b.avg_kg_tree ?? "-"}</td>
    </tr>
  `).join("") || `<tr><td class="p-2 text-slate-400" colspan="5">No harvest activity in this period</td></tr>`;
}

async function init() {
  if (!OWNER_KEY) { showDenied(); return; }

  document.getElementById("appVersion").textContent = `v${LW.VERSION}`;
  try {
    _systemSettings = await LW.api("/api/system-settings");
  } catch (e) { /* keep defaults if offline on first load */ }
  updateBannerFarmName();
  updateBannerClock();
  updateBannerWeather();
  setInterval(updateBannerClock, 1000);

  bindDashboard();
  bindCollapsibles();

  LW.offlineBanner("Offline - data may be out of date");
  LW.onOfflineChange = (off) => { if (!off) refreshDashboard(); };
  LWPTR.attach(async () => {
    await loadSuppliers();
    await refreshDashboard();
  });

  await loadSuppliers();
  await refreshDashboard();

  document.getElementById("app").classList.remove("hidden");
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("service-worker.js").catch(() => {});
}

document.addEventListener("DOMContentLoaded", init);
