let watchWaypoints = [];
let latestHudSeq = 0;

function updateClock() {
  const now = new Date();
  document.getElementById("watch-clock").textContent = now.toLocaleTimeString("it-IT");
}
setInterval(updateClock, 1000);
updateClock();

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180.0;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeSectorPath(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M", cx, cy,
    "L", start.x.toFixed(1), start.y.toFixed(1),
    "A", r, r, 0, largeArcFlag, 0, end.x.toFixed(1), end.y.toFixed(1),
    "Z",
  ].join(" ");
}

function updateWatchCompass(cur, locationMeta, destWp) {
  const windDeg = Number(cur.wind?.direction_deg ?? 0);
  const swellDeg = Number(cur.waves?.swell_dir_deg ?? cur.waves?.direction_deg ?? 210);
  const cx = 90;
  const cy = 90;
  const rOuter = 62;

  const windFrom = polarToCartesian(cx, cy, rOuter - 4, windDeg);
  const windTo = polarToCartesian(cx, cy, 14, windDeg);
  const windLine = document.getElementById("watch-wind-line");
  if (windLine) {
    windLine.setAttribute("x1", windFrom.x.toFixed(1));
    windLine.setAttribute("y1", windFrom.y.toFixed(1));
    windLine.setAttribute("x2", windTo.x.toFixed(1));
    windLine.setAttribute("y2", windTo.y.toFixed(1));
    windLine.setAttribute("opacity", "1");
  }

  const waveFrom = polarToCartesian(cx, cy, rOuter - 8, swellDeg);
  const waveTo = polarToCartesian(cx, cy, 18, swellDeg);
  const waveLine = document.getElementById("watch-wave-line");
  if (waveLine) {
    waveLine.setAttribute("x1", waveFrom.x.toFixed(1));
    waveLine.setAttribute("y1", waveFrom.y.toFixed(1));
    waveLine.setAttribute("x2", waveTo.x.toFixed(1));
    waveLine.setAttribute("y2", waveTo.y.toFixed(1));
    waveLine.setAttribute("opacity", "1");
  }

  const bayCone = document.getElementById("watch-bay-cone");
  const bayAxis = locationMeta?.bay_open_deg ?? cur.coastal_physics?.bay_surge?.bay_open_axis_deg;
  if (bayCone && Number.isFinite(Number(bayAxis))) {
    const axis = Number(bayAxis);
    bayCone.setAttribute("d", describeSectorPath(cx, cy, rOuter, axis - 36, axis + 36));
  }

  const windMeta = document.getElementById("hud-compass-wind");
  if (windMeta) {
    windMeta.textContent = `Vento ${Math.round(windDeg)}° ${cur.wind?.cardinal || ""}`.trim();
  }
  const waveMeta = document.getElementById("hud-compass-wave");
  if (waveMeta) {
    const waveCard = cur.waves?.swell_cardinal || cur.waves?.direction_cardinal || "";
    waveMeta.textContent = `Onda ${Math.round(swellDeg)}° ${waveCard}`.trim();
  }
  const targetEl = document.getElementById("hud-compass-target");
  if (targetEl) {
    const rawName = destWp?.name || locationMeta?.name || "Rada";
    targetEl.textContent = rawName.split("(")[0].trim();
  }
}

async function initWatch() {
  try {
    const locRes = await fetch("/api/v1/locations");
    if (!locRes.ok) return;
    const locData = await locRes.json();
    watchWaypoints = locData.coastal_waypoints || [];

    const selO = document.getElementById("watch-origin");
    const selD = document.getElementById("watch-dest");
    selO.innerHTML = "";
    selD.innerHTML = "";
    watchWaypoints.forEach((wp) => {
      const o1 = document.createElement("option");
      o1.value = wp.id;
      o1.textContent = wp.name;
      const o2 = o1.cloneNode(true);
      selO.appendChild(o1);
      selD.appendChild(o2);
    });
    selO.value = "portofino";
    selD.value = "san_fruttuoso";

    let hudDebounceTimer = null;
    function scheduleHudRefresh() {
      clearTimeout(hudDebounceTimer);
      hudDebounceTimer = setTimeout(() => {
        refreshHud();
      }, 220);
    }

    selO.addEventListener("change", refreshHud);
    selD.addEventListener("change", refreshHud);
    const speedEl = document.getElementById("watch-speed");
    const durEl = document.getElementById("watch-duration");
    speedEl.addEventListener("change", refreshHud);
    durEl.addEventListener("change", refreshHud);
    speedEl.addEventListener("input", scheduleHudRefresh);
    durEl.addEventListener("input", scheduleHudRefresh);
    await refreshHud();
  } catch (err) {
    console.error("Errore inizializzazione HUD:", err);
  }
}

async function refreshHud() {
  const reqSeq = ++latestHudSeq;
  const origin = document.getElementById("watch-origin").value || "portofino";
  const dest = document.getElementById("watch-dest").value || "san_fruttuoso";
  const speedRaw = parseFloat(document.getElementById("watch-speed").value);
  const speed = Number.isFinite(speedRaw) ? Math.min(40, Math.max(1, speedRaw)) : 6.0;
  const durationRaw = parseInt(document.getElementById("watch-duration").value, 10);
  const duration = Number.isFinite(durationRaw) ? Math.min(600, Math.max(20, durationRaw)) : 90;

  const destWp = watchWaypoints.find((w) => w.id === dest);
  const marineUrl =
    destWp && Number.isFinite(destWp.lat) && Number.isFinite(destWp.lon)
      ? `/api/v1/marine?lat=${encodeURIComponent(destWp.lat)}&lon=${encodeURIComponent(destWp.lon)}`
      : `/api/v1/marine?location=SEA-BAIA-DI-SAN-FRUTTUOSO-DI-CAPODIMONTE-(AMP-ZONA-B)`;

  const [routeRes, marineRes] = await Promise.all([
    fetch(`/api/v1/route-eta?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}&cruise_knots=${speed}&duration_min=${duration}&stop_min=20`),
    fetch(marineUrl),
  ]);

  if (reqSeq !== latestHudSeq) return;

  if (routeRes.ok) {
    const plan = await routeRes.json();
    document.getElementById("hud-dist").textContent = `${plan.total_distance_nm} NM`;
    document.getElementById("hud-nav-time").textContent = `Nav ${plan.estimated_navigation_minutes} min`;
    const reqKtEl = document.getElementById("hud-req-kt");
    reqKtEl.textContent = `${plan.required_average_speed_knots} kt`;
    reqKtEl.style.color = plan.required_average_speed_knots > speed ? "var(--p-amber)" : "var(--p-wind)";
    document.getElementById("hud-turnaround").textContent = plan.schedule.latest_turnaround_time;
    document.getElementById("hud-route-label").textContent = `${plan.origin.name} ↔ ${plan.destination.name}`;
  }

  if (marineRes.ok) {
    const m = await marineRes.json();
    const cur = m.current_marine;
    document.getElementById("hud-wind").textContent = `${cur.wind.speed_knots} kt`;
    document.getElementById("hud-wind-sub").textContent = `${cur.wind.cardinal} · Raff. ${cur.wind.gust_knots} kt`;
    document.getElementById("hud-wave").textContent = `${cur.waves.significant_height_m}/${cur.waves.max_height_m} m`;
    document.getElementById("hud-wave-sub").textContent = `Tp ${cur.waves.peak_period_s} s (${cur.waves.direction_cardinal})`;
    document.getElementById("hud-risacca").textContent = `Risacca ${cur.coastal_physics.bay_surge.shore_breaker_height_m} m`;
    updateWatchCompass(cur, m.location, destWp);
  }
}

document.addEventListener("DOMContentLoaded", initWatch);
