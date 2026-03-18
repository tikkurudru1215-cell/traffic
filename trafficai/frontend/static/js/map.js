/* ============================================================
   map.js — Leaflet live rerouting map + GPS simulation
   ============================================================ */

let _map, _routeLayers=[], _juncMarkers={};
let _gpsMarker=null, _gpsTail=null, _gpsRunning=false;
let _gpsStep=0, _gpsInt=null, _gpsLog=[];
let _selRoute=0;

// GPS simulation path (follows Route A, drifts off, returns)
const GPS_SIM = [
  { lat:23.2332, lon:77.4272, note:"Start — DB Mall Chowk" },
  { lat:23.2322, lon:77.4285, note:"Moving north on road" },
  { lat:23.2313, lon:77.4300, note:"On route — all clear" },
  { lat:23.2308, lon:77.4318, note:"Approaching Zone-I" },
  { lat:23.2295, lon:77.4300, note:"Slight westward drift" },
  { lat:23.2278, lon:77.4275, note:"WRONG TURN taken!" },
  { lat:23.2265, lon:77.4305, note:"Recalculating route..." },
  { lat:23.2278, lon:77.4340, note:"Merging back to route" },
  { lat:23.2290, lon:77.4362, note:"Back on planned route" },
  { lat:23.2299, lon:77.4382, note:"Arrived — MP Nagar" },
];

// Haversine distance (metres)
function haversineM(la1,lo1,la2,lo2){
  const R=6371000, p1=la1*Math.PI/180, p2=la2*Math.PI/180;
  const dp=(la2-la1)*Math.PI/180, dl=(lo2-lo1)*Math.PI/180;
  const a=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
}

/* ── Init Map ─────────────────────────────────────────────── */
function initMap() {
  _map = L.map("leaflet-map", {
    center: [23.235, 77.415],
    zoom: 13,
    zoomControl: true,
    attributionControl: false,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19, subdomains: "abcd",
  }).addTo(_map);

  L.control.attribution({ prefix:"© OpenStreetMap · CartoDB" }).addTo(_map);

  // Load initial routes
  refreshMap();

  // Control change listeners
  ["map-h","map-d","map-w"].forEach(id => {
    document.getElementById(id)?.addEventListener("change", refreshMap);
  });
}

/* ── Refresh all map layers ───────────────────────────────── */
async function refreshMap() {
  clearMapLayers();

  const hour    = +document.getElementById("map-h").value;
  const dow     = +document.getElementById("map-d").value;
  const weather =  document.getElementById("map-w").value;
  const month   = new Date().getMonth() + 1;

  // Update route meta label
  const dayN = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  document.getElementById("map-meta").textContent =
    dayN[dow] + " " + hour + ":00 · " + weather;

  try {
    const [routeData, juncData] = await Promise.all([
      apiPost("/api/routes",    { hour, day_of_week:dow, month, weather }),
      apiGet(`/api/junctions?hour=${hour}&day_of_week=${dow}&month=${month}&weather=${weather}`),
    ]);

    drawRoutes(routeData.routes);
    drawJunctions(juncData.junctions);
    renderMapSidebar(routeData.routes);
    updateOverlays(routeData.routes[0]);
  } catch(e) {
    console.error("Map refresh:", e);
  }
}

/* ── Draw route polylines ─────────────────────────────────── */
function drawRoutes(routes) {
  routes.forEach((r, rank) => {
    const isRec    = r.recommended;
    const isActive = rank === 0;
    const col   = isRec ? "#10d97e" : isActive ? "#4d9fff" : "#3a4860";
    const wt    = isActive ? 7 : 4;
    const op    = isActive ? 1.0 : 0.5;
    const dash  = isActive ? null : "8,5";

    const pl = L.polyline(r.waypoints, {
      color:col, weight:wt, opacity:op, dashArray:dash,
      lineCap:"round", lineJoin:"round",
    }).addTo(_map);
    pl.on("click", () => { _selRoute = rank; refreshMap(); });
    _routeLayers.push(pl);

    // Directional arrows on active route
    if (isActive || isRec) {
      r.waypoints.forEach((pt, i) => {
        if (i === 0 || i === r.waypoints.length-1) return;
        const prev = r.waypoints[i-1], next = r.waypoints[i+1];
        const angle = Math.atan2(next[1]-prev[1], next[0]-prev[0]) * 180/Math.PI;
        const icon = L.divIcon({
          className:"",
          html:`<div style="color:${col};font-size:11px;transform:rotate(${angle}deg);opacity:.85;line-height:1">▶</div>`,
          iconSize:[11,11], iconAnchor:[6,6],
        });
        const m = L.marker(pt, { icon, interactive:false, zIndexOffset:100 }).addTo(_map);
        _routeLayers.push(m);
      });
    }
  });

  // Origin & destination pins
  addPin([23.2332,77.4272], "#10d97e", "S", "Origin — DB Mall Chowk");
  addPin([23.2299,77.4382], "#ff4d4d", "E", "Destination — MP Nagar");
}

/* ── Draw junction bubbles ────────────────────────────────── */
function drawJunctions(junctions) {
  junctions.forEach(j => {
    const r    = Math.max(13, Math.min(25, j.volume/70));
    const icon = L.divIcon({
      className:"",
      html:`<div style="
        width:${r*2}px;height:${r*2}px;border-radius:50%;
        background:${j.color}18;border:2px solid ${j.color};
        display:flex;align-items:center;justify-content:center;
        font-family:'Space Mono',monospace;font-size:9px;color:${j.color};font-weight:700;
        box-shadow:0 0 14px ${j.color}33;cursor:pointer;transition:transform .2s"
        onmouseenter="this.style.transform='scale(1.15)'"
        onmouseleave="this.style.transform='scale(1)'"
      >${Math.round(j.volume/100)/10}k</div>`,
      iconSize:[r*2,r*2], iconAnchor:[r,r],
    });
    const mk = L.marker([j.lat, j.lon], { icon }).addTo(_map);
    mk.bindPopup(`
      <div class="jp-title">${j.name}</div>
      <div class="jp-row"><span>Predicted Volume</span><span class="jp-val" style="color:${j.color}">${j.volume.toLocaleString()} veh/hr</span></div>
      <div class="jp-row"><span>Traffic Level</span><span class="jp-val" style="color:${j.color}">${j.level}</span></div>
      <div class="jp-row"><span>Junction ID</span><span class="jp-val">${j.id}</span></div>
      <div class="jp-row"><span>Coordinates</span><span class="jp-val">${j.lat}°N, ${j.lon}°E</span></div>
    `, { className:"junc-popup", maxWidth:260 });
    _juncMarkers[j.id] = mk;
    _routeLayers.push(mk);
  });
}

function addPin(latlng, color, label, title) {
  const icon = L.divIcon({
    className:"",
    html:`<div title="${title}" style="
      width:28px;height:28px;border-radius:50% 50% 50% 0;
      transform:rotate(-45deg);background:${color};
      border:3px solid #fff;box-shadow:0 3px 12px rgba(0,0,0,.6);cursor:pointer">
    </div>`,
    iconSize:[28,28], iconAnchor:[14,28],
  });
  const m = L.marker(latlng, { icon, zIndexOffset:500 }).addTo(_map);
  m.bindTooltip(title, { permanent:false, direction:"top", offset:[0,-30], className:"junc-popup" });
  _routeLayers.push(m);
}

function clearMapLayers() {
  _routeLayers.forEach(l => l.remove());
  _routeLayers = [];
  _juncMarkers = {};
}

/* ── Sidebar route cards (inside map page) ────────────────── */
function renderMapSidebar(routes) {
  const container = document.getElementById("map-route-cards");
  container.innerHTML = routes.map((r, rank) => {
    const c   = classifyVolume(r.avg_volume);
    const pct = Math.min(100, r.avg_volume/2000*100);
    const col = r.recommended ? "#10d97e" : rank===0 ? "#4d9fff" : "#3a4860";
    return `<div class="route-card ${r.recommended?"best":""} ${rank===0?"active":""}"
                 onclick="selectMapRoute(${rank})">
      <div style="position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:3px 0 0 3px;background:${col}"></div>
      <div class="rc-top">
        <div>
          <div class="rc-name">${r.name}</div>
          <div class="rc-meta">${r.km}km · score ${r.score}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;margin-left:10px">
          <div class="rc-time" style="color:${r.color}">${r.est_time}</div>
          <div class="rc-tu">min</div>
        </div>
      </div>
      <div class="rc-bar"><div class="rc-fill" style="width:${pct}%;background:${r.color}"></div></div>
      <div class="rc-bot">
        <span class="badge ${c.cls}">${r.avg_volume.toLocaleString()} veh/hr · ${r.level}</span>
        ${r.recommended ? '<span class="rec-tag">⭐ RECOMMENDED</span>' : ""}
      </div>
    </div>`;
  }).join("");
}

function selectMapRoute(rank) {
  _selRoute = rank;
  refreshMap();
}

function updateOverlays(best) {
  document.getElementById("ov-route").textContent = "Route " + best.id;
  document.getElementById("ov-vol").textContent   = best.avg_volume.toLocaleString();
  document.getElementById("ov-vol").style.color   = best.color;
  document.getElementById("ov-time").textContent  = best.est_time + " min";
}

/* ── GPS Simulation ───────────────────────────────────────── */
function toggleGPS() {
  _gpsRunning ? stopGPS() : startGPS();
}

function startGPS() {
  _gpsRunning = true; _gpsStep = 0; _gpsLog = [];
  const btn = document.getElementById("gps-btn");
  btn.textContent = "Stop Navigation";
  btn.classList.add("running");
  document.getElementById("alert-bar").classList.add("show");
  document.getElementById("gps-log-scroll").innerHTML = "";

  if (_gpsTail)   { _gpsTail.remove();   _gpsTail   = null; }
  const tracePts = [];
  // Use Route A waypoints for deviation check
  const routeWpts = [
    [23.2332,77.4272],[23.2322,77.4285],[23.2313,77.4300],
    [23.2307,77.4318],[23.2302,77.4340],[23.2299,77.4365],[23.2299,77.4382],
  ];

  _gpsInt = setInterval(async () => {
    if (_gpsStep >= GPS_SIM.length) { stopGPS(); return; }
    const pt = GPS_SIM[_gpsStep];
    tracePts.push([pt.lat, pt.lon]);

    // Ask backend for deviation check
    try {
      const dev = await apiPost("/api/deviation", { lat:pt.lat, lon:pt.lon, route_id:"A" });
      updateGPSUI(pt, dev, tracePts);
    } catch(e) {
      // Fallback: compute locally
      const dist = Math.round(Math.min(...routeWpts.map(w => haversineM(pt.lat,pt.lon,w[0],w[1]))));
      const level = dist<=50?"ON_ROUTE":dist<=150?"LOW":dist<=300?"MEDIUM":"HIGH";
      const color = dist<=50?"#10d97e":dist<=150?"#f5a623":dist<=300?"#f97316":"#ff4d4d";
      const msg   = dist<=50?"On route — all clear":dist<=150?"Slight deviation":dist<=300?"Recalculating...":"Off route! Rerouting";
      updateGPSUI(pt, { distance_m:dist, level, message:msg, color, reroute:dist>300 }, tracePts);
    }
    _gpsStep++;
  }, 1900);
}

function updateGPSUI(pt, dev, tracePts) {
  // Move GPS marker
  if (_gpsMarker) _gpsMarker.remove();
  const gpsIcon = L.divIcon({
    className:"",
    html:`<div style="position:relative;width:22px;height:22px">
      <div style="position:absolute;inset:0;border-radius:50%;background:#4d9fff33;animation:pls 1.5s infinite"></div>
      <div style="position:absolute;inset:3px;border-radius:50%;background:#4d9fff;border:2px solid #fff;box-shadow:0 0 12px #4d9fff88"></div>
    </div>`,
    iconSize:[22,22], iconAnchor:[11,11],
  });
  _gpsMarker = L.marker([pt.lat, pt.lon], { icon:gpsIcon, zIndexOffset:1000 }).addTo(_map);
  _map.panTo([pt.lat, pt.lon], { animate:true, duration:.6 });

  // Update tail
  if (_gpsTail) _gpsTail.remove();
  _gpsTail = L.polyline(tracePts, {
    color: dev.color, weight:4, dashArray:"6,4", opacity:.8, lineCap:"round",
  }).addTo(_map);

  // Alert bar
  const bar = document.getElementById("alert-bar");
  const lvlCls = { ON_ROUTE:"ok", LOW:"lo", MEDIUM:"me", HIGH:"hi" }[dev.level] || "ok";
  bar.className = "alert-bar show " + lvlCls;
  document.getElementById("alert-txt").textContent  = dev.message;
  document.getElementById("alert-dist").textContent = dev.distance_m + "m from route";

  // Log entry
  const lc = dev.color;
  const badge = { ON_ROUTE:"ON ROUTE", LOW:"LOW ALERT", MEDIUM:"REROUTING", HIGH:"OFF ROUTE" }[dev.level];
  _gpsLog.unshift(
    `<div class="gl">
      <span class="gl-dot" style="background:${lc}"></span>
      <span class="gl-desc">${pt.note}</span>
      <span class="gl-d">${dev.distance_m}m</span>
      <span class="gl-s" style="background:${lc}1a;color:${lc}">${badge}</span>
    </div>`
  );
  document.getElementById("gps-log-scroll").innerHTML = _gpsLog.slice(0, 8).join("");
}

function stopGPS() {
  clearInterval(_gpsInt);
  _gpsRunning = false; _gpsStep = 0;
  const btn = document.getElementById("gps-btn");
  btn.textContent = "Start GPS Navigation";
  btn.classList.remove("running");
  const bar = document.getElementById("alert-bar");
  bar.className = "alert-bar ok show";
  document.getElementById("alert-txt").textContent  = "Navigation ended";
  document.getElementById("alert-dist").textContent = "";
  if (_gpsMarker) { _gpsMarker.remove(); _gpsMarker = null; }
  if (_gpsTail)   { _gpsTail.remove();   _gpsTail   = null; }
}
