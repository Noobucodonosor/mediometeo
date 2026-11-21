/* ==========================================================================
   MedioMeteo Genova v4.0 — Full-Screen Map-First Application (ADR-0013)
   - Mappa Windy-style 100dvh, CartoDB Voyager (Chiaro) / Dark Matter + OpenSeaMap
   - 1 solo layer attivo alla volta sul rail destro (wind | radar | waves | stations)
   - Rilevamento automatico Terra/Mare sul punto cliccato o cercato
   - Bottom Sheet progressivo a 3 livelli (peek | medium | expanded)
   - AI contestuale POST /api/v1/ask grounded sui dati live
   ========================================================================== */

import { escapeHtml } from "/static/js/security.js?v=4.0";
import {
  THEME_STORAGE_KEY,
  loadFavorites,
  saveFavorites,
  state,
} from "/static/js/state.js?v=4.0";
import {
  askPointQuestion,
  fetchCoastalRoute,
  fetchLocationsCatalog,
  fetchOmirlChart,
  fetchWeatherAndBulletin,
} from "/static/js/api.js?v=4.0";
import { renderCharts } from "/static/js/charts.js?v=4.0";

const SEA_BOUNDS_LAT = 44.36;

function isPointLikelySea(lat, lon, locObj = null) {
  if (locObj && locObj.category) return locObj.category === "sea";
  return lat < SEA_BOUNDS_LAT && lon > 8.65 && lon < 9.45;
}

function applyTheme(theme) {
  state.theme = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", state.theme);
  const lbl = document.getElementById("theme-label");
  if (lbl) lbl.textContent = state.theme === "dark" ? "Chiaro" : "Scuro";
  try {
    localStorage.setItem(THEME_STORAGE_KEY, state.theme);
  } catch (_) {}

  if (state.map && state.baseTileLayer) {
    state.map.removeLayer(state.baseTileLayer);
    state.baseTileLayer = createBaseTileLayer().addTo(state.map);
    state.baseTileLayer.bringToBack();
    if (state.vectorLandLayer) state.vectorLandLayer.setStyle(vectorStyle());
  }
  if (state.sheetState === "expanded" && state.weatherPkg) {
    renderCharts(state.weatherPkg.forecast.hourly_48h, state);
  }
}

function vectorStyle() {
  const isDark = state.theme === "dark";
  return {
    color: isDark ? "rgba(56, 189, 248, 0.35)" : "rgba(2, 132, 199, 0.35)",
    weight: 1.5,
    fillColor: isDark ? "#141c2b" : "#e2e8f0",
    fillOpacity: 0.72,
  };
}

function createBaseTileLayer() {
  return L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 19,
  });
}

function initLeafletMap() {
  if (typeof L === "undefined") return;

  state.map = L.map("genova-map", {
    center: [44.38, 9.02],
    zoom: 10,
    zoomControl: false,
  });

  // Base vettoriale costa ligure di fallback (sempre leggibile anche offline/sandboxed)
  const liguriaLandPoly = [
    [45.10, 7.40], [45.10, 10.30], [44.05, 10.30],
    [44.05, 9.98], [44.10, 9.83], [44.14, 9.65], [44.23, 9.45],
    [44.27, 9.39], [44.31, 9.33], [44.345, 9.234], [44.31, 9.215],
    [44.298, 9.218], [44.315, 9.175], [44.322, 9.145], [44.349, 9.151],
    [44.362, 9.120], [44.380, 9.035], [44.388, 8.973], [44.398, 8.926],
    [44.418, 8.775], [44.399, 8.685], [44.34, 8.56], [44.30, 8.48],
    [44.18, 8.35], [44.05, 8.22], [43.88, 8.02], [43.81, 7.77],
    [43.78, 7.60], [43.78, 7.40],
  ];
  state.vectorLandLayer = L.polygon(liguriaLandPoly, {
    ...vectorStyle(),
    interactive: false,
  }).addTo(state.map);

  // Torrenti principali + 6 nomi costieri puliti
  [
    [[44.50, 8.91], [44.45, 8.895], [44.415, 8.885]],
    [[44.48, 9.01], [44.44, 8.97], [44.398, 8.947]],
    [[44.56, 8.66], [44.51, 8.68], [44.46, 8.66]],
    [[44.42, 9.41], [44.36, 9.35], [44.31, 9.33]],
  ].forEach((coords) => {
    L.polyline(coords, {
      color: "rgba(2, 132, 199, 0.30)",
      weight: 1.3,
      dashArray: "3, 4",
      interactive: false,
    }).addTo(state.map);
  });

  state.baseTileLayer = createBaseTileLayer().addTo(state.map);
  state.seamarkLayer = L.tileLayer("https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenSeaMap",
    maxZoom: 18,
    opacity: 0.85,
  }).addTo(state.map);

  [
    { name: "Voltri", lat: 44.432, lon: 8.75 },
    { name: "Genova", lat: 44.422, lon: 8.934 },
    { name: "Camogli", lat: 44.356, lon: 9.155 },
    { name: "Portofino", lat: 44.303, lon: 9.211 },
    { name: "Chiavari", lat: 44.322, lon: 9.325 },
    { name: "Sestri Lev.", lat: 44.274, lon: 9.395 },
  ].forEach((hub) => {
    L.marker([hub.lat, hub.lon], {
      interactive: false,
      icon: L.divIcon({
        html: `<span class="map-hub-label">${escapeHtml(hub.name)}</span>`,
        className: "",
        iconSize: [70, 14],
        iconAnchor: [35, 7],
      }),
    }).addTo(state.map);
  });

  state.overlayGroup = L.layerGroup().addTo(state.map);
  state.routeGroup = L.layerGroup().addTo(state.map);

  state.map.on("zoomend", () => renderActiveMapLayer());
  state.map.on("click", async (ev) => {
    closeSearchDropdown();
    const lat = Number(ev.latlng.lat.toFixed(4));
    const lon = Number(ev.latlng.lng.toFixed(4));
    state.customCoords = { lat, lon };
    state.mode = isPointLikelySea(lat, lon) ? "sea" : "land";
    placeCustomPin(lat, lon);
    await refreshAllData(false);
    setSheetState("medium");
  });
}

function placeCustomPin(lat, lon) {
  if (!state.map) return;
  if (state.customMarker) state.map.removeLayer(state.customMarker);
  state.customMarker = L.circleMarker([lat, lon], {
    radius: 7,
    color: "#ffffff",
    weight: 2,
    fillColor: "#0284c7",
    fillOpacity: 0.95,
  }).addTo(state.map);
}

function shortRadaName(rawName) {
  let s = String(rawName || "").split("(")[0].trim();
  const prefixes = [
    "Baia e Porto di ",
    "Porto e Rada di ",
    "Rada e Porto ",
    "Punta del Capo / ",
    "Scogliera di ",
    "Baia di ",
    "Porto di ",
    "Rada di ",
    "Marina di ",
    "Cala di ",
  ];
  for (const p of prefixes) {
    if (s.startsWith(p)) {
      s = s.slice(p.length);
      break;
    }
  }
  return s.length > 16 ? s.slice(0, 15) + "…" : s;
}

function renderActiveMapLayer() {
  if (!state.map || !state.overlayGroup) return;
  state.overlayGroup.clearLayers();
  const placedPts = [];

  const canPlace = (lat, lon, minDx = 68, minDy = 28) => {
    const pt = state.map.latLngToContainerPoint([lat, lon]);
    for (const p of placedPts) {
      if (Math.abs(pt.x - p.x) < minDx && Math.abs(pt.y - p.y) < minDy) return false;
    }
    placedPts.push(pt);
    return true;
  };

  const radarBar = document.getElementById("radar-bar");
  if (radarBar) radarBar.hidden = state.activeLayer !== "radar";

  if (state.activeLayer === "radar") {
    updateRadarLayer();
  } else if (state.radarLayer) {
    state.map.removeLayer(state.radarLayer);
    state.radarLayer = null;
  }

  if (!state.weatherPkg) return;
  const obs = state.weatherPkg.observations_live || {};
  const zoom = state.map.getZoom() || 10;

  if (state.activeLayer === "wind") {
    const stations = (obs.all_weather_stations || obs.nearest_weather_stations || [])
      .filter((s) => s.has_live_wind !== false && s.sensor !== "Termo/Pluvio")
      .sort((a, b) => (a.display_tier ?? 3) - (b.display_tier ?? 3));
    stations.forEach((st) => {
      if (zoom < 12 && st.display_tier > 1 && st.severity === "normal") return;
      if (st.severity === "normal" && !canPlace(st.lat, st.lon)) return;
      const rot = ((st.wind_dir_deg ?? 0) + 90) % 360;
      const cls = st.severity === "alert" ? "is-alert" : st.severity === "watch" ? "is-watch" : "";
      const arrow = `<svg width="11" height="11" viewBox="0 0 12 12" style="transform:rotate(${rot}deg)" aria-hidden="true"><path d="M1.5 6h8M6.5 2.5L10.5 6l-4 3.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      addPointMarker(st.lat, st.lon, `${arrow}<span>${escapeHtml(st.wind_knots)} kt</span>`, cls, `${st.name} • ${st.wind_knots} kt`, () => selectCoordsOnMap(st.lat, st.lon, "land"));
    });
  } else if (state.activeLayer === "waves") {
    const buoy = obs.marine_wave_buoy || obs.buoys_live?.[0];
    if (buoy && canPlace(buoy.lat ?? 43.918, buoy.lon ?? 8.185)) {
      addPointMarker(
        buoy.lat ?? 43.918,
        buoy.lon ?? 8.185,
        `BOA ${escapeHtml(buoy.wave_hs_m)}m`,
        "",
        `${buoy.name} • Hs ${buoy.wave_hs_m} m`,
        () => selectCoordsOnMap(buoy.lat ?? 43.918, buoy.lon ?? 8.185, "sea")
      );
    }
    if (state.ampZones.length) {
      state.ampZones.forEach((z) => {
        L.polygon(z.coords, {
          color: z.color,
          weight: 1.5,
          fillColor: z.color,
          fillOpacity: 0.16,
        })
          .bindTooltip(`<strong>${escapeHtml(z.name)}</strong><br>${escapeHtml(z.rules)}`)
          .addTo(state.overlayGroup);
      });
    }
    state.locations
      .filter((l) => l.loc_type === "rada_porto")
      .forEach((rada) => {
        if (!canPlace(rada.lat, rada.lon, 84, 26)) return;
        addPointMarker(rada.lat, rada.lon, escapeHtml(shortRadaName(rada.name)), "", `${rada.name}`, () => selectLocationById(rada.id));
      });
  } else if (state.activeLayer === "stations") {
    const allSt = [...(obs.all_weather_stations || obs.nearest_weather_stations || [])].sort(
      (a, b) => (a.display_tier ?? 3) - (b.display_tier ?? 3)
    );
    allSt.forEach((st) => {
      if (zoom < 11 && st.display_tier > 1 && st.severity === "normal") return;
      if (st.severity === "normal" && !canPlace(st.lat, st.lon, 74, 26)) return;
      const cls = st.severity === "alert" ? "is-alert" : st.severity === "watch" ? "is-watch" : "";
      addPointMarker(st.lat, st.lon, `${escapeHtml(st.temp_c)}° · ${escapeHtml(st.precip_1h_mm)}mm`, cls, `${st.name} (${st.code})`, () => selectCoordsOnMap(st.lat, st.lon, "land"));
    });
    const hydros = obs.all_river_hydrometers || obs.nearest_river_hydrometers || [];
    hydros.forEach((hy) => {
      if (zoom < 11 && hy.display_tier > 1 && hy.status_level === "green") return;
      if (hy.status_level === "green" && !canPlace(hy.lat, hy.lon, 74, 26)) return;
      const cls = hy.status_level === "red" ? "is-alert" : hy.status_level === "orange" ? "is-watch" : "";
      addPointMarker(hy.lat, hy.lon, `IDRO ${escapeHtml(hy.level_m)}m`, cls, `${hy.name} (${hy.river})`, () => selectCoordsOnMap(hy.lat, hy.lon, "land"));
    });
  }
}

function addPointMarker(lat, lon, htmlInner, extraClass, tooltipText, onClick) {
  const icon = L.divIcon({
    html: `<div class="windy-marker ${extraClass}">${htmlInner}</div>`,
    className: "",
    iconSize: null,
  });
  const m = L.marker([lat, lon], { icon }).addTo(state.overlayGroup);
  if (tooltipText) m.bindTooltip(escapeHtml(tooltipText));
  if (onClick) {
    m.on("click", (ev) => {
      L.DomEvent.stopPropagation(ev);
      onClick();
    });
  }
}

async function selectCoordsOnMap(lat, lon, modeHint = null) {
  state.customCoords = { lat, lon };
  state.mode = modeHint || (isPointLikelySea(lat, lon) ? "sea" : "land");
  placeCustomPin(lat, lon);
  await refreshAllData(false);
  setSheetState("medium");
}

function updateRadarLayer() {
  if (!state.map || !state.weatherPkg) return;
  const radar = state.weatherPkg.nowcast?.radar || {};
  const frames = radar.frames || [];
  const slider = document.getElementById("radar-frame-slider");
  const labelEl = document.getElementById("radar-time-label");

  if (slider && frames.length > 0) {
    slider.max = String(frames.length - 1);
    if (state.radarFrameIndex >= frames.length) state.radarFrameIndex = frames.length - 1;
    slider.value = String(state.radarFrameIndex);
  }
  if (state.radarLayer) {
    state.map.removeLayer(state.radarLayer);
    state.radarLayer = null;
  }
  if (state.activeLayer !== "radar") return;

  const activeFrame = frames[state.radarFrameIndex] || frames[frames.length - 1];
  const tileUrl = activeFrame?.tile_url || activeFrame?.tile_url_template || radar.latest_tile_url;
  if (tileUrl) {
    state.radarLayer = L.tileLayer(tileUrl, { opacity: 0.65, zIndex: 450, maxNativeZoom: 7, maxZoom: 18 }).addTo(state.map);
    if (labelEl) labelEl.textContent = activeFrame ? `${activeFrame.time_label}` : "Live";
  } else if (labelEl) {
    labelEl.textContent = "Nessun eco";
  }
}

function toggleRadarAnimation() {
  const btn = document.getElementById("btn-radar-play");
  const frames = state.weatherPkg?.nowcast?.radar?.frames || [];
  if (!frames.length) return;
  state.radarPlaying = !state.radarPlaying;
  if (state.radarPlaying) {
    if (btn) btn.textContent = "Pausa";
    state.radarTimer = setInterval(() => {
      state.radarFrameIndex = (state.radarFrameIndex + 1) % frames.length;
      updateRadarLayer();
    }, 850);
  } else {
    if (btn) btn.textContent = "Play";
    if (state.radarTimer) {
      clearInterval(state.radarTimer);
      state.radarTimer = null;
    }
  }
}

function setSheetState(nextState) {
  state.sheetState = nextState;
  const sheet = document.getElementById("bottom-sheet");
  const btn = document.getElementById("btn-sheet-expand");
  const scroller = document.querySelector(".sheet-scroll");
  if (scroller) scroller.scrollTop = 0;
  if (sheet) sheet.setAttribute("data-state", nextState);
  document.body.classList.toggle("sheet-is-expanded", nextState === "expanded");
  if (btn) {
    btn.textContent =
      nextState === "expanded" ? "Riduci" : nextState === "medium" ? "Dettagli" : "Apri";
  }
  if (nextState === "expanded" && state.weatherPkg) {
    setTimeout(() => renderCharts(state.weatherPkg.forecast.hourly_48h, state), 50);
  }
}

function cycleSheetState() {
  if (state.sheetState === "peek") setSheetState("medium");
  else if (state.sheetState === "medium") setSheetState("expanded");
  else setSheetState("peek");
}

function closeSearchDropdown() {
  const panel = document.getElementById("loc-picker-panel");
  if (panel) panel.hidden = true;
}

function renderFavoritesBar() {
  const bar = document.getElementById("fav-chips-bar");
  const toggleBtn = document.getElementById("btn-toggle-fav");
  const favs = loadFavorites();

  if (toggleBtn) {
    toggleBtn.setAttribute("aria-pressed", !state.customCoords && favs.includes(state.selectedLocationId) ? "true" : "false");
  }
  if (!bar) return;

  bar.innerHTML = favs
    .map((id) => state.locations.find((l) => l.id === id))
    .filter(Boolean)
    .map((loc) => {
      const act = !state.customCoords && loc.id === state.selectedLocationId ? " active" : "";
      return `<button type="button" class="fav-chip${act}" data-fav-id="${escapeHtml(loc.id)}">${escapeHtml(loc.name)}</button>`;
    })
    .join("");
}

function renderLocationDropdown(typeFilter = "", query = "") {
  const listEl = document.getElementById("loc-picker-list");
  if (!listEl) return;
  const q = query.trim().toLowerCase();
  const filtered = state.locations.filter((loc) => {
    if (typeFilter && loc.loc_type !== typeFilter) return false;
    if (q && !loc.name.toLowerCase().includes(q) && !loc.valley_or_sector.toLowerCase().includes(q)) {
      return false;
    }
    return true;
  });

  listEl.innerHTML = filtered
    .slice(0, 45)
    .map(
      (loc) => `
      <button type="button" class="loc-item-btn" data-loc-id="${escapeHtml(loc.id)}">
        <span>${escapeHtml(loc.name)}</span>
        <span class="loc-item-sub">${escapeHtml(loc.valley_or_sector)}</span>
      </button>`
    )
    .join("");
}

async function selectLocationById(locId) {
  state.selectedLocationId = locId;
  state.customCoords = null;
  if (state.customMarker && state.map) {
    state.map.removeLayer(state.customMarker);
    state.customMarker = null;
  }
  const found = state.locations.find((l) => l.id === locId);
  if (found) {
    state.mode = found.category === "sea" ? "sea" : "land";
    const inp = document.getElementById("loc-search-input");
    if (inp) inp.value = found.name;
    if (state.map) state.map.flyTo([found.lat, found.lon], 12, { duration: 0.6 });
  }
  closeSearchDropdown();
  await refreshAllData(false);
}

async function refreshAllData(forceRefresh = false) {
  try {
    const { forecastRes, aiRes } = await fetchWeatherAndBulletin(state, forceRefresh);
    if (!forecastRes.ok) return;
    state.weatherPkg = await forecastRes.json();
    state.aiBulletin = aiRes.ok ? await aiRes.json() : null;

    const frames = state.weatherPkg.nowcast?.radar?.frames || [];
    if (frames.length) state.radarFrameIndex = frames.length - 1;

    renderSheet();
    renderActiveMapLayer();
    renderFavoritesBar();
  } catch (e) {
    console.error("Errore fetch dati:", e);
  }
}

function renderWatchBanner(pkg) {
  const banner = document.getElementById("liguria-watch-banner");
  if (!banner || !pkg) return;

  const conv = pkg.nowcast?.ligurian_convergence || {};
  const windKt = pkg.sea?.marine_conditions?.wind?.speed_knots ?? 0;
  const hydros = pkg.observations_live?.all_river_hydrometers || pkg.observations_live?.nearest_river_hydrometers || [];
  const alertHydros = hydros.filter((h) => h.status_level === "red" || h.status_level === "orange");

  const reasons = [];
  let isRed = false;
  if (alertHydros.length) {
    if (alertHydros.some((h) => h.status_level === "red")) isRed = true;
    reasons.push(`Idrometri in guardia: ${alertHydros.slice(0, 2).map((h) => `${h.name} ${h.level_m}m`).join(", ")}`);
  }
  if ((conv.convergence_score || 0) >= 50) {
    if ((conv.convergence_score || 0) >= 75) isRed = true;
    reasons.push(`Convergenza ${conv.convergence_score}/100`);
  }
  if (windKt >= 34) {
    isRed = true;
    reasons.push(`Burrasca ${windKt} kt`);
  }

  if (!reasons.length) {
    banner.hidden = true;
    return;
  }
  banner.className = isRed ? "watch-banner glass-panel watch-red" : "watch-banner glass-panel";
  banner.textContent = reasons.join(" · ");
  banner.hidden = false;
}

function renderSheet() {
  const pkg = state.weatherPkg;
  if (!pkg) return;
  const loc = pkg.location || pkg.district;
  const cur = pkg.nowcast.current;
  const landRisk = pkg.land.risk_assessment;
  const sea = pkg.sea.marine_conditions;
  const wind = sea.wind;
  const waves = sea.waves;
  const cp = sea.coastal_physics;
  const isSea = state.mode === "sea";

  const titleEl = document.getElementById("sheet-peek-title");
  const modeBadge = document.getElementById("sheet-mode-badge");
  const peekSummary = document.getElementById("sheet-peek-summary");
  if (titleEl) titleEl.textContent = state.customCoords && pkg.coordinates?.is_custom_pin ? `Presso ${loc.name}` : loc.name;
  if (modeBadge) modeBadge.textContent = isSea ? "Mare" : "Terra";
  if (peekSummary) {
    peekSummary.textContent = isSea
      ? `${wind.ligurian_name} ${wind.speed_knots} kt · Hs ${waves.significant_height_m}m`
      : `${cur.temp_c.toFixed(1)}°C · ${Math.round(cur.wind_kmh)} km/h`;
  }

  const rainPeak = Math.max(
    ...(pkg.forecast?.hourly_48h || []).slice(0, 6).map((h) => h.precip_max_lam_mm ?? h.precip_mm ?? 0),
    0
  );
  const shortEl = document.getElementById("ai-short-summary");
  const fullEl = document.getElementById("ai-full-analysis");
  if (shortEl) {
    const convScore = pkg.nowcast?.ligurian_convergence?.convergence_score ?? 0;
    if (isSea) {
      shortEl.textContent = `${waves.douglas.label} a ${loc.name} con ${wind.ligurian_name} a ${wind.speed_knots} kt. Risacca a riva intorno a ${cp.bay_surge.shore_breaker_height_m}m.`;
    } else {
      const rainHint = rainPeak >= 1.0 ? `Rovesci fino a ${rainPeak.toFixed(1)} mm/h nelle prossime 6h.` : convScore >= 60 ? "Possibili addensamenti locali." : "Asciutto nelle prossime ore.";
      shortEl.textContent = `${cur.weather_description} a ${loc.name}, ${wind.ligurian_name.toLowerCase()} ${Math.round(cur.wind_kmh)} km/h. ${rainHint}`;
    }
  }
  if (fullEl) {
    fullEl.textContent = state.aiBulletin?.synoptic_nowcast_analysis || "";
  }

  const metricsEl = document.getElementById("sheet-metrics-grid");
  if (metricsEl) {
    const perc = landRisk.thermo_comfort?.perceived_temp_c ?? cur.temp_c;
    const tempSub = Math.abs(perc - cur.temp_c) >= 1.0 ? `Percepita ${perc}°C` : cur.weather_description;
    const precip1h = landRisk.hydrogeological.precip_1h_mm ?? 0;
    const rainSub = precip1h > 0
      ? landRisk.hydrogeological.label
      : rainPeak >= 1.0
        ? `Rovesci attesi (${rainPeak.toFixed(1)} mm/h)`
        : "Asciutto nelle 6h";

    const cards = isSea
      ? [
          { label: "Vento", value: `${wind.speed_knots} kt`, sub: `Raffica ${wind.gust_knots} kt · ${wind.ligurian_name}` },
          { label: "Onda", value: `${waves.significant_height_m} m`, sub: `Max ${waves.max_height_m}m · Tp ${waves.peak_period_s}s` },
          { label: "Risacca", value: `${cp.bay_surge.shore_breaker_height_m} m`, sub: `${cp.tides.is_synthetic ? "Marea stimata" : "Marea"} ${cp.tides.current_height_cm}cm` },
          { label: "Pressione", value: `${Math.round(cur.pressure_hpa)} hPa`, sub: cur.pressure_trend_label || "Stabile" },
        ]
      : [
          { label: "Temperatura", value: `${cur.temp_c.toFixed(1)}°C`, sub: tempSub },
          { label: "Pioggia 1h", value: `${precip1h} mm/h`, sub: rainSub },
          { label: "Vento", value: `${Math.round(cur.wind_kmh)} km/h`, sub: `${wind.ligurian_name} · ${wind.cardinal}` },
          { label: "Pressione", value: `${Math.round(cur.pressure_hpa)} hPa`, sub: cur.pressure_trend_label || "Stabile" },
        ];
    metricsEl.innerHTML = cards
      .map((c) => `<div class="metric-chip"><span>${escapeHtml(c.label)}</span><strong>${escapeHtml(c.value)}</strong><span>${escapeHtml(c.sub)}</span></div>`)
      .join("");
  }

  // Timeline oraria scorrevole 24h
  const strip = document.getElementById("hourly-strip");
  const hourly = pkg.forecast?.hourly_48h || [];
  if (strip && hourly.length) {
    strip.innerHTML = hourly
      .slice(0, 24)
      .map((h) => {
        const hh = (h.time.split("T")[1] || h.time).slice(0, 5);
        const windKmh = Math.round(h.wind_kmh ?? (h.wind_knots ?? 0) * 1.852);
        const mainV = isSea ? `${Math.round(h.wind_knots)} kt` : `${Math.round(h.temp_c)}°`;
        const subV = isSea ? `Hs ${h.wave_hs_m}m` : `${windKmh} km/h`;
        const rainV = h.precip_mm > 0 ? `${h.precip_mm}mm` : "—";
        return `<div class="hour-cell" role="listitem"><span class="h-time">${escapeHtml(hh)}</span><span class="h-main">${escapeHtml(mainV)}</span><span class="h-sub">${escapeHtml(subV)}</span><span class="h-rain">${escapeHtml(rainV)}</span></div>`;
      })
      .join("");
  }

  renderWatchBanner(pkg);
  renderExpandedDetails(pkg);
}

function renderExpandedDetails(pkg) {
  const hourly = pkg.forecast?.hourly_48h || [];
  const divEl = document.getElementById("models-divergence-summary");
  if (divEl && hourly.length) {
    const slice24 = hourly.slice(0, 24);
    const maxSpread = slice24.reduce((a, b) => ((b.model_spread?.wind_spread_knots ?? 0) > (a.model_spread?.wind_spread_knots ?? 0) ? b : a), slice24[0]);
    const spreadKt = maxSpread.model_spread?.wind_spread_knots ?? 0;
    const tStr = (maxSpread.time.split("T")[1] || maxSpread.time).slice(0, 5);
    divEl.textContent = spreadKt < 5 ? `Accordo alto (Δ max ${spreadKt} kt)` : `Divergenza max Δ ${spreadKt} kt alle ${tStr}`;
  }

  const tbody = document.getElementById("models-5-hourly-tbody");
  if (tbody && hourly.length) {
    const fmt = (m, k) => (m[k]?.wind_knots !== null && m[k]?.wind_knots !== undefined ? `${m[k].wind_knots}kt` : "--");
    tbody.innerHTML = hourly
      .slice(0, 24)
      .map((h) => {
        const hh = (h.time.split("T")[1] || h.time).slice(0, 5);
        const m = h.models || {};
        const sp = h.model_spread?.wind_spread_knots ?? 0;
        const spCls = sp >= 8 ? "spread-hi" : sp >= 5 ? "spread-mid" : "";
        const rnCls = (h.precip_mm ?? 0) >= 1 ? "rain-hi" : "";
        return `<tr><td>${escapeHtml(hh)}</td><td>${escapeHtml(h.wind_knots)}kt</td><td>${escapeHtml(fmt(m, "meteofrance_arome_france_hd"))}</td><td>${escapeHtml(fmt(m, "icon_d2"))}</td><td>${escapeHtml(fmt(m, "ecmwf_ifs025"))}</td><td>${escapeHtml(fmt(m, "gfs_seamless"))}</td><td>${escapeHtml(fmt(m, "met_norway"))}</td><td class="${spCls}">${escapeHtml(sp)}kt</td><td class="${rnCls}">${escapeHtml(h.precip_mm)}mm</td><td>${escapeHtml(h.wave_hs_m)}m</td></tr>`;
      })
      .join("");
  }

  const stGrid = document.getElementById("omirl-stations-grid");
  const stations = pkg.observations_live?.nearest_weather_stations || [];
  if (stGrid) {
    stGrid.innerHTML = stations
      .slice(0, 6)
      .map((st) => {
        const hasWind = st.has_live_wind !== false && st.sensor !== "Termo/Pluvio";
        const sensor = hasWind ? "Vento" : st.has_live_temp !== false ? "Termo" : "Pluvio";
        const gustStr = st.gust_estimated ? `~${st.gust_knots}` : `${st.gust_knots}`;
        return `<div class="obs-row"><div class="obs-row-top"><span>${escapeHtml(st.name)} (${escapeHtml(st.code)})</span><span>${escapeHtml(st.distance_km)} km</span></div><div class="obs-row-sub">${escapeHtml(st.muni)} • Ore ${escapeHtml(st.observed_at)}</div><div class="obs-row-vals">${escapeHtml(st.temp_c)}°C · ${escapeHtml(st.precip_1h_mm)}mm · ${escapeHtml(st.wind_knots)}kt (r.${escapeHtml(gustStr)})</div><button type="button" class="btn-mini btn-omirl-chart" data-station-code="${escapeHtml(st.code)}" data-sensor="${escapeHtml(sensor)}">Curva 24h (${escapeHtml(sensor)})</button></div>`;
      })
      .join("");
  }

  const hySection = document.getElementById("hydrometers-section");
  if (hySection) hySection.hidden = state.mode === "sea";

  const hyGrid = document.getElementById("omirl-hydrometers-grid");
  const hydros = pkg.observations_live?.nearest_river_hydrometers || [];
  if (hyGrid) {
    hyGrid.innerHTML = hydros
      .slice(0, 6)
      .map((hy) => `<div class="obs-row"><div class="obs-row-top"><span><span class="hydro-dot ${escapeHtml(hy.status_level || "green")}"></span>${escapeHtml(hy.name)} (${escapeHtml(hy.river)})</span><span>${escapeHtml(hy.level_m)} m</span></div><div class="obs-row-sub">Gialla ${escapeHtml(hy.warn_threshold_m)}m · Rossa ${escapeHtml(hy.alarm_threshold_m)}m · Ore ${escapeHtml(hy.observed_at)}</div></div>`)
      .join("");
  }

  const arpalBox = document.getElementById("arpal-bulletin-box");
  const arpal = pkg.official_bulletins?.arpal;
  if (arpalBox && arpal) {
    let issuedStr = arpal.issued_at || "";
    try {
      if (issuedStr) {
        const d = new Date(issuedStr);
        if (!Number.isNaN(d.getTime())) {
          issuedStr = d.toLocaleString("it-IT", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
        }
      }
    } catch (_) {}
    const days = (arpal.days || [])
      .map((d) => `<div class="obs-row"><div class="obs-row-top"><span>${escapeHtml(d.label)}</span></div><div class="obs-row-sub">${escapeHtml(d.forecast_text)} — Venti: ${escapeHtml(d.winds)} — Mare: ${escapeHtml(d.sea)}</div></div>`)
      .join("");
    arpalBox.innerHTML = `<div class="obs-row"><div class="obs-row-top"><span>${escapeHtml(arpal.source || "ARPAL")}</span><span>${escapeHtml(issuedStr)}</span></div><div class="obs-row-sub">${escapeHtml(arpal.synoptic_situation || "")}</div></div>${days}`;
  }

  const dl = document.getElementById("disclaimer-land-text");
  const ds = document.getElementById("disclaimer-sea-text");
  if (dl) dl.textContent = pkg.land?.safety_disclaimer || "";
  if (ds) ds.textContent = pkg.sea?.safety_disclaimer || "";

  if (state.sheetState === "expanded") {
    renderCharts(hourly, state);
  }
}

window.inspectOmirlStationChart = async function inspectOmirlStationChart(code, sensor, btnEl) {
  if (!code || !btnEl) return;
  btnEl.textContent = "Caricamento...";
  try {
    const res = await fetchOmirlChart(code, sensor);
    if (!res.ok) {
      btnEl.textContent = "Serie 24h non disponibile";
      return;
    }
    const data = await res.json();
    const raw = data.recent_24_points?.length ? data.recent_24_points : (data.series?.[0]?.points || []).slice(-24);
    const pts = raw.map((p) => Number(p.value)).filter(Number.isFinite);
    if (!pts.length) {
      btnEl.textContent = "Nessun punto 24h";
      return;
    }
    const minV = Math.min(...pts);
    const maxV = Math.max(...pts);
    const span = maxV - minV || 1;
    const poly = pts.map((v, i) => `${(pts.length === 1 ? 110 : 4 + (i / (pts.length - 1)) * 212).toFixed(1)},${(42 - ((v - minV) / span) * 36).toFixed(1)}`).join(" ");
    btnEl.outerHTML = `<div class="omirl-sparkline-box"><div class="omirl-sparkline-head"><span>${escapeHtml(sensor)} (${escapeHtml(code)})</span><strong>${escapeHtml(pts[pts.length - 1])} ${escapeHtml(data.unit || "")}</strong></div><svg class="omirl-sparkline-svg" viewBox="0 0 220 48" preserveAspectRatio="none"><polyline points="${poly}" fill="none" stroke="var(--accent)" stroke-width="2" /></svg><div class="omirl-sparkline-meta"><span>Min ${escapeHtml(minV)}</span><span>Max ${escapeHtml(maxV)}</span></div></div>`;
  } catch (_) {
    btnEl.textContent = "Errore serie";
  }
};

function populateRouteSelects() {
  const oSel = document.getElementById("route-origin");
  const dSel = document.getElementById("route-dest");
  if (!oSel || !dSel) return;
  oSel.innerHTML = "";
  dSel.innerHTML = "";
  state.coastalWaypoints.forEach((wp) => {
    const opt = document.createElement("option");
    opt.value = wp.id;
    opt.textContent = wp.name;
    oSel.appendChild(opt);
    dSel.appendChild(opt.cloneNode(true));
  });
  oSel.value = "portofino";
  dSel.value = "san_fruttuoso";
}

async function calculateAndDrawRoute() {
  const origin = document.getElementById("route-origin")?.value || "portofino";
  const dest = document.getElementById("route-dest")?.value || "san_fruttuoso";
  const speed = document.getElementById("route-speed")?.value || "6.0";
  const duration = document.getElementById("route-duration")?.value || "90";
  const stop = document.getElementById("route-stop")?.value || "20";

  const params = new URLSearchParams({ origin, dest, cruise_knots: speed, duration_min: duration, stop_min: stop, round_trip: "true" });
  const plan = await fetchCoastalRoute(params);
  if (!plan) return;
  state.routePlan = plan;

  const kpiEl = document.getElementById("route-results-grid");
  if (kpiEl) {
    kpiEl.innerHTML = `
      <div class="route-kpi"><span>Distanza A+R</span><strong>${escapeHtml(plan.total_distance_nm)} NM</strong></div>
      <div class="route-kpi"><span>Navigazione</span><strong>${escapeHtml(plan.estimated_navigation_minutes)} min</strong></div>
      <div class="route-kpi"><span>Media richiesta</span><strong>${escapeHtml(plan.required_average_speed_knots)} kt</strong></div>
      <div class="route-kpi"><span>Turnaround</span><strong>${escapeHtml(plan.schedule.latest_turnaround_time)}</strong></div>`;
  }

  const legsEl = document.getElementById("route-legs-list");
  if (legsEl) {
    legsEl.innerHTML = (plan.legs || [])
      .map((l, i) => `<div class="route-leg-row">${i + 1}. ${escapeHtml(l.from_name)} → ${escapeHtml(l.to_name)} (<strong>${escapeHtml(l.distance_nm)} NM</strong>${l.amp_speed_limit_knots ? `, max ${escapeHtml(l.amp_speed_limit_knots)} kt` : ""})</div>`)
      .join("");
  }

  if (state.map && state.routeGroup && plan.waypoints?.length) {
    state.routeGroup.clearLayers();
    const latlngs = plan.waypoints.map((w) => [w.lat, w.lon]);
    const poly = L.polyline(latlngs, { color: "#0284c7", weight: 4, dashArray: "7, 6" }).addTo(state.routeGroup);
    plan.waypoints.forEach((w, idx) => {
      L.circleMarker([w.lat, w.lon], { radius: 5, color: "#ffffff", weight: 2, fillColor: idx === 0 ? "#059669" : idx === plan.waypoints.length - 1 ? "#d97706" : "#0284c7", fillOpacity: 1 })
        .bindTooltip(`${idx + 1}. ${escapeHtml(w.name)}`)
        .addTo(state.routeGroup);
    });
    const isWide = window.innerWidth >= 960;
    state.map.fitBounds(poly.getBounds(), {
      paddingTopLeft: [30, 80],
      paddingBottomRight: isWide ? [390, 90] : [90, 360],
    });
  }
}

function bindEvents() {
  const searchInput = document.getElementById("loc-search-input");
  const pickerPanel = document.getElementById("loc-picker-panel");
  let activeTypeFilter = "";

  if (searchInput && pickerPanel) {
    searchInput.addEventListener("focus", () => {
      pickerPanel.hidden = false;
      renderLocationDropdown(activeTypeFilter, searchInput.value);
    });
    searchInput.addEventListener("input", () => {
      pickerPanel.hidden = false;
      renderLocationDropdown(activeTypeFilter, searchInput.value);
    });
  }

  document.addEventListener("click", (ev) => {
    if (!ev.target.closest(".search-dock")) closeSearchDropdown();
  });

  document.querySelectorAll(".loc-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeTypeFilter = chip.getAttribute("data-loc-type") || "";
      document.querySelectorAll(".loc-chip").forEach((c) => {
        const act = c === chip;
        c.classList.toggle("active", act);
        c.setAttribute("aria-pressed", act ? "true" : "false");
      });
      renderLocationDropdown(activeTypeFilter, searchInput?.value || "");
    });
  });

  document.getElementById("loc-picker-list")?.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".loc-item-btn");
    if (btn) selectLocationById(btn.getAttribute("data-loc-id"));
  });

  document.getElementById("fav-chips-bar")?.addEventListener("click", (ev) => {
    const chip = ev.target.closest(".fav-chip");
    if (chip) selectLocationById(chip.getAttribute("data-fav-id"));
  });

  document.getElementById("btn-toggle-fav")?.addEventListener("click", () => {
    if (!state.selectedLocationId) return;
    let favs = loadFavorites();
    favs = favs.includes(state.selectedLocationId)
      ? favs.filter((id) => id !== state.selectedLocationId)
      : [state.selectedLocationId, ...favs].slice(0, 5);
    saveFavorites(favs);
    renderFavoritesBar();
  });

  document.getElementById("btn-gps")?.addEventListener("click", () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      selectCoordsOnMap(Number(pos.coords.latitude.toFixed(4)), Number(pos.coords.longitude.toFixed(4)));
    });
  });

  document.querySelectorAll(".rail-btn[data-layer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeLayer = btn.getAttribute("data-layer");
      document.querySelectorAll(".rail-btn[data-layer]").forEach((b) => {
        const act = b === btn;
        b.classList.toggle("active", act);
        b.setAttribute("aria-pressed", act ? "true" : "false");
      });
      renderActiveMapLayer();
    });
  });

  const routePanel = document.getElementById("route-panel");
  document.getElementById("btn-open-route")?.addEventListener("click", (e) => {
    if (!routePanel) return;
    routePanel.hidden = !routePanel.hidden;
    e.currentTarget.setAttribute("aria-expanded", routePanel.hidden ? "false" : "true");
    if (!routePanel.hidden) {
      setSheetState("peek");
      calculateAndDrawRoute();
    }
  });
  document.getElementById("btn-close-route")?.addEventListener("click", () => {
    if (routePanel) routePanel.hidden = true;
  });
  document.getElementById("btn-calc-route")?.addEventListener("click", calculateAndDrawRoute);

  document.getElementById("btn-toggle-theme")?.addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  });

  document.getElementById("btn-radar-play")?.addEventListener("click", toggleRadarAnimation);
  document.getElementById("radar-frame-slider")?.addEventListener("input", (e) => {
    state.radarFrameIndex = Number(e.target.value);
    updateRadarLayer();
  });

  document.getElementById("btn-sheet-ask")?.addEventListener("click", (e) => {
    e.stopPropagation();
    setSheetState("expanded");
    setTimeout(() => document.getElementById("ask-input")?.focus(), 80);
  });
  document.getElementById("btn-sheet-expand")?.addEventListener("click", (e) => {
    e.stopPropagation();
    cycleSheetState();
  });
  document.getElementById("btn-sheet-refresh")?.addEventListener("click", (e) => {
    e.stopPropagation();
    refreshAllData(true);
  });
  document.getElementById("sheet-handle-row")?.addEventListener("click", cycleSheetState);

  document.getElementById("omirl-stations-grid")?.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".btn-omirl-chart");
    if (btn) window.inspectOmirlStationChart(btn.getAttribute("data-station-code"), btn.getAttribute("data-sensor") || "Vento", btn);
  });

  document.getElementById("ask-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const inp = document.getElementById("ask-input");
    const ansBox = document.getElementById("ask-answer");
    const q = (inp?.value || "").trim();
    if (q.length < 2 || !ansBox) return;

    ansBox.textContent = "Analisi dei dati locali in corso...";
    ansBox.hidden = false;
    try {
      const res = await askPointQuestion({
        question: q,
        location: state.customCoords ? null : state.selectedLocationId,
        lat: state.customCoords?.lat ?? null,
        lon: state.customCoords?.lon ?? null,
        mode: state.mode,
      });
      ansBox.textContent = res.answer;
    } catch (err) {
      ansBox.textContent = err.message || "Impossibile rispondere in questo momento.";
    }
  });
}

async function initApp() {
  try {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "dark") applyTheme("dark");
  } catch (_) {}

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js?v=4.0").catch(() => {});
  }

  initLeafletMap();
  bindEvents();

  try {
    const data = await fetchLocationsCatalog();
    state.locations = data.locations || [];
    state.ampZones = data.amp_portofino_zones || [];
    state.coastalWaypoints = data.coastal_waypoints || [];
    populateRouteSelects();
    renderFavoritesBar();
  } catch (e) {
    console.error("Errore catalogo:", e);
  }

  await refreshAllData(false);
}

document.addEventListener("DOMContentLoaded", initApp);
