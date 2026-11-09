/* ==========================================================================
   MedioMeteo Genova — Client Application (ADR-0004)
   Gestisce:
   - Switch Dual-Mode TERRA / MARE
   - Mappa Leaflet interattiva con marker dei 10 distretti + click libero + Radar RainViewer
   - Grafici multi-modello Chart.js (AROME 1.3km vs ICON-D2 2km vs ECMWF + Vento/Onde)
   - Bollettino AI Advisor & Diagnostica Convergenza Ligure
   ========================================================================== */

const state = {
  mode: "land", // 'land' | 'sea'
  selectedDistrictId: "GE-CENTRO-PONENTE",
  customCoords: null, // { lat, lon } se l'utente clicca un punto libero sulla mappa
  districts: [],
  weatherPkg: null,
  aiBulletin: null,
  map: null,
  radarLayer: null,
  radarVisible: true,
  customMarker: null,
  districtMarkers: {},
  chartMultiModel: null,
  chartWindWave: null,
};

const LEVEL_LABELS = {
  green: "REGOLARE / FAVOREVOLE",
  yellow: "ATTENZIONE / CAUTELA",
  orange: "CRITICITÀ MODERATA-ALTA",
  red: "ALLERTA / CONDIZIONI CRITICHE",
};

function setBadgeLevel(el, level, text) {
  if (!el) return;
  el.className = `badge-pill level-${level || "green"}`;
  el.textContent = text;
}

async function initApp() {
  bindUIEvents();
  await loadDistricts();
  initLeafletMap();
  await refreshAllData(false);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

function bindUIEvents() {
  const btnLand = document.getElementById("btn-mode-land");
  const btnSea = document.getElementById("btn-mode-sea");
  const selectDistrict = document.getElementById("district-select");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnRadar = document.getElementById("btn-toggle-radar");

  btnLand.addEventListener("click", () => switchMode("land"));
  btnSea.addEventListener("click", () => switchMode("sea"));

  selectDistrict.addEventListener("change", async (e) => {
    state.selectedDistrictId = e.target.value;
    state.customCoords = null;
    if (state.customMarker && state.map) {
      state.map.removeLayer(state.customMarker);
      state.customMarker = null;
    }
    const found = state.districts.find((d) => d.id === state.selectedDistrictId);
    if (found) {
      state.mode = found.category;
      updateModeButtonsUI();
      if (state.map) {
        state.map.flyTo([found.lat, found.lon], found.category === "sea" ? 11 : 12, {
          duration: 0.7,
        });
      }
    }
    await refreshAllData(false);
  });

  btnRefresh.addEventListener("click", async () => {
    await refreshAllData(true);
  });

  btnRadar.addEventListener("click", () => {
    state.radarVisible = !state.radarVisible;
    updateRadarLayer();
  });
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

  // Se non siamo su un pin personalizzato e il distretto corrente appartiene all'altra categoria,
  // passa al distretto principale della modalità scelta
  const currentDist = state.districts.find((d) => d.id === state.selectedDistrictId);
  if (currentDist && currentDist.category !== targetMode && !state.customCoords) {
    state.selectedDistrictId =
      targetMode === "sea" ? "MARE-PORTO-DIGA" : "GE-CENTRO-PONENTE";
    document.getElementById("district-select").value = state.selectedDistrictId;
    const nextDist = state.districts.find((d) => d.id === state.selectedDistrictId);
    if (nextDist && state.map) {
      state.map.flyTo([nextDist.lat, nextDist.lon], 11, { duration: 0.6 });
    }
    await refreshAllData(false);
  } else if (state.weatherPkg) {
    renderDashboard();
  }
}

async function loadDistricts() {
  const res = await fetch("/api/v1/districts");
  const data = await res.json();
  state.districts = data.districts || [];

  const select = document.getElementById("district-select");
  select.innerHTML = "";

  const groupLand = document.createElement("optgroup");
  groupLand.label = "🏔️ DISTRETTI TERRA (Provincia di Genova)";
  const groupSea = document.createElement("optgroup");
  groupSea.label = "🌊 SETTORI MARE (Golfo di Genova & Largo)";

  state.districts.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = `${d.category === "sea" ? "⚓" : "📍"} ${d.name}`;
    if (d.category === "sea") {
      groupSea.appendChild(opt);
    } else {
      groupLand.appendChild(opt);
    }
  });

  select.appendChild(groupLand);
  select.appendChild(groupSea);
  select.value = state.selectedDistrictId;
}

function initLeafletMap() {
  if (typeof L === "undefined") return;

  state.map = L.map("genova-map", {
    center: [44.38, 8.98],
    zoom: 10,
    zoomControl: true,
  });

  // Base CartoDB Dark Matter ad alto contrasto per lettura radar meteo e nautica
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OpenStreetMap &copy; CARTO | MedioMeteo Genova',
    maxZoom: 18,
  }).addTo(state.map);

  // Aggiungi marker per tutti i 10 distretti Terra e Mare
  state.districts.forEach((d) => {
    const isSea = d.category === "sea";
    const markerHtml = `
      <div style="
        background: ${isSea ? "#0284c7" : "#059669"};
        color: #fff;
        border: 2px solid #fff;
        border-radius: 999px;
        width: 28px;
        height: 28px;
        display: grid;
        place-items: center;
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.6);
      ">${isSea ? "⚓" : "🏔️"}</div>
    `;
    const icon = L.divIcon({
      html: markerHtml,
      className: "",
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });

    const marker = L.marker([d.lat, d.lon], { icon }).addTo(state.map);
    marker.bindTooltip(`<strong>${d.short_name}</strong><br>${d.arpal_zone}`);
    marker.on("click", async () => {
      state.selectedDistrictId = d.id;
      state.customCoords = null;
      state.mode = d.category;
      document.getElementById("district-select").value = d.id;
      updateModeButtonsUI();
      await refreshAllData(false);
    });
    state.districtMarkers[d.id] = marker;
  });

  // Click su qualsiasi punto in Terra o Mare nel Golfo di Genova
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
      fillOpacity: 0.9,
    })
      .addTo(state.map)
      .bindPopup(`Punto selezionato:<br><strong>${lat}, ${lon}</strong>`)
      .openPopup();

    await refreshAllData(false);
  });
}

function updateRadarLayer() {
  if (!state.map || !state.weatherPkg) return;
  const radar = state.weatherPkg.nowcast?.radar;
  const latestTileUrl = radar?.latest_tile_url;

  if (state.radarLayer) {
    state.map.removeLayer(state.radarLayer);
    state.radarLayer = null;
  }

  const labelEl = document.getElementById("radar-time-label");
  if (!state.radarVisible) {
    labelEl.textContent = "Radar RainViewer: Nascosto";
    return;
  }

  if (latestTileUrl) {
    state.radarLayer = L.tileLayer(latestTileUrl, {
      opacity: 0.62,
      zIndex: 450,
    }).addTo(state.map);
    const frames = radar.frames || [];
    const lastFrame = frames[frames.length - 1];
    labelEl.textContent = lastFrame
      ? `Radar Precipitazioni: ${lastFrame.time_label} (${lastFrame.is_nowcast ? "Nowcast" : "Live"})`
      : "Radar Precipitazioni: Attivo";
  } else {
    labelEl.textContent = "Radar Precipitazioni: In aggiornamento";
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
    params.set("district", state.selectedDistrictId);
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

    renderDashboard();
    updateRadarLayer();
  } catch (e) {
    console.error("Errore caricamento dati MedioMeteo:", e);
  }
}

function renderDashboard() {
  const pkg = state.weatherPkg;
  if (!pkg) return;

  const d = pkg.district;
  const cur = pkg.nowcast.current;
  const conv = pkg.nowcast.ligurian_convergence;
  const landRisk = pkg.land.risk_assessment;
  const seaCond = pkg.sea.marine_conditions;

  // 1. Header Banner
  const pinSuffix = pkg.coordinates.is_custom_pin
    ? ` (Pin Mappa: ${pkg.coordinates.lat.toFixed(3)}, ${pkg.coordinates.lon.toFixed(3)})`
    : "";
  document.getElementById("banner-district-name").textContent = `${d.name}${pinSuffix}`;
  setBadgeLevel(
    document.getElementById("banner-zone-tag"),
    state.mode === "sea" ? seaCond.overall_level : landRisk.overall_level,
    d.arpal_zone
  );
  document.getElementById("banner-microclimate").textContent = d.microclimate_notes;

  const convLevel =
    conv.convergence_score >= 65
      ? "red"
      : conv.convergence_score >= 35
      ? "yellow"
      : "green";
  setBadgeLevel(
    document.getElementById("badge-convergence"),
    convLevel,
    `Convergenza Ligure: ${conv.convergence_score}/100`
  );

  const confLevel =
    cur.confidence_pct >= 80 ? "green" : cur.confidence_pct >= 65 ? "yellow" : "orange";
  setBadgeLevel(
    document.getElementById("badge-confidence"),
    confLevel,
    `Accordo Modelli LAM: ${cur.confidence_pct}%`
  );

  // 2. Hero Card principale
  const genDate = new Date(pkg.generated_at);
  document.getElementById("timestamp-badge").textContent = `Aggiornato ${genDate.toLocaleTimeString(
    "it-IT",
    { hour: "2-digit", minute: "2-digit" }
  )} (${pkg.sources.active.length} modelli attivi)`;

  document.getElementById("main-weather-desc").textContent = cur.weather_description;
  document.getElementById("main-temp").textContent = `${cur.temp_c.toFixed(1)}°C`;

  if (state.mode === "sea") {
    document.getElementById(
      "main-wind-summary"
    ).textContent = `${seaCond.wind.ligurian_name} (${seaCond.wind.cardinal}) ${seaCond.wind.speed_knots} kt • Raffica ${seaCond.wind.gust_knots} kt (F${seaCond.wind.beaufort.force} Beaufort)`;
  } else {
    document.getElementById(
      "main-wind-summary"
    ).textContent = `${cur.wind_ligurian_name} (${cur.wind_cardinal}) ${cur.wind_kmh} km/h • Raffica ${cur.gust_kmh} km/h`;
  }

  document.getElementById("pressure-value").textContent = `${cur.pressure_hpa} hPa`;
  document.getElementById("pressure-trend").textContent = cur.pressure_trend_label;
  document.getElementById(
    "wind-local-note"
  ).innerHTML = `🧭 <strong>Rosa dei Venti Ligure (${seaCond.wind.ligurian_name} - ${seaCond.wind.cardinal}):</strong> ${seaCond.wind.local_note}`;

  document.getElementById(
    "map-coords-label"
  ).textContent = `📍 Coordinate attive: ${pkg.coordinates.lat.toFixed(4)}°N, ${pkg.coordinates.lon.toFixed(4)}°E`;

  renderDynamicKPIs(cur, landRisk, seaCond);
  renderNowcast15mStrip(pkg.nowcast.timeline_15m);
  renderLandAndSeaPanels(landRisk, seaCond, conv);
  renderAIBulletin(state.aiBulletin);
  renderCharts(pkg.forecast.hourly_48h);
  render7DayTable(pkg.forecast.daily_7d);

  // Footer Meteomar & Disclaimers
  document.getElementById("meteomar-text").textContent = pkg.alerts.meteomar.bulletin;
  document.getElementById("disclaimer-land-text").textContent = pkg.land.safety_disclaimer;
  document.getElementById("disclaimer-sea-text").textContent = pkg.sea.safety_disclaimer;
}

function renderDynamicKPIs(cur, landRisk, seaCond) {
  const grid = document.getElementById("kpi-dynamic-grid");
  const hydro = landRisk.hydrogeological;
  const waves = seaCond.waves;
  const wind = seaCond.wind;

  const cards =
    state.mode === "sea"
      ? [
          {
            label: "Vento & Raffica (Nodi)",
            value: `${wind.speed_knots} / ${wind.gust_knots} kt`,
            sub: `Forza ${wind.beaufort.force} Beaufort (${wind.beaufort.label})`,
          },
          {
            label: "Onda Significativa / Max",
            value: `${waves.significant_height_m} / ${waves.max_height_m} m`,
            sub: `Mare ${waves.douglas.label}`,
          },
          {
            label: "Periodo & Direzione Onda",
            value: `${waves.peak_period_s} s (${waves.direction_cardinal})`,
            sub: `Lunghezza L ≈ ${waves.wavelength_m} m`,
          },
          {
            label: "Onda Vento vs Swell",
            value: `${waves.wind_wave_height_m}m / ${waves.swell_height_m}m`,
            sub: waves.steepness_warning
              ? "⚠️ Onda corta ripida frangente"
              : "Profilo d'onda regolare",
          },
          {
            label: "Temp. Acqua (SST)",
            value: `${waves.sea_surface_temp_c}°C`,
            sub: `Visibilità: ${(cur.visibility_m / 1000).toFixed(1)} km`,
          },
          {
            label: "Picco Pioggia LAM",
            value: `${hydro.precip_1h_mm} mm/h`,
            sub: `Cumulata 24h: ${hydro.precip_24h_mm} mm`,
          },
        ]
      : [
          {
            label: "Intensità Pioggia (1h)",
            value: `${hydro.precip_1h_mm} mm/h`,
            sub: `Picco LAM: ${cur.precip_max_lam_mm} mm/h`,
          },
          {
            label: "Cumulata 3h / 24h",
            value: `${hydro.precip_3h_mm} / ${hydro.precip_24h_mm} mm`,
            sub: hydro.label.split("—")[0],
          },
          {
            label: "Vento & Raffica (Terra)",
            value: `${cur.wind_kmh} / ${cur.gust_kmh} km/h`,
            sub: `${wind.speed_knots} / ${wind.gust_knots} kt da ${cur.wind_cardinal}`,
          },
          {
            label: "Umidità & CAPE",
            value: `${cur.humidity_pct}%`,
            sub: `Energia CAPE: ${cur.cape_j_kg} J/kg`,
          },
          {
            label: "Zero Termico & Visibilità",
            value: `${landRisk.appennino_passes.freezing_level_m} m`,
            sub: `Visibilità: ${(cur.visibility_m / 1000).toFixed(1)} km`,
          },
          {
            label: "Stato del Mare Antistante",
            value: `Hs ${waves.significant_height_m} m @ ${waves.peak_period_s}s`,
            sub: `Mare ${waves.douglas.label} (${waves.direction_cardinal})`,
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
  setBadgeLevel(
    document.getElementById("sea-overall-badge"),
    seaCond.overall_level,
    LEVEL_LABELS[seaCond.overall_level]
  );

  const landContainer = document.getElementById("land-risk-items");
  const convBorder =
    conv.convergence_score >= 65
      ? "red"
      : conv.convergence_score >= 35
      ? "yellow"
      : "green";

  landContainer.innerHTML = `
    <div class="risk-item border-${landRisk.hydrogeological.level}">
      <div class="risk-item-title">
        <span>🌊 Bacini & Rischio Idrogeologico (Bisagno, Polcevera, Entella)</span>
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
        <span>🛵 Viabilità Urbana, Sopraelevata & Viadotti Autostradali</span>
        <span>Raffica ${landRisk.wind_viability.gust_kmh} km/h</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.wind_viability.label}:</strong> ${landRisk.wind_viability.advice}</div>
    </div>

    <div class="risk-item border-${landRisk.appennino_passes.level}">
      <div class="risk-item-title">
        <span>🏔️ Valichi Appenninici (Giovi, Turchino, A7, A26, Val d'Aveto)</span>
        <span>ZT ~${landRisk.appennino_passes.freezing_level_m} m</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.appennino_passes.label}:</strong> ${landRisk.appennino_passes.advice}</div>
    </div>
  `;

  const seaContainer = document.getElementById("sea-risk-items");
  const act = seaCond.activities_safety;
  const w = seaCond.waves;

  seaContainer.innerHTML = `
    <div class="risk-item border-${act.sailing_yachting.level}">
      <div class="risk-item-title">
        <span>⛵ Piccolo Diporto & Vela (Golfo di Genova)</span>
        <span>${act.sailing_yachting.label}</span>
      </div>
      <div class="risk-item-desc">${act.sailing_yachting.note}</div>
    </div>

    <div class="risk-item border-${w.steepness_warning ? "yellow" : "green"}">
      <div class="risk-item-title">
        <span>📐 Cinematica & Ripidità d'Onda (Hs ${w.significant_height_m}m / Hmax ${w.max_height_m}m)</span>
        <span>Tp ${w.peak_period_s} s (${w.direction_cardinal})</span>
      </div>
      <div class="risk-item-desc"><strong>${w.steepness_class}:</strong> Onda da vento ${w.wind_wave_height_m}m + Swell lungo ${w.swell_height_m}m. Lunghezza d'onda ${w.wavelength_m}m.</div>
    </div>

    <div class="risk-item border-${act.coastal_fishing.level}">
      <div class="risk-item-title">
        <span>🎣 Pesca Sportiva & Costiera</span>
        <span>${act.coastal_fishing.label}</span>
      </div>
      <div class="risk-item-desc">${act.coastal_fishing.note}</div>
    </div>

    <div class="risk-item border-${act.kayak_sup_swimming.level}">
      <div class="risk-item-title">
        <span>🛶 Kayak, SUP, Deriva & Sicurezza Ormeggi</span>
        <span>${act.kayak_sup_swimming.label}</span>
      </div>
      <div class="risk-item-desc">${act.kayak_sup_swimming.note} | <strong>Porti:</strong> ${act.harbor_mooring.label}.</div>
    </div>
  `;
}

function renderAIBulletin(bulletin) {
  if (!bulletin) return;
  const badge = document.getElementById("ai-engine-badge");
  badge.textContent = bulletin.ai_powered
    ? "✨ Google Gemini AI Advisor"
    : "🧠 Motore Sinottico Ligure";

  document.getElementById("ai-headline").textContent = bulletin.headline;
  document.getElementById("ai-synoptic-body").textContent =
    bulletin.synoptic_nowcast_analysis;

  const takeawaysGrid = document.getElementById("ai-takeaways-grid");
  takeawaysGrid.innerHTML = (bulletin.key_takeaways || [])
    .map((item) => `<div class="ai-takeaway-item">🔹 ${item}</div>`)
    .join("");
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

  const ctx1 = document.getElementById("chart-multimodel").getContext("2d");
  if (state.chartMultiModel) state.chartMultiModel.destroy();

  state.chartMultiModel = new Chart(ctx1, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "Temp Consensus (°C)",
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
          backgroundColor: "rgba(168, 85, 247, 0.7)",
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

  // Secondo Grafico: Vento/Raffica + Altezza d'Onda Significativa e Massima
  const useKnots = state.mode === "sea";
  const windSeries = slice24.map((h) => (useKnots ? h.wind_knots : h.wind_kmh));
  const gustSeries = slice24.map((h) => (useKnots ? h.gust_knots : h.gust_kmh));
  const waveHsSeries = slice24.map((h) => h.wave_hs_m);
  const waveHmaxSeries = slice24.map((h) => h.wave_hmax_m);

  const ctx2 = document.getElementById("chart-wind-wave").getContext("2d");
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
          label: "Onda Max Stimata Hmax (m)",
          data: waveHmaxSeries,
          borderColor: "#a855f7",
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
  if (!days || !days.length) {
    tbody.innerHTML = `<tr><td colspan="7">Previsione giornaliera non disponibile</td></tr>`;
    return;
  }

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
