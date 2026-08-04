// Field harvest capture: offline-first. Every crate is written to IndexedDB
// first, then a background loop pushes it to the server whenever a network
// request actually succeeds - the UI never blocks on connectivity.

let deviceConfig = null;
let systemSettings = { green_to_yellow_minutes: 90, yellow_to_red_minutes: 150 };
let weightBuffer = "";

const PENDING_LOTS_KEY = "lw_pending_lots";
const CURRENT_SLIP_KEY = "lw_current_slip";

function getCurrentSlip() {
  let slip = localStorage.getItem(CURRENT_SLIP_KEY);
  if (!slip) {
    slip = newSlipNumber();
    localStorage.setItem(CURRENT_SLIP_KEY, slip);
  }
  return slip;
}

function newSlipNumber() {
  const now = new Date();
  const stamp = now.toISOString().replace(/[-:T.]/g, "").slice(0, 14);
  return `${deviceConfig.id}-${stamp}`;
}

function getPendingLots() {
  return JSON.parse(localStorage.getItem(PENDING_LOTS_KEY) || "[]");
}
function setPendingLots(lots) {
  localStorage.setItem(PENDING_LOTS_KEY, JSON.stringify(lots));
}

async function init() {
  document.getElementById("appVersion").textContent = `v${LW.VERSION}`;
  const deviceId = LW.getDeviceId();
  if (!deviceId) { location.href = "../"; return; }
  try {
    deviceConfig = await LW.fetchDeviceConfigOfflineTolerant(deviceId);
  } catch (e) {
    location.href = "../";
    return;
  }
  document.getElementById("stationLabel").textContent =
    `${deviceConfig.station} - Team ${deviceConfig.team_id || "?"} - Induna ${deviceConfig.induna || "?"}`;

  try {
    systemSettings = await LW.api("/api/system-settings");
  } catch (e) { /* keep defaults if offline on first load */ }

  await loadWorkers();
  await loadBlocks();
  await renderLot();
  setInterval(renderLot, 15000);
  setInterval(syncLoop, 10000);
  setInterval(async () => { await loadWorkers(); await loadBlocks(); }, 30000);
  window.addEventListener("online", syncLoop);
  syncLoop();

  bindKeypad();
  updateWorkerDisplay();
  renderDispatchedLots();
  document.getElementById("saveCrateBtn").addEventListener("click", saveCrate);
  document.getElementById("sendSlipBtn").addEventListener("click", openDriverModal);
  document.getElementById("cancelSlipBtn").addEventListener("click", closeDriverModal);
  document.getElementById("confirmSlipBtn").addEventListener("click", sendPickingSlip);
  document.getElementById("scanBtn").addEventListener("click", openScanner);
  document.getElementById("closeScanBtn").addEventListener("click", closeScanner);
}

async function loadWorkers() {
  const select = document.getElementById("workerSelect");
  try {
    const workers = await LW.api("/api/workers");
    localStorage.setItem("lw_cached_workers", JSON.stringify(workers));
    renderWorkerOptions(workers);
  } catch (e) {
    const cached = localStorage.getItem("lw_cached_workers");
    if (cached) renderWorkerOptions(JSON.parse(cached));
    else select.innerHTML = `<option value="">(offline - worker list unavailable)</option>`;
  }
}

function renderWorkerOptions(workers) {
  const select = document.getElementById("workerSelect");
  const current = select.value;
  const active = workers.filter((w) => w.active);
  select.innerHTML = `<option value="">— select —</option>` + active.map((w) => {
    const display = w.name || `${w.first_name || ""} ${w.last_name || ""}`.trim() || w.id;
    return `<option value="${w.id}">${display} (${w.id})</option>`;
  }).join("");
  if (current && Array.from(select.options).some((o) => o.value === current)) {
    select.value = current;
  }
  updateWorkerDisplay();
}

function updateWorkerDisplay() {
  const select = document.getElementById("workerSelect");
  const nameEl = document.getElementById("workerName");
  const icon = document.getElementById("workerCheckIcon");
  const id = select.value;
  if (id) {
    const opt = select.options[select.selectedIndex];
    nameEl.textContent = opt ? opt.text : id;
    nameEl.classList.replace("text-slate-400", "text-slate-800");
    icon.classList.replace("text-slate-200", "text-green-400");
  } else {
    nameEl.textContent = "—";
    nameEl.classList.replace("text-slate-800", "text-slate-400");
    icon.classList.replace("text-green-400", "text-slate-200");
  }
}

async function loadBlocks() {
  const select = document.getElementById("blockSelect");
  try {
    const blocks = await LW.api("/api/blocks");
    localStorage.setItem("lw_cached_blocks", JSON.stringify(blocks));
    renderBlockOptions(blocks);
  } catch (e) {
    const cached = localStorage.getItem("lw_cached_blocks");
    if (cached) renderBlockOptions(JSON.parse(cached));
    else select.innerHTML = `<option value="">(offline - block list unavailable)</option>`;
  }
}

function renderBlockOptions(blocks) {
  const select = document.getElementById("blockSelect");
  const current = select.value;
  select.innerHTML = blocks.map((b) => `<option value="${b.id}">${b.name || b.id}</option>`).join("");
  if (current && Array.from(select.options).some((o) => o.value === current)) {
    select.value = current;
  }
}

function bindKeypad() {
  document.querySelectorAll(".keypad-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.dataset.k;
      if (k === "back") {
        weightBuffer = weightBuffer.slice(0, -1);
      } else if (k === "." && weightBuffer.includes(".")) {
        // ignore extra decimal point
      } else {
        weightBuffer += k;
      }
      document.getElementById("weightDisplay").textContent = weightBuffer || "0";
    });
  });
}

async function saveCrate() {
  const weight = parseFloat(weightBuffer);
  if (!weight || weight <= 0) { LW.toast("Enter a weight first"); return; }
  const workerId = document.getElementById("workerSelect").value;
  const blockId = document.getElementById("blockSelect").value;
  if (!workerId || !blockId) { LW.toast("Select a worker and block"); return; }

  const record = {
    uuid: LW.uuid(),
    timestamp: new Date().toISOString(),
    worker_id: workerId,
    block_id: blockId,
    weight_kg: weight,
    deduction_kg: 0,
    device_id: deviceConfig.id,
    team_id: deviceConfig.team_id,
    slip_number: getCurrentSlip(),
    notes: "",
    synced: false,
  };
  await IDB.add(record);
  weightBuffer = "";
  document.getElementById("weightDisplay").textContent = "0";
  document.getElementById("workerSelect").value = "";
  updateWorkerDisplay();
  LW.beepSaved();
  LW.toast("Crate saved");
  await renderLot();
  syncLoop();
}

async function renderLot() {
  const slip = getCurrentSlip();
  const crates = await IDB.getBySlip(slip);
  const crateCount = crates.length;
  const totalKg = crates.reduce((s, c) => s + c.weight_kg - (c.deduction_kg || 0), 0);
  document.getElementById("crateCount").textContent = `${crateCount} crates`;
  document.getElementById("totalKg").textContent = `${totalKg.toFixed(1)} kg`;

  const card = document.getElementById("lotCard");
  card.classList.remove("urgency-green", "urgency-yellow", "urgency-red");
  if (crateCount === 0) {
    document.getElementById("elapsed").textContent = "--:--";
    card.classList.add("urgency-green");
  } else {
    const first = crates.reduce((min, c) => (c.timestamp < min ? c.timestamp : min), crates[0].timestamp);
    const minutes = (Date.now() - new Date(first).getTime()) / 60000;
    const h = Math.floor(minutes / 60), m = Math.floor(minutes % 60);
    document.getElementById("elapsed").textContent = `${h}:${String(m).padStart(2, "0")}`;
    if (minutes >= systemSettings.yellow_to_red_minutes) card.classList.add("urgency-red");
    else if (minutes >= systemSettings.green_to_yellow_minutes) card.classList.add("urgency-yellow");
    else card.classList.add("urgency-green");
  }

  const recentCrates = [...crates].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 5);
  document.getElementById("recentList").innerHTML = recentCrates
    .map((r) => `<div class="flex justify-between border-b py-1"><span>${r.block_id}</span><span>${r.weight_kg} kg</span><span>${r.synced ? "✓ synced" : "⏳ pending"}</span></div>`)
    .join("") || `<div class="text-slate-400">No crates yet</div>`;
}

function updateOfflineSplitHint() {
  document.getElementById("offlineSplitHint").classList.toggle("hidden", navigator.onLine);
}

async function openDriverModal() {
  const slip = getCurrentSlip();
  const crates = await IDB.getBySlip(slip);
  const input = document.getElementById("cratesGoingInput");
  input.value = crates.length;
  input.max = crates.length;
  updateOfflineSplitHint();
  document.getElementById("driverModal").classList.remove("hidden");
  document.getElementById("driverModal").classList.add("flex");
}
function closeDriverModal() {
  document.getElementById("driverModal").classList.add("hidden");
  document.getElementById("driverModal").classList.remove("flex");
}

// Splits off a lot's most-recently-captured crates onto a fresh placeholder
// lot (server picks FIFO - oldest stay on the departing lot) so a truck can
// take only part of what's been picked, leaving the rest to combine with the
// next batch of picking into a later dispatch. Requires connectivity: the
// server is the only source of truth for exactly which crates currently
// share this lot, so unlike a normal dispatch this can't be queued offline.
async function splitAndAdopt(slip, keepCount) {
  const result = await LW.api(`/api/lots/by-slip/${encodeURIComponent(slip)}/split`, {
    method: "POST",
    body: { keep_count: keepCount },
  });
  await IDB.reassignSlip(result.moved_uuids, result.new_lot.slip_number);
  localStorage.setItem(CURRENT_SLIP_KEY, result.new_lot.slip_number);
  return result;
}

async function sendPickingSlip() {
  const driver = document.getElementById("driverInput").value.trim();
  if (!driver) { LW.toast("Enter the driver's name"); return; }

  const slip = getCurrentSlip();
  let crates = await IDB.getBySlip(slip);
  if (crates.length === 0) { LW.toast("No crates logged yet"); return; }

  const totalPending = crates.length;
  const cratesGoing = parseInt(document.getElementById("cratesGoingInput").value, 10) || totalPending;
  let didSplit = false;

  if (cratesGoing < totalPending) {
    if (!navigator.onLine) {
      updateOfflineSplitHint();
      LW.toast("Reconnect to send a partial load, or dispatch everything now.");
      return;
    }
    try {
      const splitResult = await splitAndAdopt(slip, totalPending - cratesGoing);
      const movedUuids = new Set(splitResult.moved_uuids);
      crates = crates.filter((c) => !movedUuids.has(c.uuid));
      didSplit = true;
    } catch (e) {
      LW.toast("Could not split the load - try again: " + (e.message || e));
      return;
    }
  }

  const first = crates.reduce((min, c) => (c.timestamp < min ? c.timestamp : min), crates[0].timestamp);
  const totalKg = crates.reduce((s, c) => s + c.weight_kg - (c.deduction_kg || 0), 0);
  const byBlock = {};
  crates.forEach((c) => { byBlock[c.block_id] = (byBlock[c.block_id] || 0) + c.weight_kg; });

  const lotPayload = {
    slip_number: slip,
    timestamp: first,
    device_id: deviceConfig.id,
    team_id: deviceConfig.team_id,
    driver,
    total_crates: crates.length,
    total_kg: totalKg,
    status: "in_transit",
  };

  try {
    await LW.api("/api/lots", { method: "POST", body: lotPayload });
  } catch (e) {
    const pending = getPendingLots();
    pending.push(lotPayload);
    setPendingLots(pending);
  }

  addDispatchedLot(slip, crates.length, totalKg);
  renderDispatchedLots();
  if (!didSplit) localStorage.removeItem(CURRENT_SLIP_KEY);
  closeDriverModal();
  document.getElementById("driverInput").value = "";
  showSlipSuccess(slip, crates.length, totalKg);
  await renderLot();
  syncLoop();
}

async function syncLoop() {
  const statusEl = document.getElementById("syncStatus");
  if (!navigator.onLine) {
    statusEl.textContent = "Offline";
    return;
  }
  try {
    // Flush pending lot dispatches first (order matters less since the
    // server resolves lots lazily by slip_number either way).
    const pendingLots = getPendingLots();
    const stillPending = [];
    for (const lot of pendingLots) {
      try {
        await LW.api("/api/lots", { method: "POST", body: lot });
      } catch (e) {
        stillPending.push(lot);
      }
    }
    setPendingLots(stillPending);

    const unsynced = await IDB.getUnsynced();
    if (unsynced.length > 0) {
      const records = unsynced.map(({ synced, ...rest }) => rest);
      await LW.api("/api/sync/harvest", { method: "POST", body: { records } });
      await IDB.markSynced(unsynced.map((r) => r.uuid));
    }
    statusEl.textContent = stillPending.length > 0 || unsynced.length > 0 ? "Syncing..." : "Online - synced";
  } catch (e) {
    statusEl.textContent = "Online - sync failed, retrying";
  }
}

let qrScanner = null;
function openScanner() {
  document.getElementById("scanModal").classList.remove("hidden");
  document.getElementById("scanModal").classList.add("flex");
  qrScanner = new Html5Qrcode("qrReader");
  qrScanner.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: 200 },
    (decodedText) => {
      const select = document.getElementById("workerSelect");
      const match = Array.from(select.options).find((o) => o.value === decodedText.trim());
      if (match) {
        select.value = decodedText.trim();
        updateWorkerDisplay();
        LW.beepScanned();
        LW.toast("Worker selected");
      } else {
        LW.toast("QR code doesn't match a known worker");
      }
      closeScanner();
    },
    () => {}
  ).catch(() => LW.toast("Camera unavailable"));
}
function closeScanner() {
  document.getElementById("scanModal").classList.add("hidden");
  document.getElementById("scanModal").classList.remove("flex");
  if (qrScanner) { qrScanner.stop().catch(() => {}); qrScanner = null; }
}

const DISPATCHED_KEY = "lw_dispatched_lots";

function addDispatchedLot(slip, crates, kg) {
  const all = JSON.parse(localStorage.getItem(DISPATCHED_KEY) || "[]");
  const today = new Date().toISOString().slice(0, 10);
  const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const recent = all.filter((d) => d.date >= cutoff);
  recent.push({ date: today, slip, crates, kg, time: new Date().toLocaleTimeString() });
  localStorage.setItem(DISPATCHED_KEY, JSON.stringify(recent));
}

function renderDispatchedLots() {
  const all = JSON.parse(localStorage.getItem(DISPATCHED_KEY) || "[]");
  const today = new Date().toISOString().slice(0, 10);
  const dispatched = all.filter((d) => d.date === today);
  const listEl = document.getElementById("dispatchedList");
  const summaryEl = document.getElementById("dispatchedSummary");
  if (!dispatched.length) {
    listEl.innerHTML = `<div class="text-slate-400 py-1">No lots dispatched yet today</div>`;
    summaryEl.classList.add("hidden");
    return;
  }
  listEl.innerHTML = dispatched.map((d) => `
    <div class="flex justify-between border-b py-1">
      <span class="font-mono text-slate-600">${d.slip.split("-").slice(-1)[0]}</span>
      <span>${d.crates} crates / ${Number(d.kg).toFixed(1)} kg</span>
      <span class="text-slate-400">${d.time}</span>
    </div>`).join("");
  const totalCrates = dispatched.reduce((s, d) => s + d.crates, 0);
  const totalKg = dispatched.reduce((s, d) => s + d.kg, 0);
  summaryEl.textContent = `${dispatched.length} lot${dispatched.length > 1 ? "s" : ""} — ${totalCrates} crates — ${totalKg.toFixed(1)} kg`;
  summaryEl.classList.remove("hidden");
}

function showSlipSuccess(slip, crates, kg) {
  const banner = document.getElementById("slipSuccessBanner");
  document.getElementById("slipSuccessDetail").textContent =
    `${crates} crates — ${kg.toFixed(1)} kg dispatched`;
  banner.classList.remove("hidden");
  setTimeout(() => banner.classList.add("hidden"), 5000);
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("service-worker.js").catch(() => {});
}

init();
