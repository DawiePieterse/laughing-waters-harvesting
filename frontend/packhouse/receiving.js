let deviceConfig = null;
let selectedLot = null;
let _lastRefreshed = null;
let _suppliersCache = [];

async function init() {
  const deviceId = LW.getDeviceId();
  if (!deviceId) { location.href = "../"; return; }
  try {
    deviceConfig = await LW.fetchDeviceConfigOfflineTolerant(deviceId);
  } catch (e) {
    location.href = "../";
    return;
  }
  document.getElementById("stationLabel").textContent = deviceConfig.station;

  document.getElementById("refreshBtn").addEventListener("click", refresh);
  document.getElementById("cancelReceiveBtn").addEventListener("click", closeModal);
  document.getElementById("confirmReceiveBtn").addEventListener("click", confirmReceipt);
  document.getElementById("externalLotBtn").addEventListener("click", openExternalLotModal);
  document.getElementById("cancelExternalLotBtn").addEventListener("click", closeExternalLotModal);
  document.getElementById("confirmExternalLotBtn").addEventListener("click", confirmExternalLot);

  await loadSuppliers();
  await refresh();
  setInterval(refresh, 30000);
  setInterval(updateLastUpdatedLabel, 10000);
}

async function loadSuppliers() {
  try {
    _suppliersCache = await LW.api("/api/suppliers");
  } catch (e) { /* keep last known list if offline */ }
}

async function refresh() {
  let lots = [];
  try {
    lots = await LW.api("/api/lots/in-transit");
  } catch (e) {
    LW.toast("Could not reach server");
    return;
  }
  const list = document.getElementById("lotsList");
  const empty = document.getElementById("emptyState");
  empty.classList.toggle("hidden", lots.length > 0);

  list.innerHTML = lots.map((lot) => `
    <button class="w-full text-left rounded-xl p-4 shadow urgency-${lot.urgency} lot-item" data-id="${lot.id}">
      <div class="flex justify-between items-center">
        <div>
          <div class="font-bold">${lot.slip_number}</div>
          <div class="text-sm text-slate-600">
            ${lot.supplier_name ? `<span class="font-semibold">${lot.supplier_name}</span> - ` : ""}
            Team ${lot.team_id || "?"} - Driver ${lot.driver || "?"}
          </div>
        </div>
        <div class="text-right">
          <div class="font-semibold">${lot.total_crates} crates / ${lot.total_kg.toFixed(1)} kg</div>
          <div class="text-xs text-slate-500">${lot.age_minutes} min ago</div>
        </div>
      </div>
    </button>
  `).join("");

  list.querySelectorAll(".lot-item").forEach((el) => {
    el.addEventListener("click", () => openReceiveModal(lots.find((l) => l.id == el.dataset.id)));
  });

  _lastRefreshed = Date.now();
  updateLastUpdatedLabel();
}

function updateLastUpdatedLabel() {
  const el = document.getElementById("lastUpdatedLabel");
  if (!el || !_lastRefreshed) return;
  const secs = Math.round((Date.now() - _lastRefreshed) / 1000);
  el.textContent = secs < 5 ? "just now" : `${secs}s ago`;
}

function openReceiveModal(lot) {
  selectedLot = lot;
  document.getElementById("modalSlip").textContent = lot.slip_number;
  document.getElementById("modalMeta").textContent =
    `${lot.supplier_name ? lot.supplier_name + " - " : ""}Team ${lot.team_id || "?"} - Driver ${lot.driver || "?"} - dispatched ${lot.age_minutes} min ago`;
  document.getElementById("expectedCrates").textContent = lot.total_crates;
  document.getElementById("actualCrates").value = lot.total_crates;
  document.getElementById("prePackCrates").value = 0;
  document.getElementById("notes").value = "";
  document.getElementById("receivedBy").value = LW.getLastReceivedBy();
  document.querySelectorAll("#conditionOptions input").forEach((cb) => { cb.checked = cb.value === "Good"; });

  document.getElementById("receiveModal").classList.remove("hidden");
  document.getElementById("receiveModal").classList.add("flex");
}

function closeModal() {
  document.getElementById("receiveModal").classList.add("hidden");
  document.getElementById("receiveModal").classList.remove("flex");
  selectedLot = null;
}

async function confirmReceipt() {
  if (!selectedLot) return;
  const actualCrates = parseInt(document.getElementById("actualCrates").value, 10) || 0;
  const condition = Array.from(document.querySelectorAll("#conditionOptions input:checked")).map((cb) => cb.value).join(", ") || "Good";
  const notes = document.getElementById("notes").value;
  const receivedBy = document.getElementById("receivedBy").value.trim();
  if (!receivedBy) { LW.toast("Enter who received this lot"); return; }
  LW.setLastReceivedBy(receivedBy);

  let prePackCrates = parseInt(document.getElementById("prePackCrates").value, 10) || 0;
  if (prePackCrates > actualCrates) prePackCrates = actualCrates;

  try {
    await LW.api("/api/receiving", {
      method: "POST",
      body: {
        lot_id: selectedLot.id,
        timestamp: new Date().toISOString(),
        expected_crates: selectedLot.total_crates,
        actual_crates: actualCrates,
        condition,
        notes,
        received_by: receivedBy,
      },
    });
  } catch (e) {
    LW.toast("Could not confirm - check connection and retry");
    return;
  }

  if (prePackCrates > 0) {
    try {
      await LW.api("/api/processing/prepack", {
        method: "POST",
        body: { lot_id: selectedLot.id, crates: prePackCrates, operator: receivedBy },
      });
      LW.toast("Receipt confirmed and pre-pack crates pulled");
    } catch (e) {
      LW.toast("Receipt confirmed, but pre-pack pull failed: " + (e.message || e));
    }
  } else {
    LW.toast("Receipt confirmed");
  }

  closeModal();
  await refresh();
}

function openExternalLotModal() {
  const select = document.getElementById("extSupplierSelect");
  const external = _suppliersCache.filter((s) => s.active && !s.is_own_farm);
  select.innerHTML = external.length
    ? external.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")
    : `<option value="">(no external suppliers set up yet)</option>`;
  document.getElementById("extCrates").value = "";
  document.getElementById("extKg").value = "";
  document.getElementById("extDriver").value = "";
  document.getElementById("extNotes").value = "";

  document.getElementById("externalLotModal").classList.remove("hidden");
  document.getElementById("externalLotModal").classList.add("flex");
}

function closeExternalLotModal() {
  document.getElementById("externalLotModal").classList.add("hidden");
  document.getElementById("externalLotModal").classList.remove("flex");
}

async function confirmExternalLot() {
  const supplierId = parseInt(document.getElementById("extSupplierSelect").value, 10);
  const crates = parseInt(document.getElementById("extCrates").value, 10) || 0;
  const kg = parseFloat(document.getElementById("extKg").value) || 0;
  const driver = document.getElementById("extDriver").value.trim();
  const notes = document.getElementById("extNotes").value;
  if (!supplierId) { LW.toast("Select a supplier"); return; }
  if (!crates || !kg) { LW.toast("Enter crates and kg"); return; }

  try {
    await LW.api("/api/lots/external", {
      method: "POST",
      body: { supplier_id: supplierId, driver, total_crates: crates, total_kg: kg, notes },
    });
    LW.toast("Delivery logged");
    closeExternalLotModal();
    await refresh();
  } catch (e) {
    LW.toast("Could not log delivery - check connection and retry");
  }
}

init();
