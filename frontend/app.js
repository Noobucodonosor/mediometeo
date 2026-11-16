/* ==========================================================================
   MedioMeteo Genova v2.2 — Client Application a 6 Schede Chiuse (ADR-0005, ADR-0006, ADR-0007)
   Caratteristiche "Biglietto da Visita" (Flagship Edition):
   - Always-On Telemetry HUD Strip (5 parametri live sempre visibili anche sulla mappa).
   - 6 Schede Chiuse mutuamente esclusive: all'avvio apre `3. MAPPA LIVE` Full-Canvas.
   - Cliccando un Comune, Quartiere, Rada o punto libero sulla mappa -> seleziona la località e
     passa automaticamente a `1. ADESSO (Sensori Reali OMIRL, Idrometri, Rosa dei Venti SVG & Webcam)`.
   - Quadrante Nautico Vettoriale SVG in `1. ADESSO`: Rosa dei Venti Ligure + Vettore Vento +
     Vettore Swell + Cono di Apertura Costiera (`bay_open_deg`) con risacca.
   - 199 Sensori Reali OMIRL Regione Liguria (23 Anemometri con frecce direzionali, 75 Termometri,
     77 Pluviometri, 24 Idrometri Fluviali Reali con barre graduate, Boa Capo Mele, Webcam).
   - Modalità MARE a Fisica Costiera Pura (Zero semafori consiglio soggettivi).
   ========================================================================== */

const state = {
  mode: "land", // 'land' | 'sea'
  activeTab: "tab-mappa", // Scheda predefinita all'avvio: 3. MAPPA LIVE
  selectedLocationId: "COM-GENOVA",
  customCoords: null, // { lat, lon }
  locations: [],
  filteredLocations: [],
  ampZones: [],
  coastalWaypoints: [],
  weatherPkg: null,
  aiBulletin: null,
  routePlan: null,
  map: null,
  radarLayer: null,
  radarVisible: true,
  radarPlaying: false,
  radarTimer: null,
  radarFrameIndex: 0,
  omirlLayerGroup: null,
  omirlVisible: true,
  webcamLayerGroup: null,
  webcamsVisible: true,
  ampLayerGroup: null,
  ampVisible: true,
  locationsLayerGroup: null,
  routePolyline: null,
  customMarker: null,
  chartMultiModel: null,
  chartWindWave: null,
};

const LEVEL_LABELS = {
  green: "REGOLARE",
  yellow: "ATTENZIONE / CAUTELA",
  orange: "CRITICITÀ MODERATA-ALTA",
  red: "ALLERTA / CRITICITÀ ELEVATA",
};

function setBadgeLevel(el, level, text) {
  if (!el) return;
  el.className = `badge-pill level-${level || "green"}`;
  el.textContent = text;
}

window.switchTab = function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isTarget = btn.getAttribute("data-tab") === tabId;
    btn.classList.toggle("active", isTarget);
    btn.setAttribute("aria-selected", isTarget ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabId);
  });

  if (tabId === "tab-mappa" && state.map) {
    setTimeout(() => state.map.invalidateSize(), 80);
  }
  if (tabId === "tab-modelli" && state.weatherPkg) {
    setTimeout(() => renderCharts(state.weatherPkg.forecast.hourly_48h), 60);
  }
};

async function initApp() {
  bindUIEvents();
  await loadLocationsCatalog();
  initLeafletMap();
  await refreshAllData(false);
  await calculateCoastalRoute();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .getRegistrations()
      .then((regs) => regs.forEach((r) => r.update().catch(() => {})))
      .catch(() => {});
    navigator.serviceWorker.register("/sw.js?v=2.3").catch(() => {});
  }
}

function bindUIEvents() {
  // 6 Tab Buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      window.switchTab(targetTab);
    });
  });

  // Mode Switch TERRA / MARE
  document.getElementById("btn-mode-land").addEventListener("click", () => switchMode("land"));
  document.getElementById("btn-mode-sea").addEventListener("click", () => switchMode("sea"));

  // Filtri e Ricerca 118 Località
  const typeFilter = document.getElementById("loc-type-filter");
  const searchInput = document.getElementById("loc-search-input");
  const selectLoc = document.getElementById("district-select");

  typeFilter.addEventListener("change", () => {
    populateLocationSelect();
    renderLocationsOnMap();
  });
  searchInput.addEventListener("input", () => populateLocationSelect());

  selectLoc.addEventListener("change", async (e) => {
    await selectLocationById(e.target.value, false);
  });

  // GPS Button
  document.getElementById("btn-gps").addEventListener("click", () => {
    if (!navigator.geolocation) {
      alert("Geolocalizzazione non supportata dal browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        state.customCoords = { lat, lon };
        await refreshAllData(false);
        window.switchTab("tab-adesso");
      },
      () => {
        alert("Impossibile ottenere la posizione GPS. Usa la Mappa Live o il selettore Comuni.");
      }
    );
  });

  // Refresh Live Button
  document.getElementById("btn-refresh").addEventListener("click", async () => {
    await refreshAllData(true);
  });

  // Map Layer Toggles (Floating Pills)
  document.getElementById("btn-toggle-radar").addEventListener("click", (e) => {
    state.radarVisible = !state.radarVisible;
    e.currentTarget.classList.toggle("active", state.radarVisible);
    e.currentTarget.textContent = `🌧️ Radar: ${state.radarVisible ? "ON" : "OFF"}`;
    updateRadarLayer();
  });

  document.getElementById("btn-toggle-omirl").addEventListener("click", (e) => {
    state.omirlVisible = !state.omirlVisible;
    e.currentTarget.classList.toggle("active", state.omirlVisible);
    e.currentTarget.textContent = `💨 Sensori OMIRL: ${state.omirlVisible ? "ON" : "OFF"}`;
    renderMapOverlays();
  });

  document.getElementById("btn-toggle-webcams").addEventListener("click", (e) => {
    state.webcamsVisible = !state.webcamsVisible;
    e.currentTarget.classList.toggle("active", state.webcamsVisible);
    e.currentTarget.textContent = `📷 Webcam: ${state.webcamsVisible ? "ON" : "OFF"}`;
    renderMapOverlays();
  });

  document.getElementById("btn-toggle-amp").addEventListener("click", (e) => {
    state.ampVisible = !state.ampVisible;
    e.currentTarget.classList.toggle("active", state.ampVisible);
    e.currentTarget.textContent = `⚓ Zone AMP: ${state.ampVisible ? "ON" : "OFF"}`;
    renderMapOverlays();
  });

  // Radar Player Controls
  document.getElementById("btn-radar-play").addEventListener("click", toggleRadarAnimation);
  document.getElementById("radar-frame-slider").addEventListener("input", (e) => {
    state.radarFrameIndex = Number(e.target.value);
    updateRadarLayer();
  });

  // Route Calculator
  document.getElementById("btn-calc-route").addEventListener("click", calculateCoastalRoute);
}

async function selectLocationById(locId, autoSwitchToAdesso = false) {
  state.selectedLocationId = locId;
  state.customCoords = null;
  if (state.customMarker && state.map) {
    state.map.removeLayer(state.customMarker);
    state.customMarker = null;
  }

  const found = state.locations.find((l) => l.id === locId);
  if (found) {
    state.mode = found.category;
    updateModeButtonsUI();
    const selectEl = document.getElementById("district-select");
    if (selectEl) selectEl.value = locId;
    if (state.map) {
      state.map.flyTo([found.lat, found.lon], found.category === "sea" ? 12 : 12, {
        duration: 0.65,
      });
    }
  }

  await refreshAllData(false);
  renderLocationsOnMap();
  if (autoSwitchToAdesso) {
    window.switchTab("tab-adesso");
  }
}

function updateModeButtonsUI() {
  const btnLand = document.getElementById("btn-mode-land");
  const btnSea = document.getElementById("btn-mode-sea");
  if (state.mode === "land") {
    btnLand.className = "mode-btn active-land";
    btnSea.className = "mode-btn";
  } else {
    btnLand.className = "mode-btn";
    btnSea.className = "mode-btn active-sea";
  }
}

async function switchMode(targetMode) {
  state.mode = targetMode;
  updateModeButtonsUI();

  const currentLoc = state.locations.find((l) => l.id === state.selectedLocationId);
  if (currentLoc && currentLoc.category !== targetMode && !state.customCoords) {
    const defaultId =
      targetMode === "sea"
        ? "SEA-AVAMPORTO-DI-GENOVA-&-DIGA-FORANEA-LEVANTE"
        : "COM-GENOVA";
    await selectLocationById(defaultId, false);
  } else if (state.weatherPkg) {
    renderDashboard();
  }
}

async function loadLocationsCatalog() {
  const res = await fetch("/api/v1/locations");
  const data = await res.json();
  state.locations = data.locations || [];
  state.ampZones = data.amp_portofino_zones || [];
  state.coastalWaypoints = data.coastal_waypoints || [];

  populateLocationSelect();
  populateRouteWaypoints();
}

function populateLocationSelect() {
  const select = document.getElementById("district-select");
  const typeFilter = document.getElementById("loc-type-filter").value;
  const query = (document.getElementById("loc-search-input").value || "").trim().toLowerCase();

  const filtered = state.locations.filter((loc) => {
    if (typeFilter && loc.loc_type !== typeFilter) return false;
    if (
      query &&
      !loc.name.toLowerCase().includes(query) &&
      !loc.valley_or_sector.toLowerCase().includes(query)
    ) {
      return false;
    }
    return true;
  });

  state.filteredLocations = filtered;
  select.innerHTML = "";

  const groups = {
    comune: { label: "🏛️ 67 COMUNI CITTÀ METROPOLITANA DI GENOVA", el: document.createElement("optgroup") },
    quartiere: { label: "🏙️ 25 QUARTIERI / MUNICIPI DI GENOVA", el: document.createElement("optgroup") },
    rada_porto: { label: "⚓ 20 RADE, PORTI, CALE & CAPI (GOLFO LIGURE)", el: document.createElement("optgroup") },
    valico: { label: "⛰️ 6 VALICHI APPENNINICI & AUTOSTRADALI", el: document.createElement("optgroup") },
  };

  Object.values(groups).forEach((g) => {
    g.el.label = g.label;
  });

  filtered.forEach((loc) => {
    const opt = document.createElement("option");
    opt.value = loc.id;
    const icon =
      loc.loc_type === "rada_porto"
        ? "⚓"
        : loc.loc_type === "valico"
        ? "⛰️"
        : loc.loc_type === "quartiere"
        ? "🏙️"
        : "🏛️";
    opt.textContent = `${icon} ${loc.name} (${loc.valley_or_sector})`;
    if (groups[loc.loc_type]) {
      groups[loc.loc_type].el.appendChild(opt);
    }
  });

  Object.values(groups).forEach((g) => {
    if (g.el.children.length > 0) {
      select.appendChild(g.el);
    }
  });

  if (filtered.some((l) => l.id === state.selectedLocationId)) {
    select.value = state.selectedLocationId;
  } else if (filtered.length > 0) {
    select.value = filtered[0].id;
  }
}

function populateRouteWaypoints() {
  const selOrigin = document.getElementById("route-origin");
  const selDest = document.getElementById("route-dest");
  if (!selOrigin || !selDest) return;

  selOrigin.innerHTML = "";
  selDest.innerHTML = "";

  state.coastalWaypoints.forEach((wp) => {
    const o1 = document.createElement("option");
    o1.value = wp.id;
    o1.textContent = `⚓ ${wp.name}${wp.amp_zone ? " [" + wp.amp_zone + "]" : ""}`;
    const o2 = o1.cloneNode(true);
    selOrigin.appendChild(o1);
    selDest.appendChild(o2);
  });

  selOrigin.value = "portofino";
  selDest.value = "san_fruttuoso";
}

function initLeafletMap() {
  if (typeof L === "undefined") return;

  state.map = L.map("genova-map", {
    center: [44.395, 9.03],
    zoom: 10,
    zoomControl: true,
  });

  // Base Map OpenStreetMap Ufficiale (100% Free, Zero API Key) con filtro Dark Sala Operativa
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors | MedioMeteo Genova",
    maxNativeZoom: 18,
    maxZoom: 18,
    className: "osm-dark-tiles",
  }).addTo(state.map);

  // Layer Nautico Ufficiale OpenSeaMap (fari, boe, secche, batimetria portuale)
  L.tileLayer("https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenSeaMap",
    maxNativeZoom: 17,
    maxZoom: 18,
    opacity: 0.9,
  }).addTo(state.map);

  state.locationsLayerGroup = L.layerGroup().addTo(state.map);
  state.ampLayerGroup = L.layerGroup().addTo(state.map);
  state.omirlLayerGroup = L.layerGroup().addTo(state.map);
  state.webcamLayerGroup = L.layerGroup().addTo(state.map);

  renderLocationsOnMap();
  state.map.on("zoomend", () => renderLocationsOnMap());

  // Click libero sulla Mappa Live -> seleziona coordinata e passa automaticamente a 1. ADESSO (ADR-0006)
  state.map.on("click", async (ev) => {
    const lat = Number(ev.latlng.lat.toFixed(4));
    const lon = Number(ev.latlng.lng.toFixed(4));
    state.customCoords = { lat, lon };

    if (state.customMarker) {
      state.map.removeLayer(state.customMarker);
    }
    state.customMarker = L.circleMarker([lat, lon], {
      radius: 9,
      color: "#38bdf8",
      weight: 3,
      fillColor: "#f59e0b",
      fillOpacity: 0.92,
    })
      .addTo(state.map)
      .bindPopup(`Punto selezionato:<br><strong>${lat}, ${lon}</strong>`)
      .openPopup();

    await refreshAllData(false);
    window.switchTab("tab-adesso");
  });
}

function renderLocationsOnMap() {
  if (!state.map || !state.locationsLayerGroup) return;
  state.locationsLayerGroup.clearLayers();

  const currentZoom = state.map.getZoom() || 10;
  const typeFilter = document.getElementById("loc-type-filter")?.value || "";

  state.locations.forEach((loc) => {
    if (typeFilter && loc.loc_type !== typeFilter) return;

    const isMajorHub =
      loc.loc_type === "rada_porto" ||
      loc.loc_type === "valico" ||
      loc.id === state.selectedLocationId ||
      [
        "COM-GENOVA",
        "COM-ARENZANO",
        "COM-COGOLETO",
        "COM-CAMPO-LIGURE",
        "COM-BUSALLA",
        "COM-TORRIGLIA",
        "COM-RECCO",
        "COM-CAMOGLI",
        "COM-PORTOFINO",
        "COM-SANTA-MARGHERITA-LIGURE",
        "COM-RAPALLO",
        "COM-CHIAVARI",
        "COM-LAVAGNA",
        "COM-SESTRI-LEVANTE",
        "COM-MONEGLIA",
        "COM-SANTO-STEFANO-D-AVETO",
      ].includes(loc.id);

    if (!typeFilter && currentZoom < 11 && !isMajorHub) {
      return;
    }

    const isSelected = loc.id === state.selectedLocationId;
    const colorMap = {
      comune: "#10b981",
      quartiere: "#34d399",
      rada_porto: "#0ea5e9",
      valico: "#f59e0b",
    };
    const symbolMap = {
      comune: "🏛️",
      quartiere: "🏙️",
      rada_porto: "⚓",
      valico: "⛰️",
    };
    const bg = isSelected ? "#f59e0b" : colorMap[loc.loc_type] || "#10b981";
    const sym = symbolMap[loc.loc_type] || "📍";
    const size = isSelected ? 30 : loc.loc_type === "rada_porto" || loc.id === "COM-GENOVA" ? 25 : 21;

    const icon = L.divIcon({
      html: `<div style="
        background: ${bg};
        color: #fff;
        border: ${isSelected ? "2.5px solid #fff" : "1.5px solid rgba(255,255,255,0.85)"};
        border-radius: 999px;
        width: ${size}px;
        height: ${size}px;
        display: grid;
        place-items: center;
        font-size: ${size > 23 ? 13 : 10}px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.75);
      ">${sym}</div>`,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });

    const marker = L.marker([loc.lat, loc.lon], { icon }).addTo(state.locationsLayerGroup);
    const bayNote =
      loc.bay_open_deg !== null && loc.bay_open_deg !== undefined
        ? `<br>📐 Cala aperta a <strong>${loc.bay_open_deg}°</strong>`
        : "";
    marker.bindTooltip(
      `<strong>${loc.name}</strong> (${loc.loc_type.toUpperCase()})<br>${loc.valley_or_sector}${bayNote}<br><em>Clicca per aprire 1. 📡 ADESSO</em>`
    );

    marker.on("click", async (ev) => {
      L.DomEvent.stopPropagation(ev);
      await selectLocationById(loc.id, true);
    });
  });
}

function renderMapOverlays() {
  if (!state.map) return;

  // 1. Poligoni AMP Portofino (Zone A, B, C)
  state.ampLayerGroup.clearLayers();
  if (state.ampVisible && state.ampZones.length) {
    state.ampZones.forEach((zone) => {
      const poly = L.polygon(zone.coords, {
        color: zone.color,
        weight: 2,
        fillColor: zone.color,
        fillOpacity: 0.22,
      }).addTo(state.ampLayerGroup);
      poly.bindTooltip(
        `<strong>${zone.name}</strong><br>Limite velocità: <strong>${
          zone.max_speed_knots === 0 ? "DIVIETO ACCESSO" : zone.max_speed_knots + " kt"
        }</strong><br>${zone.rules}`
      );
    });
  }

  if (!state.weatherPkg) return;
  const obs = state.weatherPkg.observations_live || {};

  // 2. Stazioni Reali OMIRL (con Freccia Vettoriale Vento!) & Idrometri sulla Mappa
  state.omirlLayerGroup.clearLayers();
  if (state.omirlVisible) {
    const stations = obs.all_weather_stations || obs.nearest_weather_stations || [];
    stations.forEach((st) => {
      const windDeg = st.wind_dir_deg ?? 0;
      // Il vento meteorologico indica DA dove soffia (es. 0° = da Nord verso Sud).
      // Per ruotare la freccia '➤' (che punta a destra = 90° Est) nella direzione VERSO cui soffia il vento:
      const arrowRotate = (windDeg + 90) % 360;
      const isStrong = (st.wind_knots || 0) >= 16;
      const borderCol = isStrong ? "#f59e0b" : "#38bdf8";
      const textCol = isStrong ? "#fde68a" : "#7dd3fc";

      const badgeHtml = `<div style="
        background: rgba(5, 14, 28, 0.92);
        color: ${textCol};
        border: 1.5px solid ${borderCol};
        border-radius: 999px;
        padding: 1px 6px;
        font-size: 10px;
        font-weight: 800;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        gap: 3px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.7);
      "><span style="display:inline-block;transform:rotate(${arrowRotate}deg);font-size:10px;color:#38bdf8;">➤</span>${st.wind_knots ?? "--"}kt</div>`;

      const icon = L.divIcon({
        html: badgeHtml,
        className: "",
        iconSize: [58, 20],
        iconAnchor: [29, 10],
      });
      const m = L.marker([st.lat, st.lon], { icon }).addTo(state.omirlLayerGroup);
      const srcLabel = st.is_live_rest ? "LIVE REST OMIRL" : "OMIRL / LAM";
      m.bindTooltip(
        `<strong>📡 Centralina OMIRL: ${st.name} (${st.code})</strong> [${srcLabel}]<br>` +
          `Vento: <strong>${st.wind_knots} kt</strong> (${st.wind_kmh} km/h) da ${windDeg}° | Max/Raff: ${st.gust_knots} kt<br>` +
          `Temp: <strong>${st.temp_c}°C</strong> | Pioggia 1h: <strong>${st.precip_1h_mm} mm</strong> • Ore ${st.observed_at}`
      );
      m.on("click", async (ev) => {
        L.DomEvent.stopPropagation(ev);
        state.customCoords = { lat: st.lat, lon: st.lon };
        await refreshAllData(false);
        window.switchTab("tab-adesso");
      });
    });

    const hydros = obs.all_river_hydrometers || obs.nearest_river_hydrometers || [];
    hydros.forEach((hy) => {
      const color =
        hy.status_level === "red"
          ? "#ef4444"
          : hy.status_level === "orange"
          ? "#f97316"
          : "#10b981";
      const badgeHtml = `<div style="
        background: rgba(5, 14, 28, 0.92);
        color: ${color};
        border: 1.5px solid ${color};
        border-radius: 6px;
        padding: 1px 5px;
        font-size: 10px;
        font-weight: 800;
        white-space: nowrap;
        box-shadow: 0 2px 6px rgba(0,0,0,0.7);
      ">🌊 ${hy.level_m}m</div>`;
      const icon = L.divIcon({
        html: badgeHtml,
        className: "",
        iconSize: [54, 18],
        iconAnchor: [27, 9],
      });
      const m = L.marker([hy.lat, hy.lon], { icon }).addTo(state.omirlLayerGroup);
      m.bindTooltip(
        `<strong>🌊 Idrometro Reale OMIRL: ${hy.name} (${hy.river})</strong><br>` +
          `Livello misurato: <strong>${hy.level_m} m</strong> (Soglia Gialla: ${hy.warn_threshold_m} m / Rossa: ${hy.alarm_threshold_m} m)<br>` +
          `${hy.status_label} • Ore ${hy.observed_at}`
      );
    });

    // Boa Ondametrica Capo Mele (se disponibile)
    if (obs.marine_wave_buoy) {
      const b = obs.marine_wave_buoy;
      const buoyIcon = L.divIcon({
        html: `<div style="
          background: #0284c7;
          color: #fff;
          border: 2px solid #fff;
          border-radius: 999px;
          padding: 2px 7px;
          font-size: 10px;
          font-weight: 900;
          white-space: nowrap;
          box-shadow: 0 3px 10px rgba(0,0,0,0.8);
        ">🛟 Boa Hs ${b.wave_hs_m}m</div>`,
        className: "",
        iconSize: [86, 22],
        iconAnchor: [43, 11],
      });
      const bm = L.marker([b.lat, b.lon], { icon: buoyIcon }).addTo(state.omirlLayerGroup);
      bm.bindTooltip(
        `<strong>🛟 ${b.name} (${b.code})</strong><br>Altezza Onda Significativa misurata: <strong>${b.wave_hs_m} m</strong> (Δ ${b.increment_m >= 0 ? "+" : ""}${b.increment_m} m)<br>Aggiornamento: ${b.observed_at}`
      );
    }
  }

  // 3. Pin Webcam Live sulla Mappa
  state.webcamLayerGroup.clearLayers();
  if (state.webcamsVisible) {
    const cams = obs.all_webcams || obs.nearest_webcams || [];
    cams.forEach((cam) => {
      const icon = L.divIcon({
        html: `<div style="
          background: #0284c7;
          color: #fff;
          border: 1.5px solid #fff;
          border-radius: 999px;
          width: 22px;
          height: 22px;
          display: grid;
          place-items: center;
          font-size: 11px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.75);
        ">📷</div>`,
        className: "",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      const m = L.marker([cam.lat, cam.lon], { icon }).addTo(state.webcamLayerGroup);
      const imgPreview = cam.live_image_url
        ? `<img src="${cam.live_image_url}" alt="${cam.name}" style="width:200px;border-radius:6px;margin:4px 0;display:block;" />`
        : "";
      m.bindPopup(
        `<strong>📷 ${cam.name}</strong><br>${cam.view_direction}<br>${imgPreview}` +
          `<a href="${cam.portal_url}" target="_blank" rel="noopener" style="color:#38bdf8;font-weight:700;">Apri Stream / Portale Live ↗</a>`
      );
    });
  }
}

function toggleRadarAnimation() {
  const btn = document.getElementById("btn-radar-play");
  const frames = state.weatherPkg?.nowcast?.radar?.frames || [];
  if (!frames.length) return;

  state.radarPlaying = !state.radarPlaying;
  if (state.radarPlaying) {
    btn.textContent = "⏸️ Pausa Radar";
    state.radarTimer = setInterval(() => {
      state.radarFrameIndex = (state.radarFrameIndex + 1) % frames.length;
      const slider = document.getElementById("radar-frame-slider");
      if (slider) slider.value = String(state.radarFrameIndex);
      updateRadarLayer();
    }, 850);
  } else {
    btn.textContent = "▶️ Play Radar";
    if (state.radarTimer) {
      clearInterval(state.radarTimer);
      state.radarTimer = null;
    }
  }
}

function updateRadarLayer() {
  if (!state.map || !state.weatherPkg) return;
  const radar = state.weatherPkg.nowcast?.radar || {};
  const frames = radar.frames || [];
  const slider = document.getElementById("radar-frame-slider");

  if (slider && frames.length > 0) {
    slider.max = String(frames.length - 1);
    if (state.radarFrameIndex >= frames.length) {
      state.radarFrameIndex = frames.length - 1;
    }
    slider.value = String(state.radarFrameIndex);
  }

  if (state.radarLayer) {
    state.map.removeLayer(state.radarLayer);
    state.radarLayer = null;
  }

  const labelEl = document.getElementById("radar-time-label");
  if (!state.radarVisible) {
    labelEl.textContent = "Radar: OFF";
    return;
  }

  const activeFrame = frames[state.radarFrameIndex] || frames[frames.length - 1];
  const tileUrl = activeFrame?.tile_url || activeFrame?.tile_url_template || radar.latest_tile_url;

  if (tileUrl) {
    state.radarLayer = L.tileLayer(tileUrl, {
      opacity: 0.62,
      zIndex: 450,
      maxNativeZoom: 7,
      maxZoom: 18,
    }).addTo(state.map);
    labelEl.textContent = activeFrame
      ? `Radar: ${activeFrame.time_label} (${activeFrame.is_nowcast ? "Nowcast +30m" : "Osservato"})`
      : "Radar Live";
  } else {
    labelEl.textContent = "Radar: Nessun eco";
  }
}

async function refreshAllData(forceRefresh = false) {
  const params = new URLSearchParams();
  params.set("mode", state.mode);
  if (forceRefresh) params.set("refresh", "true");

  if (state.customCoords) {
    params.set("lat", state.customCoords.lat);
    params.set("lon", state.customCoords.lon);
  } else {
    params.set("location", state.selectedLocationId);
  }

  try {
    const [forecastRes, aiRes] = await Promise.all([
      fetch(`/api/v1/forecast?${params.toString()}`),
      fetch(`/api/v1/ai-bulletin?${params.toString()}`),
    ]);

    if (!forecastRes.ok) {
      const err = await forecastRes.json();
      alert(err.detail || "Coordinate fuori dal dominio della Liguria.");
      return;
    }

    state.weatherPkg = await forecastRes.json();
    state.aiBulletin = aiRes.ok ? await aiRes.json() : null;

    const frames = state.weatherPkg.nowcast?.radar?.frames || [];
    if (frames.length > 0) {
      state.radarFrameIndex = frames.length - 1;
    }

    renderDashboard();
    renderMapOverlays();
    updateRadarLayer();
  } catch (e) {
    console.error("Errore caricamento dati MedioMeteo:", e);
  }
}

function renderDashboard() {
  const pkg = state.weatherPkg;
  if (!pkg) return;

  const d = pkg.district;
  const loc = pkg.location || d;
  const cur = pkg.nowcast.current;
  const conv = pkg.nowcast.ligurian_convergence;
  const landRisk = pkg.land.risk_assessment;
  const seaCond = pkg.sea.marine_conditions;
  const waves = seaCond.waves;
  const wind = seaCond.wind;
  const coastal = seaCond.coastal_physics;
  const thermo = landRisk.thermo_comfort || {};

  // 1. Striscia di Telemetria Sempre Visibile ("Always-On Telemetry HUD")
  const pinSuffix = pkg.coordinates.is_custom_pin
    ? ` (${pkg.coordinates.lat.toFixed(4)}°N, ${pkg.coordinates.lon.toFixed(4)}°E)`
    : "";
  document.getElementById("banner-district-name").textContent = `${loc.name}${pinSuffix}`;
  setBadgeLevel(
    document.getElementById("banner-zone-tag"),
    state.mode === "sea" ? "physics" : landRisk.overall_level,
    loc.arpal_zone || d.arpal_zone
  );
  const typeTag = document.getElementById("banner-type-tag");
  if (typeTag) {
    typeTag.textContent = `${(loc.loc_type || "località").toUpperCase()} • ${loc.valley_or_sector || ""}`;
  }
  document.getElementById("banner-microclimate").textContent =
    loc.shelter_notes || d.microclimate_notes;

  // Popolamento dei 5 Numeri Chiave dell'HUD
  const hudTemp = document.getElementById("hud-val-temp");
  const hudSubTemp = document.getElementById("hud-sub-temp");
  if (hudTemp) {
    hudTemp.textContent = `${cur.temp_c.toFixed(1)}°C`;
    hudSubTemp.textContent = `${cur.weather_description} • Perc. ${thermo.perceived_temp_c ?? cur.temp_c}°C`;
  }

  const hudWind = document.getElementById("hud-val-wind");
  const hudSubWind = document.getElementById("hud-sub-wind");
  if (hudWind) {
    hudWind.textContent =
      state.mode === "sea"
        ? `${wind.speed_knots} kt (raff. ${wind.gust_knots} kt)`
        : `${cur.wind_kmh} km/h (${wind.speed_knots} kt)`;
    hudSubWind.textContent = `${wind.ligurian_name} (${wind.cardinal} ${wind.direction_deg}°) • F${wind.beaufort.force} Bft`;
  }

  const hudWave = document.getElementById("hud-val-wave");
  const hudSubWave = document.getElementById("hud-sub-wave");
  if (hudWave) {
    hudWave.textContent = `Hs ${waves.significant_height_m}m / Hmax ${waves.max_height_m}m`;
    hudSubWave.textContent = `Tp ${waves.peak_period_s}s da ${waves.direction_cardinal} • ${waves.douglas.label}`;
  }

  const hudRain = document.getElementById("hud-val-rain");
  const hudSubRain = document.getElementById("hud-sub-rain");
  if (hudRain) {
    hudRain.textContent = `${landRisk.hydrogeological.precip_1h_mm} mm/h`;
    hudSubRain.textContent = `Risacca riva: ${coastal.bay_surge.shore_breaker_height_m}m • Marea ${coastal.tides.current_height_cm}cm`;
  }

  const hudPress = document.getElementById("hud-val-press");
  if (hudPress) {
    hudPress.textContent = `${cur.pressure_hpa} hPa`;
  }

  const convLevel =
    conv.convergence_score >= 65
      ? "red"
      : conv.convergence_score >= 35
      ? "yellow"
      : "green";
  setBadgeLevel(
    document.getElementById("badge-convergence"),
    convLevel,
    `Conv: ${conv.convergence_score}/100`
  );

  const confLevel =
    cur.confidence_pct >= 80 ? "green" : cur.confidence_pct >= 65 ? "yellow" : "orange";
  setBadgeLevel(
    document.getElementById("badge-confidence"),
    confLevel,
    `5 Mod: ${cur.confidence_pct}%`
  );

  const genDate = new Date(pkg.generated_at);
  document.getElementById("timestamp-badge").textContent = genDate.toLocaleTimeString(
    "it-IT",
    { hour: "2-digit", minute: "2-digit" }
  );

  // 2. Tab 1: Riepilogo + Quadrante SVG + Stazioni OMIRL + Idrometri + Webcam
  document.getElementById("main-weather-desc").textContent = cur.weather_description;
  document.getElementById("main-temp").textContent = `${cur.temp_c.toFixed(1)}°C`;

  if (state.mode === "sea") {
    document.getElementById(
      "main-wind-summary"
    ).textContent = `${wind.ligurian_name} (${wind.cardinal} ${wind.direction_deg}°) ${wind.speed_knots} kt (${wind.speed_ms} m/s) • Raffica ${wind.gust_knots} kt (F${wind.beaufort.force} Beaufort)`;
  } else {
    document.getElementById(
      "main-wind-summary"
    ).textContent = `${cur.wind_ligurian_name} (${cur.wind_cardinal} ${cur.wind_dir_deg}°) ${cur.wind_kmh} km/h (${wind.speed_knots} kt) • Raffica ${cur.gust_kmh} km/h`;
  }

  document.getElementById("pressure-value").textContent = `${cur.pressure_hpa} hPa`;
  document.getElementById("pressure-trend").textContent = cur.pressure_trend_label;
  document.getElementById(
    "wind-local-note"
  ).innerHTML = `🧭 <strong>Rosa dei Venti Ligure (${wind.ligurian_name} - ${wind.cardinal}):</strong> ${wind.local_note}`;

  document.getElementById(
    "map-coords-label"
  ).textContent = `📍 ${pkg.coordinates.lat.toFixed(4)}°N, ${pkg.coordinates.lon.toFixed(4)}°E`;

  renderDynamicKPIs(cur, landRisk, seaCond);
  renderNauticalCompassSVG(cur, seaCond, loc);
  renderOmirlObservationsAndWebcams(pkg.observations_live, cur, seaCond);
  renderNowcast15mStrip(pkg.nowcast.timeline_15m);
  renderLandAndSeaPanels(landRisk, seaCond, conv);
  render5ModelsHourlyTable(pkg.forecast.hourly_48h);
  renderCharts(pkg.forecast.hourly_48h);
  render7DayTable(pkg.forecast.daily_7d);
  renderAIBulletinAndOfficialArpal(state.aiBulletin, pkg.official_bulletins?.arpal);

  document.getElementById("meteomar-text").textContent = pkg.alerts.meteomar.bulletin;
  document.getElementById("disclaimer-land-text").textContent = pkg.land.safety_disclaimer;
  document.getElementById("disclaimer-sea-text").textContent = pkg.sea.safety_disclaimer;
}

/* ==========================================================================
   QUADRANTE GRAFICO SVG: Rosa dei Venti Ligure + Vettore Swell + Cono Cala
   ========================================================================== */
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

function renderNauticalCompassSVG(cur, seaCond, loc) {
  const container = document.getElementById("svg-nautical-compass");
  const legendEl = document.getElementById("compass-legend");
  const badgeEl = document.getElementById("compass-bay-badge");
  if (!container || !seaCond) return;

  const wind = seaCond.wind;
  const waves = seaCond.waves;
  const baySurge = seaCond.coastal_physics.bay_surge;
  const bayAxis = loc.bay_open_deg ?? baySurge.bay_open_axis_deg ?? 195;

  if (badgeEl) {
    badgeEl.textContent = `CALA APERTA A ${bayAxis}° • RISACCA ${baySurge.shore_breaker_height_m}m`;
  }

  const cx = 130;
  const cy = 130;
  const rOuter = 96;

  // Cono apertura cala (+/- 38 gradi intorno a bayAxis)
  const conePath = describeSectorPath(cx, cy, rOuter, bayAxis - 38, bayAxis + 38);

  // Vettore Vento (provenienza = wind.direction_deg)
  const windFrom = polarToCartesian(cx, cy, rOuter - 6, wind.direction_deg);
  const windTo = polarToCartesian(cx, cy, 18, wind.direction_deg);

  // Vettore Swell Primario (provenienza = waves.swell_dir_deg)
  const swellDeg = waves.swell_dir_deg ?? waves.direction_deg ?? 210;
  const swellFrom = polarToCartesian(cx, cy, rOuter - 12, swellDeg);
  const swellTo = polarToCartesian(cx, cy, 24, swellDeg);

  const cardinals = [
    { deg: 0, lbl: "N", name: "Tramontana" },
    { deg: 45, lbl: "NE", name: "Grecale" },
    { deg: 90, lbl: "E", name: "Levante" },
    { deg: 135, lbl: "SE", name: "Scirocco" },
    { deg: 180, lbl: "S", name: "Ostro" },
    { deg: 225, lbl: "SW", name: "Libeccio" },
    { deg: 270, lbl: "W", name: "Ponente" },
    { deg: 315, lbl: "NW", name: "Maestrale" },
  ];

  const labelsSvg = cardinals
    .map((c) => {
      const p = polarToCartesian(cx, cy, rOuter + 18, c.deg);
      const isMain = c.deg % 90 === 0;
      return `
        <text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}"
          text-anchor="middle" dominant-baseline="middle"
          fill="${isMain ? "#f8fafc" : "#94a3b8"}"
          font-size="${isMain ? "11" : "9"}"
          font-weight="${isMain ? "800" : "600"}">
          ${c.lbl}
        </text>
      `;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 260 260" width="235" height="235" role="img" aria-label="Quadrante Nautico Rosa dei Venti Ligure e Vettori Vento/Onda">
      <defs>
        <marker id="arrow-wind" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#10b981" />
        </marker>
        <marker id="arrow-swell" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#38bdf8" />
        </marker>
      </defs>

      <!-- Cerchi Concentrici Strumentali -->
      <circle cx="${cx}" cy="${cy}" r="${rOuter}" fill="rgba(4,12,24,0.85)" stroke="rgba(148,163,184,0.28)" stroke-width="1.5" />
      <circle cx="${cx}" cy="${cy}" r="66" fill="none" stroke="rgba(148,163,184,0.14)" stroke-dasharray="3,3" />
      <circle cx="${cx}" cy="${cy}" r="34" fill="none" stroke="rgba(148,163,184,0.14)" />

      <!-- Cono di Esposizione Costiera della Rada/Cala (bay_open_deg) -->
      <path d="${conePath}" fill="rgba(245, 158, 11, 0.16)" stroke="rgba(245, 158, 11, 0.55)" stroke-width="1.2" />

      <!-- Assi Cardinali -->
      <line x1="${cx}" y1="${cy - rOuter}" x2="${cx}" y2="${cy + rOuter}" stroke="rgba(148,163,184,0.18)" />
      <line x1="${cx - rOuter}" y1="${cy}" x2="${cx + rOuter}" y2="${cy}" stroke="rgba(148,163,184,0.18)" />

      <!-- Vettore Swell / Onda (Azzurro) -->
      <line x1="${swellFrom.x.toFixed(1)}" y1="${swellFrom.y.toFixed(1)}"
            x2="${swellTo.x.toFixed(1)}" y2="${swellTo.y.toFixed(1)}"
            stroke="#38bdf8" stroke-width="3.2" stroke-dasharray="5,3" marker-end="url(#arrow-swell)" />

      <!-- Vettore Vento Reale (Verde Smeraldo) -->
      <line x1="${windFrom.x.toFixed(1)}" y1="${windFrom.y.toFixed(1)}"
            x2="${windTo.x.toFixed(1)}" y2="${windTo.y.toFixed(1)}"
            stroke="#10b981" stroke-width="3.8" marker-end="url(#arrow-wind)" />

      <!-- Punto Centrale Località -->
      <circle cx="${cx}" cy="${cy}" r="6" fill="#f59e0b" stroke="#fff" stroke-width="1.5" />

      <!-- Etichette Rosa dei Venti -->
      ${labelsSvg}
    </svg>
  `;

  if (legendEl) {
    legendEl.innerHTML = `
      <span style="color:#10b981;font-weight:700;">━━➤ Vento ${wind.ligurian_name} (${wind.speed_knots} kt da ${wind.direction_deg}°)</span> &nbsp;•&nbsp;
      <span style="color:#38bdf8;font-weight:700;">┅┅➤ Swell (${waves.swell_height_m}m @ ${waves.swell_period_s}s da ${swellDeg}°)</span> &nbsp;•&nbsp;
      <span style="color:#fbbf24;font-weight:700;">◪ Cono Cala (${bayAxis}°)</span>
    `;
  }
}

function renderDynamicKPIs(cur, landRisk, seaCond) {
  const grid = document.getElementById("kpi-dynamic-grid");
  const hydro = landRisk.hydrogeological;
  const thermo = landRisk.thermo_comfort || {};
  const waves = seaCond.waves;
  const wind = seaCond.wind;
  const coastal = seaCond.coastal_physics;

  const cards =
    state.mode === "sea"
      ? [
          {
            label: "Vento & Raffica (kt | m/s | km/h)",
            value: `${wind.speed_knots} / ${wind.gust_knots} kt`,
            sub: `${wind.speed_ms}/${wind.gust_ms} m/s • F${wind.beaufort.force} ${wind.beaufort.label}`,
          },
          {
            label: "Spettro Onda Hs / Hmax / H1000",
            value: `${waves.significant_height_m} / ${waves.max_height_m} m`,
            sub: `Picco 1/1000: ${waves.extreme_height_1_1000_m}m • ${waves.douglas.label}`,
          },
          {
            label: "Periodo Tp, Lunghezza L & Ripidità",
            value: `${waves.peak_period_s} s (L=${waves.wavelength_m}m)`,
            sub: `Ripidità H/L: ${waves.steepness_pct}% da ${waves.direction_cardinal}`,
          },
          {
            label: "Onda Vento vs Swell Lungo",
            value: `${waves.wind_wave_height_m}m / ${waves.swell_height_m}m`,
            sub: `Vento ${waves.wind_wave_cardinal} (${waves.wind_wave_period_s}s) • Swell ${waves.swell_cardinal} (${waves.swell_period_s}s)`,
          },
          {
            label: "Risacca in Rada & Marea",
            value: `Frangente ${coastal.bay_surge.shore_breaker_height_m} m`,
            sub: `Marea ${coastal.tides.current_height_cm} cm (${coastal.tides.current_phase})`,
          },
          {
            label: "Corrente, SST & Visibilità",
            value: `${coastal.surface_current.speed_knots} kt (${coastal.surface_current.direction_cardinal})`,
            sub: `Acqua ${waves.sea_surface_temp_c}°C • Visibilità ${coastal.visibility_nm} NM`,
          },
        ]
      : [
          {
            label: "Intensità Pioggia (1h / Picco LAM)",
            value: `${hydro.precip_1h_mm} mm/h`,
            sub: `Max AROME/ICON-D2: ${cur.precip_max_lam_mm} mm/h`,
          },
          {
            label: "Cumulata Pluviometrica 3h / 24h",
            value: `${hydro.precip_3h_mm} / ${hydro.precip_24h_mm} mm`,
            sub: hydro.label.split("—")[0],
          },
          {
            label: "Vento & Raffica (km/h | kt)",
            value: `${cur.wind_kmh} / ${cur.gust_kmh} km/h`,
            sub: `${wind.speed_knots} / ${wind.gust_knots} kt da ${cur.wind_cardinal} (${cur.wind_dir_deg}°)`,
          },
          {
            label: "Dew Point, Percepita & Maccaja",
            value: `DP ${thermo.dew_point_c ?? "--"}°C (Perc. ${thermo.perceived_temp_c ?? cur.temp_c}°C)`,
            sub: thermo.maccaja_status || `Umidità ${cur.humidity_pct}%`,
          },
          {
            label: "Zero Termico, UV & Radiazione",
            value: `ZT ${landRisk.appennino_passes.freezing_level_m} m`,
            sub: `UV ${thermo.uv_index ?? cur.uv_index} • Rad. ${thermo.solar_radiation_wm2 ?? cur.solar_radiation_wm2} W/m²`,
          },
          {
            label: "Fisica Mare Antistante",
            value: `Hs ${waves.significant_height_m}m (Hmax ${waves.max_height_m}m)`,
            sub: `Tp ${waves.peak_period_s}s da ${waves.direction_cardinal} • ${waves.douglas.label}`,
          },
        ];

  grid.innerHTML = cards
    .map(
      (c) => `
      <div class="kpi-box">
        <div class="kpi-label">${c.label}</div>
        <div class="kpi-value">${c.value}</div>
        <div class="kpi-sub">${c.sub}</div>
      </div>
    `
    )
    .join("");
}

window.inspectOmirlStationChart = async function inspectOmirlStationChart(code, sensor, btnEl) {
  if (!code) return;
  const originalText = btnEl.textContent;
  btnEl.textContent = "⏳ Caricamento serie OMIRL...";
  try {
    const res = await fetch(`/api/v1/omirl-chart?code=${encodeURIComponent(code)}&sensor=${encodeURIComponent(sensor)}`);
    const data = await res.json();
    if (data.available && data.recent_24_points?.length) {
      const pts = data.recent_24_points.slice(-8);
      const summary = pts.map((p) => `${p.timestamp.split(" ")[1] || p.timestamp}: ${p.value}`).join(" → ");
      btnEl.outerHTML = `<div style="margin-top:0.3rem;padding:0.35rem 0.5rem;background:rgba(56,189,248,0.1);border-radius:6px;font-size:0.71rem;color:#bae6fd;">
        📈 <strong>Ultime letture ${sensor} (${data.unit || ""}) [Min ${data.min_value} / Max ${data.max_value}]:</strong><br>${summary}
      </div>`;
    } else {
      btnEl.textContent = "Serie storica 24h non esposta per questo sensore";
    }
  } catch (e) {
    btnEl.textContent = originalText;
  }
};

function renderOmirlObservationsAndWebcams(obs, cur, seaCond) {
  if (!obs) return;

  // 1. Stazioni Meteo/Marine Reali OMIRL
  const stGrid = document.getElementById("omirl-stations-grid");
  const stations = obs.nearest_weather_stations || [];
  stGrid.innerHTML = stations
    .map((st) => {
      const liveBadge = st.is_live_rest
        ? `<span class="badge-pill level-green" style="font-size:0.62rem;padding:0.08rem 0.4rem;">LIVE REST OMIRL</span>`
        : `<span class="badge-pill level-physics" style="font-size:0.62rem;padding:0.08rem 0.4rem;">SINOTTICA</span>`;
      const defaultSensor = st.has_live_wind ? "Vento" : st.has_live_temp ? "Termo" : "Pluvio";
      return `
        <div class="station-card">
          <div class="station-header">
            <div class="station-name">📡 ${st.name} <span style="color:var(--text-muted);font-size:0.72rem;">(${st.code})</span></div>
            <div style="display:flex;gap:0.35rem;align-items:center;">
              ${liveBadge}
              <span class="station-dist">📍 ${st.distance_km} km</span>
            </div>
          </div>
          <div style="font-size:0.73rem;color:var(--text-muted);">${st.muni} • Quota ${st.elev_m} m • Rilevato ore ${st.observed_at}</div>
          <div style="display:flex;justify-content:space-between;margin-top:0.2rem;font-size:0.83rem;flex-wrap:wrap;gap:0.4rem;">
            <span>🌡️ <strong>${st.temp_c}°C</strong></span>
            <span>🌧️ <strong>${st.precip_1h_mm} mm</strong></span>
            <span>💨 <strong>${st.wind_knots} kt</strong> (${st.wind_kmh} km/h da ${st.wind_dir_deg ?? 0}°) • Max <strong>${st.gust_knots} kt</strong></span>
          </div>
          <div>
            <button type="button" class="btn-action" style="font-size:0.69rem;padding:0.18rem 0.5rem;margin-top:0.2rem;"
              onclick="window.inspectOmirlStationChart('${st.code}', '${defaultSensor}', this)">
              📈 Ispetta Curva 24h OMIRL (${defaultSensor})
            </button>
          </div>
        </div>
      `;
    })
    .join("");

  // 2. Idrometri Torrenti Reali OMIRL con Barra Graduata Visiva
  const hyGrid = document.getElementById("omirl-hydrometers-grid");
  const hydros = obs.nearest_river_hydrometers || [];
  hyGrid.innerHTML = hydros
    .map((hy) => {
      const pillClass = `level-${hy.status_level || "green"}`;
      const maxScale = Math.max(hy.alarm_threshold_m * 1.25, hy.level_m * 1.2, 2.5);
      const fillPct = Math.max(4, Math.min(100, Math.round((Math.max(0, hy.level_m) / maxScale) * 100)));
      const warnPct = Math.min(96, Math.round((hy.warn_threshold_m / maxScale) * 100));
      const alarmPct = Math.min(98, Math.round((hy.alarm_threshold_m / maxScale) * 100));
      const barColor =
        hy.status_level === "red"
          ? "#ef4444"
          : hy.status_level === "orange"
          ? "#f97316"
          : "#10b981";

      return `
        <div class="station-card">
          <div class="station-header">
            <div class="station-name">🌊 ${hy.name} <span style="color:var(--text-muted);font-size:0.72rem;">(${hy.code})</span></div>
            <span class="station-dist">📍 ${hy.distance_km} km</span>
          </div>
          <div style="font-size:0.73rem;color:var(--text-muted);">Bacino: <strong>${hy.river}</strong> (${hy.municipality || "GE"}) • Ore ${hy.observed_at}</div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-top:0.15rem;">
            <span style="font-size:1.1rem;font-weight:900;color:#fff;">Livello: ${hy.level_m} m</span>
            <span class="badge-pill ${pillClass}">${hy.status_level === "green" ? "REGOLARE" : "GUARDIA IDRO"}</span>
          </div>
          <!-- Barra Graduata Idrometrica con Tacche Soglia Gialla e Rossa -->
          <div class="hydro-gauge-track" title="Livello ${hy.level_m}m su scala ${maxScale.toFixed(1)}m">
            <div class="hydro-gauge-fill" style="width:${fillPct}%;background:${barColor};"></div>
            <div class="hydro-threshold-mark" style="left:${warnPct}%;background:#fbbf24;" title="Soglia Gialla: ${hy.warn_threshold_m}m"></div>
            <div class="hydro-threshold-mark" style="left:${alarmPct}%;background:#ef4444;" title="Soglia Rossa: ${hy.alarm_threshold_m}m"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-muted);">
            <span>0.0 m</span>
            <span style="color:#fbbf24;">⚠️ Gialla ${hy.warn_threshold_m} m</span>
            <span style="color:#f87171;">🚨 Rossa ${hy.alarm_threshold_m} m</span>
          </div>
        </div>
      `;
    })
    .join("");

  // 3. Galleria Webcam Live (Immagine JPEG Live OMIRL o Orizzonte Fisico SVG Mare/Cielo)
  const camGrid = document.getElementById("live-webcams-grid");
  const cams = obs.nearest_webcams || [];
  const hs = seaCond?.waves?.significant_height_m ?? 0.4;
  const windKt = seaCond?.wind?.speed_knots ?? 6;
  const waveAmp = Math.min(22, Math.max(4, Math.round(hs * 10)));

  camGrid.innerHTML = cams
    .map((cam) => {
      const previewStyle = cam.live_image_url
        ? `background: linear-gradient(180deg, rgba(4,12,24,0.15) 0%, rgba(4,12,24,0.88) 100%), url('${cam.live_image_url}') center/cover no-repeat;`
        : `background: linear-gradient(180deg, #0b2444 0%, #071932 58%, #041022 100%);`;
      const svgBackdrop = cam.live_image_url
        ? ""
        : `<svg viewBox="0 0 320 175" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%;opacity:0.45;pointer-events:none;">
            <path d="M0,${115 - waveAmp} Q80,${115 + waveAmp} 160,${115 - waveAmp} T320,${115 - waveAmp} L320,175 L0,175 Z" fill="#0284c7" />
            <path d="M0,${132 + waveAmp / 2} Q80,${132 - waveAmp} 160,${132 + waveAmp / 2} T320,${132 + waveAmp / 2} L320,175 L0,175 Z" fill="#0369a1" />
            <circle cx="265" cy="40" r="14" fill="rgba(56,189,248,0.28)" />
          </svg>`;
      return `
        <div class="webcam-card">
          <div class="webcam-preview" style="${previewStyle}">
            ${svgBackdrop}
            <div style="display:flex;justify-content:space-between;align-items:center;z-index:2;">
              <span class="badge-pill ${cam.live_image_url ? "level-green" : "level-physics"}">
                ${cam.live_image_url ? "📷 IMMAGINE LIVE OMIRL" : "📷 TELEMETRIA VISIVA & STREAM"}
              </span>
              <span style="font-size:0.74rem;font-weight:800;color:#38bdf8;background:rgba(4,12,24,0.75);padding:0.1rem 0.45rem;border-radius:999px;">
                📍 a ${cam.distance_km} km
              </span>
            </div>
            <div style="z-index:2;">
              <div style="font-size:0.92rem;font-weight:800;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.9);">${cam.name}</div>
              <div style="font-size:0.74rem;color:#cbd5e1;margin-top:0.1rem;">🔭 ${cam.view_direction}</div>
              <div style="font-size:0.7rem;color:#7dd3fc;margin-top:0.15rem;">
                Condizione inquadrata: ${cur?.temp_c?.toFixed(1) ?? "--"}°C • Vento ${windKt} kt • Onda Hs ${hs}m
              </div>
            </div>
          </div>
          <div class="webcam-body">
            <div style="display:flex;justify-content:space-between;color:var(--text-muted);font-size:0.72rem;">
              <span>Fonte: ${cam.provider}</span>
              <span>${cam.timestamp_label}</span>
            </div>
            <a href="${cam.live_image_url || cam.portal_url}" target="_blank" rel="noopener" class="btn-action" style="justify-content:center;margin-top:0.2rem;">
              👁️ Apri ${cam.live_image_url ? "Foto Reale HD / Portale" : "Stream Live Ufficiale"} ↗
            </a>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderNowcast15mStrip(timeline) {
  const strip = document.getElementById("nowcast-15m-strip");
  if (!timeline || !timeline.length) {
    strip.innerHTML = `<div class="nowcast-cell">Dati 15m non disponibili</div>`;
    return;
  }

  strip.innerHTML = timeline
    .map((step) => {
      const timeLabel = step.time.split("T")[1] || step.time;
      const windStr =
        state.mode === "sea"
          ? `${step.wind_knots}/${step.gust_knots} kt ${step.wind_cardinal}`
          : `${step.wind_kmh.toFixed(0)} km/h ${step.wind_cardinal}`;
      return `
        <div class="nowcast-cell">
          <div class="nowcast-time">${timeLabel}</div>
          <div class="nowcast-temp">${step.temp_c.toFixed(1)}°C</div>
          <div class="nowcast-meta" style="color: ${
            step.rain_rate_mm_h > 0.2 ? "#38bdf8" : "var(--text-muted)"
          }; font-weight: 600;">
            🌧️ ${step.rain_rate_mm_h.toFixed(1)} mm/h
          </div>
          <div class="nowcast-meta">💨 ${windStr}</div>
        </div>
      `;
    })
    .join("");
}

function renderLandAndSeaPanels(landRisk, seaCond, conv) {
  setBadgeLevel(
    document.getElementById("land-overall-badge"),
    landRisk.overall_level,
    LEVEL_LABELS[landRisk.overall_level]
  );

  // Pannello TERRA: Fisica + Indicatori Operativi
  const landContainer = document.getElementById("land-risk-items");
  const thermo = landRisk.thermo_comfort || {};
  const convBorder =
    conv.convergence_score >= 65
      ? "red"
      : conv.convergence_score >= 35
      ? "yellow"
      : "green";

  landContainer.innerHTML = `
    <div class="risk-item border-${landRisk.hydrogeological.level}">
      <div class="risk-item-title">
        <span>🌊 Bacini Idrografici & Sottopassi (Bisagno, Polcevera, Entella, Stura)</span>
        <span>${landRisk.hydrogeological.precip_1h_mm} mm/h</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.hydrogeological.label}:</strong> ${landRisk.hydrogeological.advice}</div>
    </div>

    <div class="risk-item border-${convBorder}">
      <div class="risk-item-title">
        <span>⚡ Linea di Convergenza Ligure (Tramontana Scura vs Scirocco)</span>
        <span>Score ${conv.convergence_score}/100</span>
      </div>
      <div class="risk-item-desc"><strong>${conv.status}:</strong> ${conv.explanation}</div>
    </div>

    <div class="risk-item border-${landRisk.wind_viability.level}">
      <div class="risk-item-title">
        <span>🛵 Viabilità Urbana, Sopraelevata Aldo Moro & Viadotti A7/A10/A12/A26</span>
        <span>Raffica ${landRisk.wind_viability.gust_kmh} km/h</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.wind_viability.label}:</strong> ${landRisk.wind_viability.advice}</div>
    </div>

    <div class="risk-item border-${landRisk.appennino_passes.level}">
      <div class="risk-item-title">
        <span>🏔️ Valichi Appenninici (Giovi, Turchino, Scoffera, Bocco, Faiallo)</span>
        <span>ZT ~${landRisk.appennino_passes.freezing_level_m} m</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.appennino_passes.label}:</strong> ${landRisk.appennino_passes.advice}</div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>🌡️ Termo-Igrometria, Punto di Rugiada & Diagnostica Maccaja Ligure</span>
        <span>DP ${thermo.dew_point_c ?? "--"}°C | UV ${thermo.uv_index ?? "--"}</span>
      </div>
      <div class="risk-item-desc">
        Percepita: <strong>${thermo.perceived_temp_c ?? "--"}°C</strong> (${thermo.comfort_label || "Regolare"}) •
        Humidex: ${thermo.humidex ?? "--"} • Windchill: ${thermo.windchill_c ?? "--"}°C •
        Radiazione Solare: ${thermo.solar_radiation_wm2 ?? "--"} W/m² •
        <strong>${thermo.maccaja_status || ""}</strong>
      </div>
    </div>
  `;

  // Pannello MARE: SOLO Fisica Costiera & Oceanografica Pura (ZERO semafori soggettivi — ADR-0006)
  const seaContainer = document.getElementById("sea-risk-items");
  const w = seaCond.waves;
  const wind = seaCond.wind;
  const cp = seaCond.coastal_physics;
  const bs = cp.bay_surge;
  const td = cp.tides;
  const cur = cp.surface_current;

  const tideExtremaStr = (td.extrema || [])
    .slice(0, 4)
    .map((ex) => `${ex.type === "HIGH" ? "▲ Alta" : "▼ Bassa"} ${ex.time} (${ex.height_cm} cm)`)
    .join(" • ");

  seaContainer.innerHTML = `
    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>💨 Cinematica del Vento & Scala Beaufort</span>
        <span>${wind.speed_knots} kt (Raffica ${wind.gust_knots} kt)</span>
      </div>
      <div class="risk-item-desc">
        Direzione: <strong>${wind.cardinal} (${wind.direction_deg}° — ${wind.ligurian_name})</strong> •
        Velocità: <strong>${wind.speed_knots} kt</strong> | <strong>${wind.speed_ms} m/s</strong> | <strong>${wind.speed_kmh} km/h</strong> •
        Forza <strong>${wind.beaufort.force} Beaufort (${wind.beaufort.label})</strong>: <em>${wind.beaufort.sea_effect}</em>.
      </div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>🌊 Spettro Completo dell'Onda (Hs, Hmax, H1/1000, Periodo Tp & Ripidità)</span>
        <span>Hs ${w.significant_height_m} m | Hmax ${w.max_height_m} m</span>
      </div>
      <div class="risk-item-desc">
        <strong>${w.douglas.label}:</strong> Onda significativa Hs <strong>${w.significant_height_m} m</strong>,
        Onda massima statistica (Rayleigh) Hmax <strong>${w.max_height_m} m</strong>, Picco estremo H1/1000 <strong>${w.extreme_height_1_1000_m} m</strong>.<br>
        Periodo di picco Tp <strong>${w.peak_period_s} s</strong> da <strong>${w.direction_cardinal} (${w.direction_deg}°)</strong> •
        Lunghezza d'onda L = <strong>${w.wavelength_m} m</strong> • ${w.steepness_class}.
      </div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>🔀 Partizione Spettrale: Onda Viva da Vento vs Swell Lungo</span>
        <span>Hwind ${w.wind_wave_height_m} m | Hswell ${w.swell_height_m} m</span>
      </div>
      <div class="risk-item-desc">
        • <strong>Onda Viva da Vento Locale:</strong> ${w.wind_wave_height_m} m @ ${w.wind_wave_period_s} s da ${w.wind_wave_cardinal} (${w.wind_wave_dir_deg}°)<br>
        • <strong>Swell Primario (Mare Lungo):</strong> ${w.swell_height_m} m @ ${w.swell_period_s} s da ${w.swell_cardinal} (${w.swell_dir_deg}°)
      </div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>🏖️ Fisica Costiera di Rada: Rifrazione (Kr), Shoaling (Ks) & Risacca a Riva</span>
        <span>Frangente ${bs.shore_breaker_height_m} m</span>
      </div>
      <div class="risk-item-desc">
        Asse apertura cala: <strong>${bs.bay_open_axis_deg}°</strong> (angolo incidenza swell Δ=${bs.swell_incidence_diff_deg}° — <em>${bs.exposure_geometry}</em>).<br>
        Coeff. penetrazione Kr = <strong>${bs.refraction_kr}</strong> • Coeff. shoaling periodo Ks = <strong>${bs.shoaling_ks}</strong> •
        Altezza fisica frangente/risacca a riva = <strong>${bs.shore_breaker_height_m} m</strong>.
      </div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span>🌙 Curva di Marea, Corrente Superficiale & Visibilità Ottica</span>
        <span>${td.current_height_cm} cm (${td.current_phase})</span>
      </div>
      <div class="risk-item-desc">
        • <strong>Estremi di Marea:</strong> ${tideExtremaStr || "In calcolo"} (Escursione ${td.range_cm} cm)<br>
        • <strong>Corrente Superficiale:</strong> <strong>${cur.speed_knots} kt</strong> (${cur.speed_ms} m/s) verso ${cur.direction_cardinal} (drift vento ${cur.wind_drift_component_knots} kt)<br>
        • <strong>Temp. Acqua (SST):</strong> ${w.sea_surface_temp_c}°C • <strong>Visibilità Ottica:</strong> ${cp.visibility_nm} NM (${cp.visibility_m} m)
      </div>
    </div>
  `;
}

function render5ModelsHourlyTable(hourly48) {
  const tbody = document.getElementById("models-5-hourly-tbody");
  if (!tbody || !hourly48 || !hourly48.length) return;

  tbody.innerHTML = hourly48
    .slice(0, 24)
    .map((h) => {
      const tLabel = (h.time.split("T")[1] || h.time).slice(0, 5);
      const m = h.models || {};
      const fmtM = (key) => {
        const obj = m[key];
        if (!obj || obj.wind_knots === null || obj.wind_knots === undefined) return "--";
        return `<strong>${obj.wind_knots} kt</strong> <span style="color:var(--text-muted);font-size:0.72rem;">(r.${obj.gust_knots ?? "--"})</span>`;
      };
      const spreadKt = h.model_spread?.wind_spread_knots ?? 0;
      const spreadColor = spreadKt >= 8 ? "#f97316" : spreadKt >= 5 ? "#fbbf24" : "#34d399";

      return `
        <tr>
          <td><strong>${tLabel}</strong></td>
          <td><strong>${h.wind_knots} kt</strong> (${h.wind_kmh} km/h) ${h.wind_cardinal}</td>
          <td>${fmtM("meteofrance_arome_france_hd")}</td>
          <td>${fmtM("icon_d2")}</td>
          <td>${fmtM("ecmwf_ifs025")}</td>
          <td>${fmtM("gfs_seamless")}</td>
          <td>${fmtM("met_norway")}</td>
          <td style="color:${spreadColor};font-weight:700;">Δ ${spreadKt} kt</td>
          <td>${h.precip_mm} mm <span style="color:#38bdf8;font-size:0.72rem;">(max ${h.precip_max_lam_mm})</span></td>
          <td>Hs <strong>${h.wave_hs_m}m</strong> / Hmax ${h.wave_hmax_m}m @ ${h.wave_period_s}s</td>
          <td>${h.shore_breaker_m} m</td>
        </tr>
      `;
    })
    .join("");
}

async function calculateCoastalRoute() {
  const origin = document.getElementById("route-origin")?.value || "portofino";
  const dest = document.getElementById("route-dest")?.value || "san_fruttuoso";
  const speed = document.getElementById("route-speed")?.value || "6.0";
  const duration = document.getElementById("route-duration")?.value || "90";
  const stop = document.getElementById("route-stop")?.value || "20";

  const params = new URLSearchParams({
    origin,
    dest,
    cruise_knots: speed,
    duration_min: duration,
    stop_min: stop,
    round_trip: "true",
  });

  try {
    const res = await fetch(`/api/v1/route-eta?${params.toString()}`);
    if (!res.ok) return;
    const plan = await res.json();
    state.routePlan = plan;

    const kpiGrid = document.getElementById("route-results-grid");
    const cmp = plan.physical_comparison_outbound_vs_inbound || {};
    kpiGrid.innerHTML = `
      <div class="kpi-box">
        <div class="kpi-label">Distanza Costiera (Andata / A+R)</div>
        <div class="kpi-value">${plan.one_way_distance_nm} / ${plan.total_distance_nm} NM</div>
        <div class="kpi-sub">Rotta su grafo che non taglia i capi</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Tempo Navigazione Effettivo</div>
        <div class="kpi-value">${plan.estimated_navigation_minutes} min</div>
        <div class="kpi-sub">+ ${plan.planned_stop_minutes} min sosta = ${plan.estimated_total_minutes} min tot</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Velocità Media Richiesta</div>
        <div class="kpi-value">${plan.required_average_speed_knots} kt</div>
        <div class="kpi-sub">Per rientrare in ${plan.planned_duration_minutes} min totali</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Orario Limite Rientro (Turnaround)</div>
        <div class="kpi-value" style="color:#fbbf24;">${plan.schedule.latest_turnaround_time}</div>
        <div class="kpi-sub">ETA Dest: ${plan.schedule.eta_destination} • Rientro: ${plan.schedule.eta_return_origin}</div>
      </div>
    `;

    const legsList = document.getElementById("route-legs-list");
    const legsHtml = (plan.legs || [])
      .map(
        (leg, i) => `
        <div class="risk-item border-physics">
          <div class="risk-item-title">
            <span>Tratta ${i + 1}: ${leg.from_name} → ${leg.to_name}</span>
            <span>${leg.distance_nm} NM</span>
          </div>
          <div class="risk-item-desc">
            ${
              leg.amp_speed_limit_knots
                ? `⚠️ <strong>Vincolo Area Marina Protetta (AMP Portofino):</strong> velocità limitata a <strong>max ${leg.amp_speed_limit_knots} kt</strong>`
                : "Navigazione libera fuori dalle zone di riserva integrale/generale AMP."
            }
          </div>
        </div>
      `
      )
      .join("");

    legsList.innerHTML =
      `
      <div class="risk-item border-green">
        <div class="risk-item-title">
          <span>🔄 Confronto Fisico Andata vs Ritorno</span>
          <span>Partenza ${plan.schedule.departure_time}</span>
        </div>
        <div class="risk-item-desc">${cmp.delta_summary || ""}</div>
      </div>
    ` + legsHtml;

    if (state.map && plan.waypoints) {
      if (state.routePolyline) {
        state.map.removeLayer(state.routePolyline);
      }
      const latlngs = plan.waypoints.map((w) => [w.lat, w.lon]);
      state.routePolyline = L.polyline(latlngs, {
        color: "#38bdf8",
        weight: 4,
        dashArray: "6, 6",
      }).addTo(state.map);
    }
  } catch (e) {
    console.error("Errore calcolo rotta:", e);
  }
}

function renderAIBulletinAndOfficialArpal(bulletin, arpal) {
  if (bulletin) {
    const badge = document.getElementById("ai-engine-badge");
    badge.textContent = bulletin.ai_powered
      ? "✨ Google Gemini Analista Sinottico"
      : "🧠 Motore Sinottico Fisico Ligure";

    document.getElementById("ai-headline").textContent = bulletin.headline;
    document.getElementById("ai-synoptic-body").textContent =
      bulletin.synoptic_nowcast_analysis +
      "\n\n" +
      (bulletin.sea_operational_briefing || "");

    const takeawaysGrid = document.getElementById("ai-takeaways-grid");
    takeawaysGrid.innerHTML = (bulletin.key_takeaways || [])
      .map((item) => `<div class="ai-takeaway-item">🔹 ${item}</div>`)
      .join("");
  }

  const arpalBox = document.getElementById("arpal-bulletin-box");
  const arpalBadge = document.getElementById("arpal-issued-badge");
  if (!arpalBox || !arpal) return;

  if (arpalBadge) {
    arpalBadge.textContent = arpal.live_extracted ? "ARPAL LIVE" : "ARPAL SINTESI";
  }

  const daysHtml = (arpal.days || [])
    .map(
      (d) => `
      <div class="risk-item border-physics">
        <div class="risk-item-title">
          <span>📅 ${d.label}</span>
          <span>Zonizzazione Liguria</span>
        </div>
        <div class="risk-item-desc">
          <strong>Meteo:</strong> ${d.forecast_text}<br>
          <strong>Venti:</strong> ${d.winds}<br>
          <strong>Mare:</strong> ${d.sea}
        </div>
      </div>
    `
    )
    .join("");

  arpalBox.innerHTML =
    `
    <div class="risk-item border-green">
      <div class="risk-item-title">
        <span>Situazione Sinottica Regionale (${arpal.source || "ARPAL"})</span>
        <span>${arpal.issued_at || ""}</span>
      </div>
      <div class="risk-item-desc">${arpal.synoptic_situation || ""}</div>
    </div>
  ` + daysHtml;
}

function renderCharts(hourly48) {
  if (typeof Chart === "undefined" || !hourly48 || !hourly48.length) return;

  const slice24 = hourly48.slice(0, 24);
  const labels = slice24.map((h) => (h.time.split("T")[1] || h.time).slice(0, 5));

  const aromeRain = slice24.map(
    (h) => h.models?.meteofrance_arome_france_hd?.precip_mm ?? h.precip_mm
  );
  const iconRain = slice24.map((h) => h.models?.icon_d2?.precip_mm ?? h.precip_mm);
  const ecmwfRain = slice24.map((h) => h.models?.ecmwf_ifs025?.precip_mm ?? h.precip_mm);
  const consensusTemp = slice24.map((h) => h.temp_c);

  const canvas1 = document.getElementById("chart-multimodel");
  if (!canvas1) return;
  const ctx1 = canvas1.getContext("2d");
  if (state.chartMultiModel) state.chartMultiModel.destroy();

  state.chartMultiModel = new Chart(ctx1, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "Temp Consenso (°C)",
          data: consensusTemp,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.15)",
          yAxisID: "yTemp",
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 2,
        },
        {
          label: "AROME 1.3km Pioggia (mm/h)",
          data: aromeRain,
          backgroundColor: "rgba(56, 189, 248, 0.8)",
          yAxisID: "yRain",
        },
        {
          label: "ICON-D2 2km Pioggia (mm/h)",
          data: iconRain,
          backgroundColor: "rgba(16, 185, 129, 0.75)",
          yAxisID: "yRain",
        },
        {
          label: "ECMWF 9km Pioggia (mm/h)",
          data: ecmwfRain,
          backgroundColor: "rgba(14, 165, 233, 0.7)",
          yAxisID: "yRain",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1", font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.08)" } },
        yRain: {
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "mm/h", color: "#38bdf8" },
          ticks: { color: "#38bdf8" },
          grid: { color: "rgba(148,163,184,0.1)" },
        },
        yTemp: {
          position: "right",
          title: { display: true, text: "°C", color: "#f59e0b" },
          ticks: { color: "#f59e0b" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });

  const useKnots = state.mode === "sea";
  const windSeries = slice24.map((h) => (useKnots ? h.wind_knots : h.wind_kmh));
  const gustSeries = slice24.map((h) => (useKnots ? h.gust_knots : h.gust_kmh));
  const waveHsSeries = slice24.map((h) => h.wave_hs_m);
  const waveHmaxSeries = slice24.map((h) => h.wave_hmax_m);

  const canvas2 = document.getElementById("chart-wind-wave");
  if (!canvas2) return;
  const ctx2 = canvas2.getContext("2d");
  if (state.chartWindWave) state.chartWindWave.destroy();

  state.chartWindWave = new Chart(ctx2, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: useKnots ? "Vento Medio (kt)" : "Vento Medio (km/h)",
          data: windSeries,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          yAxisID: "yWind",
          tension: 0.3,
          borderWidth: 2,
        },
        {
          label: useKnots ? "Raffiche (kt)" : "Raffiche (km/h)",
          data: gustSeries,
          borderColor: "#ef4444",
          borderDash: [4, 4],
          yAxisID: "yWind",
          tension: 0.3,
          borderWidth: 2,
        },
        {
          label: "Onda Significativa Hs (m)",
          data: waveHsSeries,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.2)",
          fill: true,
          yAxisID: "yWave",
          tension: 0.35,
          borderWidth: 2.5,
        },
        {
          label: "Onda Max Statistica Hmax (m)",
          data: waveHmaxSeries,
          borderColor: "#f59e0b",
          borderDash: [2, 2],
          yAxisID: "yWave",
          tension: 0.35,
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1", font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.08)" } },
        yWind: {
          position: "left",
          beginAtZero: true,
          title: {
            display: true,
            text: useKnots ? "Nodi (kt)" : "km/h",
            color: "#10b981",
          },
          ticks: { color: "#10b981" },
          grid: { color: "rgba(148,163,184,0.1)" },
        },
        yWave: {
          position: "right",
          beginAtZero: true,
          title: { display: true, text: "Onda (m)", color: "#38bdf8" },
          ticks: { color: "#38bdf8" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

function render7DayTable(days) {
  const tbody = document.getElementById("daily-7d-tbody");
  if (!tbody || !days || !days.length) return;

  tbody.innerHTML = days
    .map((d) => {
      const dt = new Date(d.date);
      const dayLabel = dt.toLocaleDateString("it-IT", {
        weekday: "short",
        day: "2-digit",
        month: "short",
      });
      return `
        <tr>
          <td><strong>${dayLabel}</strong></td>
          <td>${d.weather_description}</td>
          <td><span style="color:#94a3b8">${d.temp_min_c}°</span> / <strong>${d.temp_max_c}°C</strong></td>
          <td><strong>${d.precip_sum_mm} mm</strong> <span style="font-size:0.75rem;color:#38bdf8">(LAM max ${d.precip_max_model_mm} mm)</span></td>
          <td>${d.wind_dominant_name} (${d.wind_dominant_cardinal})</td>
          <td>${d.gust_max_kmh} km/h | <strong>${d.gust_max_knots} kt</strong> (F${d.beaufort_max})</td>
          <td><strong>Hs ${d.wave_max_hs_m}m</strong> (Hmax ${d.wave_max_hmax_m}m) @ ${d.wave_period_max_s}s — <em>${d.douglas_max_label}</em></td>
        </tr>
      `;
    })
    .join("");
}

document.addEventListener("DOMContentLoaded", initApp);
