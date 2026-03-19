/* ============================================================
   app.js — Shared utilities, tab switching, API helpers
   ============================================================ */

const API = "";  // empty = same origin (Flask serves both)

/* ── Tab Switching ─────────────────────────────────────────── */
function switchTab(id, el) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("on"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("on"));
  document.getElementById(id).classList.add("on");
  el.classList.add("on");

  // Lazy-init tabs
  if (id === "p-map" && !window._mapInited) {
    window._mapInited = true;
    initMap();
  }
  if (id === "routes-page" && !window._routesInited) {
    window._routesInited = true;
    loadRoutes();
  }
}

/* ── API Helpers ───────────────────────────────────────────── */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

function apiGet(path)        { return apiFetch(path); }
function apiPost(path, body) { return apiFetch(path, { method:"POST", body:JSON.stringify(body) }); }

/* ── Clock ─────────────────────────────────────────────────── */
function updateClock() {
  const n = new Date();
  const t = n.toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit", hour12:true });
  document.getElementById("clk").textContent = t;
}
setInterval(updateClock, 1000);
updateClock();

/* ── Traffic classifiers ───────────────────────────────────── */
function classifyVolume(v) {
  if (v < 400)  return { level:"LOW",       color:"#10d97e", cls:"bg-g", gstat:"gs-ok" };
  if (v < 900)  return { level:"MODERATE",  color:"#f5a623", cls:"bg-y", gstat:"gs-lo" };
  if (v < 1600) return { level:"HIGH",      color:"#ff4d4d", cls:"bg-r", gstat:"gs-me" };
  return              { level:"VERY HIGH", color:"#9b6dff", cls:"bg-p", gstat:"gs-hi" };
}

const LEVEL_DESC = {
  "LOW":       "Free flowing — no delays expected.",
  "MODERATE":  "Noticeable delays — allow extra 5 min.",
  "HIGH":      "Significant congestion — consider alternate route.",
  "VERY HIGH": "Near gridlock — rerouting strongly advised.",
};

/* ── Chart default options ─────────────────────────────────── */
function chartDefaults(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, ...(extra.plugins || {}) },
    scales: {
      x: { ticks:{ color:"#50596e", font:{size:10} }, grid:{ color:"#1d2535" } },
      y: { ticks:{ color:"#50596e", font:{size:10} }, grid:{ color:"#1d2535" } },
      ...(extra.scales || {}),
    },
    ...extra,
  };
}

/* ── Load status chip (updates RF R²) ──────────────────────── */
async function loadStatus() {
  try {
    const d = await apiGet("/api/status");
    const chip = document.getElementById("chip-r2");
    if (chip) chip.textContent = `RF R²=${d.r2}`;
  } catch(e) { /* silent */ }
}

/* ── On load ─────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  loadStatus();
  initDashboard();
  initPredictor();
});
