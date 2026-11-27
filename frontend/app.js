const API_BASE = "http://127.0.0.1:8000/api";
const NYAMIRA_CENTER = [-0.5633, 34.9358];

// Key Nyamira Town checkpoints & transit corridors
const CHECKPOINTS = [
  { name: "Nyamira Town Center / Hospital Jct", coords: [-0.5633, 34.9358] },
  { name: "Kisii–Nyamira Gate", coords: [-0.5715, 34.9220] },
  { name: "Sotik–Nyamira Gate", coords: [-0.5680, 34.9560] },
  { name: "Kebirigo–Ikonge Gate", coords: [-0.5850, 34.9460] },
];

const CORRIDOR_POLYLINES = [
  [[-0.5715, 34.9220], [-0.5633, 34.9358]], // Kisii–Nyamira
  [[-0.5633, 34.9358], [-0.5680, 34.9560]], // Nyamira–Sotik
  [[-0.5633, 34.9358], [-0.5850, 34.9460]], // Nyamira–Kebirigo/Ikonge
];

let map;
let vehicleLayerGroup;
let autoSync = true;
let pollTimer = null;

// --- Leaflet Initialization ---
function initMap() {
  map = L.map("nyamira-map").setView(NYAMIRA_CENTER, 14);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // Corridor route lines
  CORRIDOR_POLYLINES.forEach((lineCoords) => {
    L.polyline(lineCoords, {
      color: "#38bdf8",
      weight: 3,
      opacity: 0.75,
      dashArray: "6, 6",
    }).addTo(map);
  });

  // Checkpoint markers
  CHECKPOINTS.forEach((cp) => {
    L.circleMarker(cp.coords, {
      radius: 7,
      fillColor: "#38bdf8",
      color: "#0b1120",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.95,
    })
      .bindPopup(`<strong>Checkpoint:</strong> ${cp.name}`)
      .addTo(map);
  });

  vehicleLayerGroup = L.layerGroup().addTo(map);
}

// --- Data Fetching ---
async function refreshDashboard() {
  try {
    const [analyticsRes, activeRes, movementsRes] = await Promise.all([
      fetch(`${API_BASE}/analytics`),
      fetch(`${API_BASE}/active-vehicles`),
      fetch(buildMovementsUrl()),
    ]);

    if (!analyticsRes.ok || !activeRes.ok || !movementsRes.ok) {
      throw new Error("Backend API returned non-200 response");
    }

    const analytics = await analyticsRes.json();
    const activeVehicles = await activeRes.json();
    const movements = await movementsRes.json();

    renderKPIs(analytics.kpis);
    renderCorridorBars(analytics.corridor_stats);
    renderAlerts(analytics.alerts);
    renderActiveVehicles(activeVehicles);
    renderMovementsTable(movements);
    renderMapVehicles(movements);
  } catch (err) {
    console.error("Failed to sync Nyamira dashboard:", err);
  }
}

function buildMovementsUrl() {
  const params = new URLSearchParams({ limit: "120" });
  const plate = document.getElementById("filter-plate").value.trim();
  const corridor = document.getElementById("filter-corridor").value;
  const direction = document.getElementById("filter-direction").value;
  const category = document.getElementById("filter-category").value;

  if (plate) params.set("plate", plate);
  if (corridor) params.set("corridor", corridor);
  if (direction) params.set("direction", direction);
  if (category) params.set("category", category);

  return `${API_BASE}/movements?${params.toString()}`;
}

// --- Rendering Helpers ---
function renderKPIs(kpis) {
  document.getElementById("kpi-entries").textContent = kpis.entries_today;
  document.getElementById("kpi-exits").textContent = kpis.exits_today;
  document.getElementById("kpi-inside").textContent = kpis.currently_inside;
  document.getElementById("kpi-dwell").textContent = `${kpis.avg_dwell_minutes}m`;
  document.getElementById("kpi-alerts").textContent = kpis.active_alerts;
}

function renderCorridorBars(corridorStats) {
  const container = document.getElementById("corridor-bars");
  const maxTotal = Math.max(...corridorStats.map((c) => c.total), 1);

  container.innerHTML = corridorStats
    .map((c) => {
      const pct = Math.round((c.total / maxTotal) * 100);
      return `
        <div class="corridor-row">
          <div class="corridor-row-top">
            <strong>${c.corridor}</strong>
            <span>IN: ${c.entries} • OUT: ${c.exits} (${c.total})</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderAlerts(alerts) {
  const feed = document.getElementById("alert-feed");
  document.getElementById("alert-badge-count").textContent = `${alerts.length} Alerts`;

  if (!alerts.length) {
    feed.innerHTML = `<div class="empty-msg">No anomalies or overstays detected in selected window.</div>`;
    return;
  }

  feed.innerHTML = alerts
    .map(
      (a) => `
      <div class="alert-item">
        <div class="item-top">
          <span>${a.plate_number} (${a.direction})</span>
          <span class="accent-red">${formatTime(a.timestamp)}</span>
        </div>
        <div class="item-sub">${a.flag} • ${a.corridor}</div>
      </div>
    `
    )
    .join("");
}

function renderActiveVehicles(activeList) {
  const container = document.getElementById("active-vehicles-list");
  document.getElementById("active-count-pill").textContent = `${activeList.length} Active`;

  if (!activeList.length) {
    container.innerHTML = `<div class="empty-msg">No vehicles currently logged inside Nyamira town.</div>`;
    return;
  }

  container.innerHTML = activeList
    .map(
      (v) => `
      <div class="active-item">
        <div class="item-top">
          <span>${v.plate_number} • ${v.vehicle_category}</span>
          <span class="accent-amber">${Math.round(v.dwell_minutes || 0)}m inside</span>
        </div>
        <div class="item-sub">Entered via ${v.corridor} at ${formatTime(v.timestamp)}</div>
      </div>
    `
    )
    .join("");
}

function renderMovementsTable(movements) {
  const tbody = document.getElementById("movements-tbody");

  if (!movements.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-msg">No matching vehicle movements found.</td></tr>`;
    return;
  }

  tbody.innerHTML = movements
    .map((m) => {
      const dirBadge =
        m.direction === "ENTRY"
          ? `<span class="badge badge-entry">ENTRY (IN)</span>`
          : `<span class="badge badge-exit">EXIT (OUT)</span>`;

      const statusBadge = m.anomaly_flag
        ? `<span class="badge badge-alert">${m.anomaly_flag}</span>`
        : m.is_currently_inside
        ? `<span class="badge badge-normal">Inside Town</span>`
        : `<span class="badge badge-normal">Completed</span>`;

      const dwellText =
        m.dwell_minutes !== null && m.dwell_minutes !== undefined
          ? `${m.dwell_minutes} min`
          : "—";

      return `
        <tr>
          <td><strong>${m.plate_number}</strong></td>
          <td>${dirBadge}</td>
          <td>${m.corridor}</td>
          <td>${m.vehicle_category}<br><span class="item-sub">${m.trip_purpose}</span></td>
          <td>${formatDateTime(m.timestamp)}</td>
          <td>${dwellText}</td>
          <td>${m.source}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    })
    .join("");
}

function renderMapVehicles(movements) {
  vehicleLayerGroup.clearLayers();

  // Plot latest 25 movement events on Leaflet map
  movements.slice(0, 25).forEach((m) => {
    const isEntry = m.direction === "ENTRY";
    const marker = L.circleMarker([m.latitude, m.longitude], {
      radius: 6,
      fillColor: isEntry ? "#10b981" : "#f59e0b",
      color: "#0f172a",
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.9,
    });

    marker.bindPopup(`
      <strong>${m.plate_number}</strong> (${m.direction})<br/>
      ${m.vehicle_category} — ${m.corridor}<br/>
      <small>${formatDateTime(m.timestamp)}</small>
    `);

    marker.addTo(vehicleLayerGroup);
  });
}

// --- Formatting Helpers ---
function formatTime(isoStr) {
  const d = new Date(isoStr.endsWith("Z") ? isoStr : `${isoStr}Z`);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(isoStr) {
  const d = new Date(isoStr.endsWith("Z") ? isoStr : `${isoStr}Z`);
  return d.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// --- Modal & Actions ---
const modal = document.getElementById("log-modal");
const form = document.getElementById("movement-form");
const formError = document.getElementById("form-error");

function openModal() {
  formError.classList.add("hidden");
  formError.textContent = "";
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  form.reset();
}

document.getElementById("btn-open-modal").addEventListener("click", openModal);
document.getElementById("btn-close-modal").addEventListener("click", closeModal);
document.getElementById("btn-cancel-modal").addEventListener("click", closeModal);

document.getElementById("btn-anpr-scan").addEventListener("click", () => {
  const samplePlates = ["KDA 741N", "KDB 308C", "KDC 920M", "GK 514A", "KDD 118Z"];
  const picked = samplePlates[Math.floor(Math.random() * samplePlates.length)];
  document.getElementById("input-plate").value = picked;
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.classList.add("hidden");

  const payload = {
    plate_number: document.getElementById("input-plate").value.trim().toUpperCase(),
    direction: document.getElementById("input-direction").value,
    vehicle_category: document.getElementById("input-category").value,
    corridor: document.getElementById("input-corridor").value,
    trip_purpose: document.getElementById("input-purpose").value.trim(),
    source: "MANUAL",
  };

  try {
    const res = await fetch(`${API_BASE}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      const msg = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join("; ")
        : data.detail || "Validation error";
      throw new Error(msg);
    }

    closeModal();
    await refreshDashboard();
  } catch (err) {
    formError.textContent = err.message;
    formError.classList.remove("hidden");
  }
});

document.getElementById("btn-simulate").addEventListener("click", async () => {
  try {
    await fetch(`${API_BASE}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: 6 }),
    });
    await refreshDashboard();
  } catch (err) {
    console.error("Simulation error:", err);
  }
});

const autoSyncBtn = document.getElementById("btn-auto-refresh");
autoSyncBtn.addEventListener("click", () => {
  autoSync = !autoSync;
  autoSyncBtn.textContent = `Auto-Sync: ${autoSync ? "ON" : "OFF"}`;
  autoSyncBtn.classList.toggle("active", autoSync);
  configurePolling();
});

["filter-plate", "filter-corridor", "filter-direction", "filter-category"].forEach((id) => {
  document.getElementById(id).addEventListener("input", refreshDashboard);
  document.getElementById(id).addEventListener("change", refreshDashboard);
});

document.getElementById("btn-reset-filters").addEventListener("click", () => {
  document.getElementById("filter-plate").value = "";
  document.getElementById("filter-corridor").value = "";
  document.getElementById("filter-direction").value = "";
  document.getElementById("filter-category").value = "";
  refreshDashboard();
});

function configurePolling() {
  if (pollTimer) clearInterval(pollTimer);
  if (autoSync) {
    pollTimer = setInterval(refreshDashboard, 5000);
  }
}

// --- Boot ---
initMap();
refreshDashboard();
configurePolling();
