/* ==========================================================================
   MedioMeteo Genova v2.5 — Client Application a 6 Schede Chiuse (ADR-0005..0008)
   Sistema visivo taste-skill 2.5.1: blue-black-cornflower + IBM Plex Sans/Mono + sharp radius.
   - Always-On Telemetry HUD Strip (5 parametri live sempre visibili anche sulla mappa).
   - 6 Schede chiuse mutuamente esclusive: all'avvio apre `3. Mappa operativa live`.
   - Click su Comune, Quartiere, Rada, Stazione OMIRL o punto libero -> apre `1. Adesso`.
   - Quadrante nautico vettoriale SVG + fusione multi-sensore OMIRL + sparkline SVG 24h.
   - Modalità Mare a fisica costiera pura (zero semafori consiglio soggettivi).
   ========================================================================== */

import { escapeHtml, sanitizeHttpUrl } from "/static/js/security.js?v=2.6";
import { LEVEL_LABELS, SVG_ICONS } from "/static/js/icons.js?v=2.6";

const state = {
  mode: "land", // 'land' | 'sea'
  activeTab: "tab-mappa", // Scheda predefinita all'avvio: 3. Mappa operativa live
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
  webcamsVisible: false,
  ampLayerGroup: null,
  ampVisible: true,
  locationsLayerGroup: null,
  routePolyline: null,
  customMarker: null,
  chartMultiModel: null,
  chartWindWave: null,
};

function setBadgeLevel(el, level, text) {
  if (!el) return;
  el.className = `badge-pill level-${level || "green"}`;
  el.textContent = text;
}

window.switchTab = function switchTab(tabId) {
  state.activeTab = tabId;
  const hasNativeFocusGroup = "focusGroup" in HTMLElement.prototype;

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isTarget = btn.getAttribute("data-tab") === tabId;
    btn.classList.toggle("active", isTarget);
    btn.setAttribute("aria-selected", isTarget ? "true" : "false");
    btn.toggleAttribute("focusgroupstart", isTarget);
    if (!hasNativeFocusGroup) {
      btn.tabIndex = isTarget ? 0 : -1;
    }
    if (isTarget && typeof btn.scrollIntoView === "function") {
      try {
        btn.scrollIntoView({ block: "nearest", inline: "nearest", container: "nearest" });
      } catch (_) {
        btn.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    }
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const isTarget = panel.id === tabId;
    panel.classList.toggle("active", isTarget);
    panel.hidden = !isTarget;
  });

  if (tabId === "tab-mappa" && state.map) {
    setTimeout(() => state.map.invalidateSize(), 80);
  }
  if (tabId === "tab-modelli" && state.weatherPkg) {
    setTimeout(() => renderCharts(state.weatherPkg.forecast.hourly_48h), 60);
  }
};

function initAccessibilityFallbacks() {
  const hasNativeFocusGroup = "focusGroup" in HTMLElement.prototype;

  // Roving tabindex fallback for [role="tablist"] when browser lacks native focusgroup
  const tablist = document.querySelector('[role="tablist"]');
  if (tablist && !hasNativeFocusGroup) {
    const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
    tabs.forEach((t) => {
      t.tabIndex = t.getAttribute("aria-selected") === "true" ? 0 : -1;
    });
    tablist.addEventListener("keydown", (ev) => {
      const idx = tabs.indexOf(document.activeElement);
      if (idx === -1) return;
      let nextIdx = -1;
      if (ev.key === "ArrowRight") nextIdx = (idx + 1) % tabs.length;
      else if (ev.key === "ArrowLeft") nextIdx = (idx - 1 + tabs.length) % tabs.length;
      else if (ev.key === "Home") nextIdx = 0;
      else if (ev.key === "End") nextIdx = tabs.length - 1;
      if (nextIdx >= 0) {
        ev.preventDefault();
        const nextTab = tabs[nextIdx];
        nextTab.focus();
        window.switchTab(nextTab.getAttribute("data-tab"));
      }
    });
  }

  // Roving tabindex fallback for [role="toolbar"]
  const toolbar = document.querySelector('[role="toolbar"]');
  if (toolbar && !hasNativeFocusGroup) {
    const items = Array.from(toolbar.querySelectorAll("button, a[href]"));
    items.forEach((el, i) => {
      el.tabIndex = i === 0 ? 0 : -1;
    });
    toolbar.addEventListener("focusin", (ev) => {
      if (items.includes(ev.target)) {
        items.forEach((el) => {
          el.tabIndex = el === ev.target ? 0 : -1;
        });
      }
    });
    toolbar.addEventListener("keydown", (ev) => {
      const idx = items.indexOf(document.activeElement);
      if (idx === -1) return;
      let nextIdx = -1;
      if (ev.key === "ArrowRight") nextIdx = (idx + 1) % items.length;
      else if (ev.key === "ArrowLeft") nextIdx = (idx - 1 + items.length) % items.length;
      else if (ev.key === "Home") nextIdx = 0;
      else if (ev.key === "End") nextIdx = items.length - 1;
      if (nextIdx >= 0) {
        ev.preventDefault();
        items[nextIdx].focus();
      }
    });
  }

  // IntersectionObserver horizontal fade fallback when scroll-driven animations are absent
  if (typeof CSS !== "undefined" && !CSS.supports("animation-timeline", "scroll()")) {
    document.querySelectorAll(".tabs-nav.scroller").forEach((scroller) => {
      const first = scroller.firstElementChild;
      const last = scroller.lastElementChild;
      if (!first || !last) return;
      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.target === first) {
              scroller.classList.toggle("more-start", entry.intersectionRatio < 1);
            } else if (entry.target === last) {
              scroller.classList.toggle("more-end", entry.intersectionRatio < 1);
            }
          });
        },
        { root: scroller, threshold: 1, rootMargin: "1px" }
      );
      obs.observe(first);
      obs.observe(last);
    });
  }
}

async function initApp() {
  initAccessibilityFallbacks();
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
    navigator.serviceWorker.register("/sw.js?v=2.6").catch(() => {});
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

  // Mode Switch Terra / Mare
  document.getElementById("btn-mode-land").addEventListener("click", () => switchMode("land"));
  document.getElementById("btn-mode-sea").addEventListener("click", () => switchMode("sea"));

  const btnAdessoToMap = document.getElementById("btn-adesso-to-map");
  if (btnAdessoToMap) {
    btnAdessoToMap.addEventListener("click", () => window.switchTab("tab-mappa"));
  }

  const btnInspectorClose = document.getElementById("btn-inspector-close");
  if (btnInspectorClose) {
    btnInspectorClose.addEventListener("click", closeMapInspector);
  }
  const btnInspectorOpenAdesso = document.getElementById("btn-inspector-open-adesso");
  if (btnInspectorOpenAdesso) {
    btnInspectorOpenAdesso.addEventListener("click", () => {
      closeMapInspector();
      window.switchTab("tab-adesso");
    });
  }
  const inspectorSlot = document.getElementById("inspector-chart-slot");
  if (inspectorSlot) {
    inspectorSlot.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".btn-omirl-chart");
      if (!btn) return;
      const code = btn.getAttribute("data-station-code");
      const sensor = btn.getAttribute("data-sensor") || "Vento";
      if (code) window.inspectOmirlStationChart(code, sensor, btn);
    });
  }

  const omirlStationsGrid = document.getElementById("omirl-stations-grid");
  if (omirlStationsGrid) {
    omirlStationsGrid.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".btn-omirl-chart");
      if (!btn) return;
      const code = btn.getAttribute("data-station-code");
      const sensor = btn.getAttribute("data-sensor") || "Vento";
      if (code) window.inspectOmirlStationChart(code, sensor, btn);
    });
  }

  // Filtri e ricerca unificata 118 località (Popover combobox + select nascosti sincronizzati)
  const pickerBtn = document.getElementById("loc-picker-btn");
  const pickerPanel = document.getElementById("loc-picker-panel");
  const typeFilter = document.getElementById("loc-type-filter");
  const searchInput = document.getElementById("loc-search-input");
  const selectLoc = document.getElementById("district-select");
  const chipButtons = document.querySelectorAll(".loc-chip");

  function setPickerOpen(open) {
    if (!pickerBtn || !pickerPanel) return;
    pickerPanel.hidden = !open;
    pickerBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open && searchInput) {
      setTimeout(() => searchInput.focus(), 20);
    }
  }

  window.__closeLocPicker = () => setPickerOpen(false);

  const btnToggleFav = document.getElementById("btn-toggle-fav");
  if (btnToggleFav) {
    btnToggleFav.addEventListener("click", () => {
      if (!state.selectedLocationId) return;
      let favs = loadFavorites();
      if (favs.includes(state.selectedLocationId)) {
        favs = favs.filter((id) => id !== state.selectedLocationId);
      } else {
        favs = [state.selectedLocationId, ...favs].slice(0, 5);
      }
      saveFavorites(favs);
      renderFavoritesBar();
    });
  }

  const favChipsBar = document.getElementById("fav-chips-bar");
  if (favChipsBar) {
    favChipsBar.addEventListener("click", async (ev) => {
      const chip = ev.target.closest(".fav-chip");
      if (!chip) return;
      const favId = chip.getAttribute("data-fav-id");
      if (!favId) return;
      if (pickerPanel && pickerBtn) {
        pickerPanel.hidden = true;
        pickerBtn.setAttribute("aria-expanded", "false");
      }
      await selectLocationById(favId, false);
    });
  }

  if (pickerBtn && pickerPanel) {
    pickerBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      setPickerOpen(pickerPanel.hidden);
    });

    document.addEventListener("pointerdown", (ev) => {
      if (!pickerPanel.hidden && !pickerPanel.contains(ev.target) && !pickerBtn.contains(ev.target)) {
        setPickerOpen(false);
      }
    });

    pickerPanel.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        setPickerOpen(false);
        pickerBtn.focus();
      }
    });
  }

  chipButtons.forEach((chip) => {
    chip.addEventListener("click", () => {
      const val = chip.getAttribute("data-loc-type") || "";
      chipButtons.forEach((c) => c.setAttribute("aria-pressed", c === chip ? "true" : "false"));
      if (typeFilter) typeFilter.value = val;
      populateLocationSelect();
      renderLocationsOnMap();
    });
  });

  if (typeFilter) {
    typeFilter.addEventListener("change", () => {
      populateLocationSelect();
      renderLocationsOnMap();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => populateLocationSelect());
    searchInput.addEventListener("keydown", async (ev) => {
      if (ev.key === "Enter" && state.filteredLocations.length > 0) {
        ev.preventDefault();
        await selectLocationById(state.filteredLocations[0].id, false);
        setPickerOpen(false);
      } else if (ev.key === "ArrowDown") {
        const firstOpt = document.querySelector("#loc-picker-list .loc-option");
        if (firstOpt) {
          ev.preventDefault();
          firstOpt.focus();
        }
      }
    });
  }

  if (selectLoc) {
    selectLoc.addEventListener("change", async (e) => {
      await selectLocationById(e.target.value, false);
    });
  }

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
        alert("Impossibile ottenere la posizione GPS. Usa la mappa live o il selettore comuni.");
      }
    );
  });

  // Refresh Live Button
  document.getElementById("btn-refresh").addEventListener("click", async () => {
    await refreshAllData(true);
  });

  // Map Layer Toggles
  document.getElementById("btn-toggle-radar").addEventListener("click", (e) => {
    state.radarVisible = !state.radarVisible;
    e.currentTarget.classList.toggle("active", state.radarVisible);
    e.currentTarget.setAttribute("aria-pressed", state.radarVisible ? "true" : "false");
    updateRadarLayer();
  });

  document.getElementById("btn-toggle-omirl").addEventListener("click", (e) => {
    state.omirlVisible = !state.omirlVisible;
    e.currentTarget.classList.toggle("active", state.omirlVisible);
    e.currentTarget.setAttribute("aria-pressed", state.omirlVisible ? "true" : "false");
    renderMapOverlays();
  });

  document.getElementById("btn-toggle-webcams").addEventListener("click", (e) => {
    state.webcamsVisible = !state.webcamsVisible;
    e.currentTarget.classList.toggle("active", state.webcamsVisible);
    e.currentTarget.setAttribute("aria-pressed", state.webcamsVisible ? "true" : "false");
    renderMapOverlays();
  });

  document.getElementById("btn-toggle-amp").addEventListener("click", (e) => {
    state.ampVisible = !state.ampVisible;
    e.currentTarget.classList.toggle("active", state.ampVisible);
    e.currentTarget.setAttribute("aria-pressed", state.ampVisible ? "true" : "false");
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

  // Modelli Focused View Switcher (Meteogrammi | Confronto 5 modelli | 7 giorni)
  document.querySelectorAll(".modelli-subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-modelli-pane");
      document.querySelectorAll(".modelli-subtab-btn").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-pressed", active ? "true" : "false");
      });
      ["modelli-pane-charts", "modelli-pane-table", "modelli-pane-7d"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.hidden = id !== targetId;
      });
      if (targetId === "modelli-pane-charts" && state.weatherPkg) {
        setTimeout(() => renderCharts(state.weatherPkg.forecast.hourly_48h), 40);
      }
    });
  });
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
      state.map.flyTo([found.lat, found.lon], 12, {
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
  const isLand = state.mode === "land";
  btnLand.className = isLand ? "mode-btn active-land" : "mode-btn";
  btnSea.className = isLand ? "mode-btn" : "mode-btn active-sea";
  btnLand.setAttribute("aria-pressed", isLand ? "true" : "false");
  btnSea.setAttribute("aria-pressed", isLand ? "false" : "true");
}

function updateLocationPickerTrigger(loc, coords) {
  const lbl = document.getElementById("loc-picker-label");
  const meta = document.getElementById("loc-picker-meta");
  if (!lbl || !meta) return;

  if (coords && coords.is_custom_pin) {
    lbl.textContent = loc?.name ? `Presso ${loc.name}` : "Punto su mappa";
    meta.textContent = `${coords.lat.toFixed(2)}°N, ${coords.lon.toFixed(2)}°E`;
    return;
  }

  const typeNames = {
    comune: "Comune",
    quartiere: "Quartiere",
    rada_porto: "Rada",
    valico: "Valico",
  };
  lbl.textContent = loc?.name || "Genova";
  meta.textContent = typeNames[loc?.loc_type] || loc?.valley_or_sector || "Genova";
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

const FAV_STORAGE_KEY = "mediometeo_favorites_v1";
const DEFAULT_FAVORITES = ["COM-GENOVA", "COM-PORTOFINO", "QRT-GENOVA-MARASSI", "COM-ARENZANO"];

function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAV_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length) {
        return parsed.slice(0, 5);
      }
    }
  } catch (_) {}
  return [...DEFAULT_FAVORITES];
}

function saveFavorites(ids) {
  try {
    localStorage.setItem(FAV_STORAGE_KEY, JSON.stringify(ids.slice(0, 5)));
  } catch (_) {}
}

function renderFavoritesBar() {
  const bar = document.getElementById("fav-chips-bar");
  const toggleBtn = document.getElementById("btn-toggle-fav");
  const favs = loadFavorites();

  if (toggleBtn) {
    const isFav = !state.customCoords && favs.includes(state.selectedLocationId);
    toggleBtn.setAttribute("aria-pressed", isFav ? "true" : "false");
  }
  if (!bar) return;

  const validFavs = favs
    .map((id) => state.locations.find((l) => l.id === id))
    .filter(Boolean);

  bar.innerHTML = validFavs
    .map((loc) => {
      const active = !state.customCoords && loc.id === state.selectedLocationId;
      return `<button type="button" class="fav-chip${active ? " active" : ""}" data-fav-id="${escapeHtml(loc.id)}">${escapeHtml(loc.name)}</button>`;
    })
    .join("");
}

function populateLocationSelect() {
  const select = document.getElementById("district-select");
  const listEl = document.getElementById("loc-picker-list");
  const typeFilter = document.getElementById("loc-type-filter")?.value || "";
  const query = (document.getElementById("loc-search-input")?.value || "").trim().toLowerCase();

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
  if (select) select.innerHTML = "";
  if (listEl) listEl.innerHTML = "";

  const groupsMeta = {
    comune: "67 Comuni — Città Metropolitana",
    quartiere: "25 Quartieri / Municipi",
    rada_porto: "20 Rade, porti e capi",
    valico: "6 Valichi appenninici",
  };

  const groups = {
    comune: { label: groupsMeta.comune, el: document.createElement("optgroup"), items: [] },
    quartiere: { label: groupsMeta.quartiere, el: document.createElement("optgroup"), items: [] },
    rada_porto: { label: groupsMeta.rada_porto, el: document.createElement("optgroup"), items: [] },
    valico: { label: groupsMeta.valico, el: document.createElement("optgroup"), items: [] },
  };

  Object.values(groups).forEach((g) => {
    g.el.label = g.label;
  });

  const codeMap = {
    comune: "CM",
    quartiere: "QT",
    rada_porto: "RD",
    valico: "VL",
  };

  filtered.forEach((loc) => {
    const code = codeMap[loc.loc_type] || "GE";
    if (select) {
      const opt = document.createElement("option");
      opt.value = loc.id;
      opt.textContent = `[${code}] ${loc.name} (${loc.valley_or_sector})`;
      if (groups[loc.loc_type]) {
        groups[loc.loc_type].el.appendChild(opt);
      }
    }
    if (groups[loc.loc_type]) {
      groups[loc.loc_type].items.push(loc);
    }
  });

  Object.values(groups).forEach((g) => {
    if (select && g.el.children.length > 0) {
      select.appendChild(g.el);
    }
    if (listEl && g.items.length > 0) {
      const head = document.createElement("div");
      head.className = "loc-group-head";
      head.textContent = g.label;
      listEl.appendChild(head);

      g.items.forEach((loc) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "loc-option";
        btn.setAttribute("role", "option");
        btn.setAttribute("aria-selected", loc.id === state.selectedLocationId ? "true" : "false");

        const nameSpan = document.createElement("span");
        nameSpan.textContent = loc.name;
        const sectorSpan = document.createElement("span");
        sectorSpan.className = "loc-option-sector";
        sectorSpan.textContent = loc.valley_or_sector;

        btn.appendChild(nameSpan);
        btn.appendChild(sectorSpan);
        btn.addEventListener("click", async () => {
          await selectLocationById(loc.id, false);
          if (typeof window.__closeLocPicker === "function") window.__closeLocPicker();
        });
        listEl.appendChild(btn);
      });
    }
  });

  if (listEl && filtered.length === 0) {
    const emptyEl = document.createElement("div");
    emptyEl.className = "loc-picker-empty";
    emptyEl.textContent = "Nessuna località trovata per questo filtro.";
    listEl.appendChild(emptyEl);
  }

  if (select) {
    if (filtered.some((l) => l.id === state.selectedLocationId)) {
      select.value = state.selectedLocationId;
    } else if (filtered.length > 0) {
      select.value = filtered[0].id;
    }
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
    o1.textContent = `${wp.name}${wp.amp_zone ? " [" + wp.amp_zone + "]" : ""}`;
    const o2 = o1.cloneNode(true);
    selOrigin.appendChild(o1);
    selDest.appendChild(o2);
  });

  selOrigin.value = "portofino";
  selDest.value = "san_fruttuoso";
}

function closeMapInspector() {
  const drawer = document.getElementById("map-inspector-drawer");
  if (drawer) drawer.hidden = true;
}

function openMapInspector({ title, meta, metrics, stationCode = null, sensor = "Vento" }) {
  const drawer = document.getElementById("map-inspector-drawer");
  if (!drawer) return;
  const titleEl = document.getElementById("inspector-title");
  const metaEl = document.getElementById("inspector-meta");
  const metricsEl = document.getElementById("inspector-metrics");
  const chartSlot = document.getElementById("inspector-chart-slot");

  if (titleEl) titleEl.textContent = title || "--";
  if (metaEl) metaEl.textContent = meta || "--";
  if (metricsEl) {
    metricsEl.innerHTML = (metrics || [])
      .map(
        (m) => `
      <div class="map-inspector-kv">
        <span>${escapeHtml(m.label)}</span>
        <strong>${escapeHtml(m.value)}</strong>
      </div>`
      )
      .join("");
  }
  if (chartSlot) {
    if (stationCode) {
      chartSlot.innerHTML = `<button type="button" class="btn-action btn-omirl-chart" data-station-code="${escapeHtml(stationCode)}" data-sensor="${escapeHtml(sensor)}">Curva 24h OMIRL (${escapeHtml(sensor)})</button>`;
    } else {
      chartSlot.innerHTML = "";
    }
  }
  drawer.hidden = false;
}

function initLeafletMap() {
  if (typeof L === "undefined") return;

  state.map = L.map("genova-map", {
    center: [44.395, 9.03],
    zoom: 10,
    zoomControl: true,
  });

  // Base vettoriale costa ligure (sempre visibile anche offline / senza tile raster)
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
  L.polygon(liguriaLandPoly, {
    color: "rgba(90, 185, 252, 0.45)",
    weight: 1.5,
    fillColor: "#141c2b",
    fillOpacity: 0.92,
    interactive: false,
  }).addTo(state.map);

  // Torrenti principali genovesi & etichette costiere minimali sempre visibili
  const riverPaths = [
    [[44.50, 8.91], [44.45, 8.895], [44.415, 8.885]], // Polcevera
    [[44.48, 9.01], [44.44, 8.97], [44.398, 8.947]], // Bisagno
    [[44.56, 8.66], [44.51, 8.68], [44.46, 8.66]], // Stura
    [[44.42, 9.41], [44.36, 9.35], [44.31, 9.33]], // Entella
  ];
  riverPaths.forEach((coords) => {
    L.polyline(coords, {
      color: "rgba(90, 185, 252, 0.35)",
      weight: 1.4,
      dashArray: "3, 4",
      interactive: false,
    }).addTo(state.map);
  });

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
        iconSize: [72, 16],
        iconAnchor: [36, 8],
      }),
    }).addTo(state.map);
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
  state.map.on("zoomend", () => {
    renderLocationsOnMap();
    renderMapOverlays();
  });

  // Click libero sulla Mappa Live -> seleziona coordinata e apre Inspector Drawer
  state.map.on("click", async (ev) => {
    const lat = Number(ev.latlng.lat.toFixed(4));
    const lon = Number(ev.latlng.lng.toFixed(4));
    state.customCoords = { lat, lon };

    if (state.customMarker) {
      state.map.removeLayer(state.customMarker);
    }
    state.customMarker = L.circleMarker([lat, lon], {
      radius: 8,
      color: "#5ab9fc",
      weight: 2.5,
      fillColor: "#f59e0b",
      fillOpacity: 0.92,
    })
      .addTo(state.map)
      .bindTooltip(`Punto selezionato: <strong>${lat}, ${lon}</strong>`);

    openMapInspector({
      title: `Punto selezionato (${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E)`,
      meta: "Caricamento modello locale e sensori...",
      metrics: [],
    });
    await refreshAllData(false);
    if (state.weatherPkg) {
      const cur = state.weatherPkg.nowcast?.current || {};
      const waves = state.weatherPkg.sea?.marine_conditions?.waves || {};
      const locName = state.weatherPkg.location?.name || "Punto su mappa";
      openMapInspector({
        title: locName,
        meta: `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`,
        metrics: [
          { label: "Temperatura", value: `${cur.temp_c ?? "--"}°C` },
          { label: "Vento", value: `${cur.wind_knots ?? "--"} kt (r.${cur.gust_knots ?? "--"})` },
          { label: "Pioggia 1h", value: `${cur.precip_mm ?? 0} mm` },
          { label: "Onda Hs", value: `${waves.significant_height_m ?? "--"} m` },
        ],
      });
    }
  });
}

function renderLocationsOnMap() {
  if (!state.map || !state.locationsLayerGroup) return;
  state.locationsLayerGroup.clearLayers();

  const currentZoom = state.map.getZoom() || 10;
  const typeFilter = document.getElementById("loc-type-filter")?.value || "";

  state.locations.forEach((loc) => {
    if (typeFilter && loc.loc_type !== typeFilter) return;

    const isSelected = loc.id === state.selectedLocationId;
    if (!typeFilter && currentZoom < 12 && !isSelected) {
      return;
    }
    const styleMap = {
      comune: { code: "CM", bg: "#10b981", fg: "#06130e" },
      quartiere: { code: "QT", bg: "#34d399", fg: "#06130e" },
      rada_porto: { code: "RD", bg: "#5ab9fc", fg: "#0a0d14" },
      valico: { code: "VL", bg: "#f59e0b", fg: "#0a0d14" },
    };
    const meta = styleMap[loc.loc_type] || { code: "GE", bg: "#10b981", fg: "#06130e" };
    const bg = isSelected ? "#f59e0b" : meta.bg;
    const fg = isSelected ? "#0a0d14" : meta.fg;
    const w = isSelected ? 28 : 24;
    const h = isSelected ? 24 : 20;

    const icon = L.divIcon({
      html: `<div style="
        background: ${bg};
        color: ${fg};
        border: ${isSelected ? "2px solid #e9edf3" : "1px solid rgba(10,13,20,0.75)"};
        border-radius: 4px;
        width: ${w}px;
        height: ${h}px;
        display: grid;
        place-items: center;
        font-family: 'IBM Plex Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.02em;
        box-shadow: 0 2px 6px rgba(0,0,0,0.65);
      ">${meta.code}</div>`,
      className: "",
      iconSize: [w, h],
      iconAnchor: [w / 2, h / 2],
    });

    const marker = L.marker([loc.lat, loc.lon], { icon }).addTo(state.locationsLayerGroup);
    const bayNote =
      loc.bay_open_deg !== null && loc.bay_open_deg !== undefined
        ? `<br>Cala aperta a <strong>${loc.bay_open_deg}°</strong>`
        : "";
    marker.bindTooltip(
      `<strong>${loc.name}</strong> (${meta.code})<br>${loc.valley_or_sector}${bayNote}<br><em>Clicca per aprire 1. Adesso</em>`
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
          zone.max_speed_knots === 0 ? "Divieto accesso" : zone.max_speed_knots + " kt"
        }</strong><br>${zone.rules}`
      );
    });
  }

  if (!state.weatherPkg) return;
  const obs = state.weatherPkg.observations_live || {};

  // 2. Stazioni reali OMIRL (anemometri con freccia SVG + termo/pluvio badge) & idrometri (Spatial Tiering ADR-0010)
  const zoom = state.map ? state.map.getZoom() : 10;
  const shouldShowFullBadge = (item) => {
    const tier = item.display_tier ?? 1;
    const sev = item.severity || "normal";
    if (sev === "watch" || sev === "alert" || tier === 1) return true;
    if (tier === 2 && zoom >= 11) return true;
    if (tier >= 3 && zoom >= 13) return true;
    return false;
  };

  state.omirlLayerGroup.clearLayers();
  if (state.omirlVisible) {
    const stations = obs.all_weather_stations || obs.nearest_weather_stations || [];
    stations.forEach((st) => {
      const hasWind = st.has_live_wind !== false && st.sensor !== "Termo/Pluvio";
      const windDeg = st.wind_dir_deg ?? 0;
      const arrowRotate = (windDeg + 90) % 360;
      const isStrong = (st.wind_knots || 0) >= 16;
      const fullBadge = shouldShowFullBadge(st);

      let badgeHtml = "";
      let iconSize = [66, 22];
      let iconAnchor = [33, 11];

      if (!fullBadge) {
        const dotColor = hasWind ? (isStrong ? "#f59e0b" : "#5ab9fc") : Number(st.precip_1h_mm || 0) > 0 ? "#5ab9fc" : "#94a3b8";
        iconSize = [8, 8];
        iconAnchor = [4, 4];
        badgeHtml = `<div style="width:8px;height:8px;border-radius:50%;background:${dotColor};border:1px solid #0a0d14;opacity:0.85;box-shadow:0 1px 3px rgba(0,0,0,0.6);"></div>`;
      } else if (hasWind) {
        const borderCol = isStrong ? "#f59e0b" : "#5ab9fc";
        const textCol = isStrong ? "#fbbf24" : "#e9edf3";
        const arrowColor = isStrong ? "#f59e0b" : "#5ab9fc";
        const arrowSvg = `<svg width="11" height="11" viewBox="0 0 12 12" style="display:inline-block;flex-shrink:0;transform:rotate(${arrowRotate}deg);" aria-hidden="true"><path d="M1.5 6h8M6.5 2.5L10.5 6l-4 3.5" fill="none" stroke="${arrowColor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        badgeHtml = `<div style="
          background: rgba(10, 13, 20, 0.94);
          color: ${textCol};
          border: 1px solid ${borderCol};
          border-radius: 4px;
          padding: 2px 6px;
          font-family: 'IBM Plex Mono', monospace;
          font-variant-numeric: tabular-nums;
          font-size: 11px;
          font-weight: 600;
          white-space: nowrap;
          display: inline-flex;
          align-items: center;
          gap: 4px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.7);
        ">${arrowSvg}<span>${st.wind_knots ?? "--"} kt</span></div>`;
      } else {
        const hasRain = Number(st.precip_1h_mm || 0) > 0;
        const borderCol = hasRain ? "#5ab9fc" : "rgba(233, 237, 243, 0.28)";
        const tempPart = st.has_live_temp !== false && st.temp_c !== undefined ? `${st.temp_c}°` : "";
        const rainPart = st.has_live_rain && st.precip_1h_mm !== undefined ? `${Number(st.precip_1h_mm).toFixed(1)}mm` : "";
        const badgeText = [tempPart, rainPart].filter(Boolean).join(" ") || `${st.temp_c ?? "--"}°`;
        iconSize = [68, 20];
        iconAnchor = [34, 10];
        badgeHtml = `<div style="
          background: rgba(10, 13, 20, 0.92);
          color: #e9edf3;
          border: 1px solid ${borderCol};
          border-radius: 4px;
          padding: 1px 6px;
          font-family: 'IBM Plex Mono', monospace;
          font-variant-numeric: tabular-nums;
          font-size: 11px;
          font-weight: 500;
          white-space: nowrap;
          display: inline-flex;
          align-items: center;
          gap: 4px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.65);
        ">${badgeText}</div>`;
      }

      const icon = L.divIcon({
        html: badgeHtml,
        className: "",
        iconSize,
        iconAnchor,
      });
      const m = L.marker([st.lat, st.lon], { icon }).addTo(state.omirlLayerGroup);
      const srcLabel = st.is_live_rest ? "Live REST OMIRL" : "OMIRL / LAM";
      const windLine = hasWind
        ? `Vento: <strong>${st.wind_knots} kt</strong> (${st.wind_kmh} km/h da ${windDeg}°) | Raff: ${st.gust_knots} kt<br>`
        : `Sensore: <strong>${st.sensor || "Termo/Pluvio"}</strong><br>`;
      m.bindTooltip(
        `<strong>Centralina OMIRL: ${escapeHtml(st.name)} (${escapeHtml(st.code)})</strong> [${escapeHtml(srcLabel)}]<br>` +
          windLine +
          `Temp: <strong>${escapeHtml(st.temp_c)}°C</strong> | Pioggia 1h: <strong>${escapeHtml(st.precip_1h_mm)} mm</strong> • Ore ${escapeHtml(st.observed_at)}`
      );
      m.on("click", async (ev) => {
        L.DomEvent.stopPropagation(ev);
        state.customCoords = { lat: st.lat, lon: st.lon };
        const defaultSensor = hasWind ? "Vento" : st.has_live_temp !== false ? "Termo" : "Pluvio";
        const gustLabel = st.gust_estimated ? `~${st.gust_knots} kt` : `${st.gust_knots} kt`;
        openMapInspector({
          title: `${st.name} (${st.code})`,
          meta: `${st.muni || "Genova"} • Quota ${st.elev_m} m • Ore ${st.observed_at}`,
          metrics: [
            { label: "Temperatura", value: `${st.temp_c ?? "--"}°C` },
            { label: "Vento / Raffica", value: hasWind ? `${st.wind_knots} / ${gustLabel}` : `Rif. ${st.wind_knots} kt` },
            { label: "Pioggia 1h", value: `${st.precip_1h_mm ?? 0} mm` },
            { label: "Sensore", value: st.sensor || "OMIRL" },
          ],
          stationCode: st.code,
          sensor: defaultSensor,
        });
        await refreshAllData(false);
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
      const fullHydro = shouldShowFullBadge(hy);
      const badgeHtml = fullHydro
        ? `<div style="
        background: rgba(10, 13, 20, 0.94);
        color: ${color};
        border: 1px solid ${color};
        border-radius: 4px;
        padding: 1px 6px;
        font-family: 'IBM Plex Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
        box-shadow: 0 2px 6px rgba(0,0,0,0.7);
      ">IDRO ${escapeHtml(hy.level_m)}m</div>`
        : `<div style="width:8px;height:8px;border-radius:50%;background:${color};border:1px solid #0a0d14;opacity:0.9;"></div>`;
      const icon = L.divIcon({
        html: badgeHtml,
        className: "",
        iconSize: fullHydro ? [76, 20] : [8, 8],
        iconAnchor: fullHydro ? [38, 10] : [4, 4],
      });
      const m = L.marker([hy.lat, hy.lon], { icon }).addTo(state.omirlLayerGroup);
      m.bindTooltip(
        `<strong>Idrometro reale OMIRL: ${escapeHtml(hy.name)} (${escapeHtml(hy.river)})</strong><br>` +
          `Livello misurato: <strong>${escapeHtml(hy.level_m)} m</strong> (Soglia gialla: ${escapeHtml(hy.warn_threshold_m)} m / Rossa: ${escapeHtml(hy.alarm_threshold_m)} m)<br>` +
          `${escapeHtml(hy.status_label)} • Ore ${escapeHtml(hy.observed_at)}`
      );
      m.on("click", (ev) => {
        L.DomEvent.stopPropagation(ev);
        openMapInspector({
          title: `Idrometro ${hy.name} (${hy.code})`,
          meta: `Torrente ${hy.river} • Ore ${hy.observed_at}`,
          metrics: [
            { label: "Livello alveo", value: `${hy.level_m} m` },
            { label: "Soglia gialla", value: `${hy.warn_threshold_m} m` },
            { label: "Soglia rossa", value: `${hy.alarm_threshold_m} m` },
            { label: "Stato", value: hy.status_level === "green" ? "Regolare" : "Guardia" },
          ],
          stationCode: hy.code,
          sensor: "Idro",
        });
      });
    });

    // Boa ondametrica Capo Mele (se disponibile)
    const buoy = obs.marine_wave_buoy || obs.buoys_live?.[0];
    if (buoy) {
      const b = buoy;
      const bLat = b.lat ?? 43.918;
      const bLon = b.lon ?? 8.185;
      const bInc = Number(b.increment_m ?? 0);
      const buoyIcon = L.divIcon({
        html: `<div style="
          background: #0284c7;
          color: #ffffff;
          border: 1px solid #e9edf3;
          border-radius: 4px;
          padding: 2px 7px;
          font-family: 'IBM Plex Mono', monospace;
          font-variant-numeric: tabular-nums;
          font-size: 11px;
          font-weight: 600;
          white-space: nowrap;
          box-shadow: 0 3px 10px rgba(0,0,0,0.75);
        ">BOA Hs ${b.wave_hs_m}m</div>`,
        className: "",
        iconSize: [96, 22],
        iconAnchor: [48, 11],
      });
      const bm = L.marker([bLat, bLon], { icon: buoyIcon }).addTo(state.omirlLayerGroup);
      bm.bindTooltip(
        `<strong>${b.name} (${b.code})</strong><br>Altezza onda significativa misurata: <strong>${b.wave_hs_m} m</strong> (Δ ${bInc >= 0 ? "+" : ""}${bInc} m)<br>Aggiornamento: ${b.observed_at}`
      );
    }
  }

  // 3. Pin webcam live sulla mappa (SVG camera glyph in #0284c7)
  state.webcamLayerGroup.clearLayers();
  if (state.webcamsVisible) {
    const cams = obs.all_webcams || obs.nearest_webcams || [];
    const camMarkerSvg = `<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="4.5" width="12" height="8.5" rx="1.5"/><circle cx="8" cy="8.75" r="2.2"/><path d="M5.5 4.5L6.5 3h3l1 1.5"/></svg>`;
    cams.forEach((cam) => {
      const icon = L.divIcon({
        html: `<div style="
          background: #0284c7;
          color: #ffffff;
          border: 1px solid #e9edf3;
          border-radius: 4px;
          width: 24px;
          height: 24px;
          display: grid;
          place-items: center;
          box-shadow: 0 2px 6px rgba(0,0,0,0.75);
        ">${camMarkerSvg}</div>`,
        className: "",
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
      const m = L.marker([cam.lat, cam.lon], { icon }).addTo(state.webcamLayerGroup);
      const imgPreview = cam.live_image_url
        ? `<img src="${cam.live_image_url}" alt="${cam.name}" style="width:200px;border-radius:4px;margin:4px 0;display:block;" />`
        : "";
      m.bindPopup(
        `<strong>${cam.name}</strong><br>${cam.view_direction}<br>${imgPreview}` +
          `<a href="${cam.portal_url}" target="_blank" rel="noopener" style="color:#5ab9fc;font-weight:600;">Apri stream / portale live</a>`
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
    btn.textContent = "Pausa radar";
    state.radarTimer = setInterval(() => {
      state.radarFrameIndex = (state.radarFrameIndex + 1) % frames.length;
      const slider = document.getElementById("radar-frame-slider");
      if (slider) slider.value = String(state.radarFrameIndex);
      updateRadarLayer();
    }, 850);
  } else {
    btn.textContent = "Play radar";
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
      : "Radar live";
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
  updateLocationPickerTrigger(loc, pkg.coordinates);
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
    const typeLabelMap = {
      comune: "Comune",
      quartiere: "Quartiere",
      rada_porto: "Rada / porto",
      valico: "Valico",
    };
    const typeLabel = typeLabelMap[loc.loc_type] || "Località";
    typeTag.textContent = loc.valley_or_sector ? `${typeLabel} • ${loc.valley_or_sector}` : typeLabel;
  }
  document.getElementById("banner-microclimate").textContent =
    loc.shelter_notes || d.microclimate_notes;

  // Refresh selected option state in unified picker
  populateLocationSelect();
  renderFavoritesBar();

  // Popolamento HUD adattiva 4-metriche Terra / Mare
  const isSeaMode = state.mode === "sea";
  const cellTemp = document.getElementById("hud-cell-temp");
  const cellWave = document.getElementById("hud-cell-wave");
  if (cellTemp) cellTemp.hidden = isSeaMode;
  if (cellWave) cellWave.hidden = !isSeaMode;

  const hudTemp = document.getElementById("hud-val-temp");
  const hudSubTemp = document.getElementById("hud-sub-temp");
  if (hudTemp) {
    hudTemp.textContent = `${cur.temp_c.toFixed(1)}°C`;
    hudSubTemp.textContent = `${cur.weather_description} • Perc. ${thermo.perceived_temp_c ?? cur.temp_c}°C`;
  }

  const hudWind = document.getElementById("hud-val-wind");
  const hudSubWind = document.getElementById("hud-sub-wind");
  if (hudWind) {
    hudWind.textContent = isSeaMode
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

  const hudLblRain = document.getElementById("hud-lbl-rain");
  const hudRain = document.getElementById("hud-val-rain");
  const hudSubRain = document.getElementById("hud-sub-rain");
  if (hudRain) {
    if (isSeaMode) {
      if (hudLblRain) hudLblRain.textContent = "Risacca e marea";
      hudRain.textContent = `Risacca ${coastal.bay_surge.shore_breaker_height_m}m`;
      const tideTag = coastal.tides?.is_synthetic ? "Marea stimata" : "Marea";
      hudSubRain.textContent = `${tideTag} ${coastal.tides.current_height_cm}cm (${coastal.tides.current_phase})`;
    } else {
      if (hudLblRain) hudLblRain.textContent = "Pioggia 1h";
      hudRain.textContent = `${landRisk.hydrogeological.precip_1h_mm} mm/h`;
      hudSubRain.textContent = `${landRisk.hydrogeological.label}`;
    }
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

  renderWatchBanner(pkg);

  // 2. Tab 1: Diagnostica compatta + Quadrante SVG + Stazioni OMIRL + Idrometri + Webcam
  const descEl = document.getElementById("main-weather-desc");
  if (descEl) {
    descEl.textContent = `${cur.weather_description} • ${cur.wind_ligurian_name} ${state.mode === "sea" ? wind.speed_knots + " kt" : cur.wind_kmh + " km/h"}`;
  }
  const trendEl = document.getElementById("pressure-trend");
  if (trendEl) trendEl.textContent = `${cur.pressure_hpa} hPa • ${cur.pressure_trend_label}`;
  document.getElementById(
    "wind-local-note"
  ).innerHTML = `<span><strong>Rosa dei venti ligure (${escapeHtml(wind.ligurian_name)} — ${escapeHtml(wind.cardinal)}):</strong> ${escapeHtml(wind.local_note)}</span>`;

  document.getElementById(
    "map-coords-label"
  ).textContent = `${pkg.coordinates.lat.toFixed(4)}°N, ${pkg.coordinates.lon.toFixed(4)}°E`;

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
    badgeEl.textContent = `Cala aperta ${bayAxis}° • Risacca ${baySurge.shore_breaker_height_m}m`;
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
          fill="${isMain ? "#e9edf3" : "#8891a1"}"
          font-family="IBM Plex Mono, monospace"
          font-size="${isMain ? "11" : "10"}"
          font-weight="${isMain ? "600" : "500"}">
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
          <path d="M0,0 L8,4 L0,8 Z" fill="#5ab9fc" />
        </marker>
      </defs>

      <!-- Cerchi Concentrici Strumentali -->
      <circle cx="${cx}" cy="${cy}" r="${rOuter}" fill="#0a0d14" stroke="rgba(233,237,243,0.22)" stroke-width="1.5" />
      <circle cx="${cx}" cy="${cy}" r="66" fill="none" stroke="rgba(233,237,243,0.12)" stroke-dasharray="3,3" />
      <circle cx="${cx}" cy="${cy}" r="34" fill="none" stroke="rgba(233,237,243,0.12)" />

      <!-- Cono di Esposizione Costiera della Rada/Cala (bay_open_deg) -->
      <path d="${conePath}" fill="rgba(245, 158, 11, 0.16)" stroke="rgba(245, 158, 11, 0.55)" stroke-width="1.2" />

      <!-- Assi Cardinali -->
      <line x1="${cx}" y1="${cy - rOuter}" x2="${cx}" y2="${cy + rOuter}" stroke="rgba(233,237,243,0.14)" />
      <line x1="${cx - rOuter}" y1="${cy}" x2="${cx + rOuter}" y2="${cy}" stroke="rgba(233,237,243,0.14)" />

      <!-- Vettore Swell / Onda -->
      <line x1="${swellFrom.x.toFixed(1)}" y1="${swellFrom.y.toFixed(1)}"
            x2="${swellTo.x.toFixed(1)}" y2="${swellTo.y.toFixed(1)}"
            stroke="#5ab9fc" stroke-width="3" stroke-dasharray="5,3" marker-end="url(#arrow-swell)" />

      <!-- Vettore Vento Reale -->
      <line x1="${windFrom.x.toFixed(1)}" y1="${windFrom.y.toFixed(1)}"
            x2="${windTo.x.toFixed(1)}" y2="${windTo.y.toFixed(1)}"
            stroke="#10b981" stroke-width="3.5" marker-end="url(#arrow-wind)" />

      <!-- Punto Centrale Località -->
      <circle cx="${cx}" cy="${cy}" r="5.5" fill="#f59e0b" stroke="#e9edf3" stroke-width="1.5" />

      <!-- Etichette Rosa dei Venti -->
      ${labelsSvg}
    </svg>
  `;

  if (legendEl) {
    legendEl.innerHTML = `
      <span style="color:#10b981;font-weight:600;display:inline-flex;align-items:center;gap:4px;">
        <span style="display:inline-block;width:14px;height:2px;background:#10b981;"></span>
        Vento ${wind.ligurian_name} (${wind.speed_knots} kt da ${wind.direction_deg}°)
      </span>
      <span style="color:#5ab9fc;font-weight:600;display:inline-flex;align-items:center;gap:4px;">
        <span style="display:inline-block;width:14px;border-top:2px dashed #5ab9fc;"></span>
        Swell (${waves.swell_height_m}m @ ${waves.swell_period_s}s da ${swellDeg}°)
      </span>
      <span style="color:#fbbf24;font-weight:600;display:inline-flex;align-items:center;gap:4px;">
        <span style="display:inline-block;width:10px;height:10px;background:rgba(245,158,11,0.35);border:1px solid #fbbf24;border-radius:2px;"></span>
        Cono cala (${bayAxis}°)
      </span>
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
            label: "Vento & raffica (kt | m/s | km/h)",
            value: `${wind.speed_knots} / ${wind.gust_knots} kt`,
            sub: `${wind.speed_ms}/${wind.gust_ms} m/s • F${wind.beaufort.force} ${wind.beaufort.label}`,
          },
          {
            label: "Spettro onda Hs / Hmax / H1000",
            value: `${waves.significant_height_m} / ${waves.max_height_m} m`,
            sub: `Picco 1/1000: ${waves.extreme_height_1_1000_m}m • ${waves.douglas.label}`,
          },
          {
            label: "Periodo Tp, lunghezza L & ripidità",
            value: `${waves.peak_period_s} s (L=${waves.wavelength_m}m)`,
            sub: `Ripidità H/L: ${waves.steepness_pct}% da ${waves.direction_cardinal}`,
          },
          {
            label: "Onda vento vs swell lungo",
            value: `${waves.wind_wave_height_m}m / ${waves.swell_height_m}m`,
            sub: `Vento ${waves.wind_wave_cardinal} (${waves.wind_wave_period_s}s) • Swell ${waves.swell_cardinal} (${waves.swell_period_s}s)`,
          },
          {
            label: "Risacca in rada & marea",
            value: `Frangente ${coastal.bay_surge.shore_breaker_height_m} m`,
            sub: `Marea ${coastal.tides.current_height_cm} cm (${coastal.tides.current_phase})`,
          },
          {
            label: "Corrente, SST & visibilità",
            value: `${coastal.surface_current.speed_knots} kt (${coastal.surface_current.direction_cardinal})`,
            sub: `Acqua ${waves.sea_surface_temp_c}°C • Visibilità ${coastal.visibility_nm} NM`,
          },
        ]
      : [
          {
            label: "Intensità pioggia (1h / picco LAM)",
            value: `${hydro.precip_1h_mm} mm/h`,
            sub: `Max AROME/ICON-D2: ${cur.precip_max_lam_mm} mm/h`,
          },
          {
            label: "Cumulata pluviometrica 3h / 24h",
            value: `${hydro.precip_3h_mm} / ${hydro.precip_24h_mm} mm`,
            sub: hydro.label.split("—")[0],
          },
          {
            label: "Vento & raffica (km/h | kt)",
            value: `${cur.wind_kmh} / ${cur.gust_kmh} km/h`,
            sub: `${wind.speed_knots} / ${wind.gust_knots} kt da ${cur.wind_cardinal} (${cur.wind_dir_deg}°)`,
          },
          {
            label: "Dew point, percepita & maccaja",
            value: `DP ${thermo.dew_point_c ?? "--"}°C (Perc. ${thermo.perceived_temp_c ?? cur.temp_c}°C)`,
            sub: thermo.maccaja_status || `Umidità ${cur.humidity_pct}%`,
          },
          {
            label: "Zero termico, UV & radiazione",
            value: `ZT ${landRisk.appennino_passes.freezing_level_m} m`,
            sub: `UV ${thermo.uv_index ?? cur.uv_index} • Rad. ${thermo.solar_radiation_wm2 ?? cur.solar_radiation_wm2} W/m²`,
          },
          {
            label: "Fisica mare antistante",
            value: `Hs ${waves.significant_height_m}m (Hmax ${waves.max_height_m}m)`,
            sub: `Tp ${waves.peak_period_s}s da ${waves.direction_cardinal} • ${waves.douglas.label}`,
          },
        ];

  grid.innerHTML = cards
    .map(
      (c) => `
      <div class="kpi-box">
        <div class="kpi-label">${escapeHtml(c.label)}</div>
        <div class="kpi-value">${escapeHtml(c.value)}</div>
        <div class="kpi-sub">${escapeHtml(c.sub)}</div>
      </div>
    `
    )
    .join("");
}

window.inspectOmirlStationChart = async function inspectOmirlStationChart(code, sensor, btnEl) {
  if (!code) return;
  const originalHtml = btnEl.innerHTML;
  btnEl.textContent = "Caricamento serie OMIRL...";
  try {
    const res = await fetch(`/api/v1/omirl-chart?code=${encodeURIComponent(code)}&sensor=${encodeURIComponent(sensor)}`);
    if (!res.ok) {
      btnEl.textContent = "Serie storica 24h non disponibile";
      return;
    }
    const data = await res.json();

    const rawPoints =
      Array.isArray(data.recent_24_points) && data.recent_24_points.length
        ? data.recent_24_points
        : Array.isArray(data.series?.[0]?.points)
        ? data.series[0].points.slice(-24)
        : [];

    const points = rawPoints
      .map((p) => ({
        label: String(p.timestamp ?? p.time_label ?? "").split(" ").pop() || "",
        value: Number(p.value),
      }))
      .filter((p) => Number.isFinite(p.value));

    if ((data.available === false && !points.length) || !points.length) {
      btnEl.textContent = "Serie storica 24h non esposta per questo sensore";
      return;
    }

    const vals = points.map((p) => p.value);
    const minVal = data.min_value ?? Math.min(...vals);
    const maxVal = data.max_value ?? Math.max(...vals);
    const latestPt = points[points.length - 1];
    const unitMap = { Vento: "km/h", Termo: "°C", Pluvio: "mm", Idro: "m" };
    const unit = data.unit ?? unitMap[sensor] ?? "";

    const w = 220;
    const h = 48;
    const padX = 4;
    const padY = 6;
    const span = maxVal - minVal;
    const coords = points.map((p, idx) => {
      const x = points.length === 1 ? w / 2 : padX + (idx / (points.length - 1)) * (w - padX * 2);
      const normY = span > 0 ? (p.value - minVal) / span : 0.5;
      const y = h - padY - normY * (h - padY * 2);
      return { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)) };
    });

    const polylinePoints =
      coords.length === 1
        ? `4,${coords[0].y} 216,${coords[0].y}`
        : coords.map((c) => `${c.x},${c.y}`).join(" ");
    const firstX = coords.length === 1 ? 4 : coords[0].x;
    const lastCoord = coords[coords.length - 1];
    const lastX = coords.length === 1 ? 216 : lastCoord.x;
    const areaPoints = `${firstX},${h - 2} ${polylinePoints} ${lastX},${h - 2}`;

    btnEl.outerHTML = `
      <div class="omirl-sparkline-box" role="region" aria-label="Serie storica 24h ${escapeHtml(sensor)} ${escapeHtml(code)}">
        <div class="omirl-sparkline-head">
          <span>${escapeHtml(sensor)} (${escapeHtml(code)})</span>
          <strong>${escapeHtml(latestPt.value)}${unit ? " " + escapeHtml(unit) : ""}</strong>
        </div>
        <svg class="omirl-sparkline-svg" viewBox="0 0 220 48" preserveAspectRatio="none" role="img" aria-label="Andamento ultime 24 letture ${sensor}">
          <line x1="0" y1="24" x2="220" y2="24" stroke="rgba(233,237,243,0.12)" stroke-dasharray="2,3" stroke-width="1" />
          <polygon points="${areaPoints}" fill="rgba(90,185,252,0.14)" />
          <polyline points="${polylinePoints}" fill="none" stroke="#5ab9fc" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="${lastCoord.x}" cy="${lastCoord.y}" r="2.6" fill="#5ab9fc" stroke="#0a0d14" stroke-width="1" />
        </svg>
        <div class="omirl-sparkline-meta">
          <span>Min ${minVal}${unit ? " " + unit : ""}</span>
          <span>Max ${maxVal}${unit ? " " + unit : ""}</span>
          <span>Ore ${latestPt.label || "--:--"}</span>
        </div>
      </div>
    `;
  } catch (e) {
    btnEl.innerHTML = originalHtml;
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
        ? `<span class="badge-pill level-green">Live REST OMIRL</span>`
        : `<span class="badge-pill level-physics">Sinottica</span>`;
      const hasWind = st.has_live_wind !== false && st.sensor !== "Termo/Pluvio";
      const defaultSensor = hasWind ? "Vento" : st.has_live_temp !== false ? "Termo" : "Pluvio";
      const windPart = hasWind
        ? `<span>${SVG_ICONS.wind} <strong>${st.wind_knots} kt</strong> (${st.wind_kmh} km/h da ${st.wind_dir_deg ?? 0}°) • Max <strong>${st.gust_estimated ? "~" : ""}${st.gust_knots} kt</strong></span>`
        : `<span style="color:var(--p-muted);">${SVG_ICONS.wind} Rif. zona ${st.wind_knots} kt</span>`;

      return `
        <div class="station-card">
          <div class="station-header">
            <div class="station-name">${escapeHtml(st.name)} <span class="station-code">(${escapeHtml(st.code)})</span></div>
            <div style="display:flex;gap:0.35rem;align-items:center;flex-wrap:wrap;">
              ${liveBadge}
              <span class="station-dist">${escapeHtml(st.distance_km)} km</span>
            </div>
          </div>
          <div class="station-meta-line">${escapeHtml(st.muni)} • Quota ${escapeHtml(st.elev_m)} m • Rilevato ore ${escapeHtml(st.observed_at)}</div>
          <div class="station-metrics-row">
            <span>${SVG_ICONS.thermometer} <strong>${escapeHtml(st.temp_c)}°C</strong></span>
            <span>${SVG_ICONS.rain} <strong>${escapeHtml(st.precip_1h_mm)} mm</strong></span>
            ${windPart}
          </div>
          <div>
            <button type="button" class="btn-action btn-omirl-chart" style="margin-top:0.2rem;"
              data-station-code="${escapeHtml(st.code)}" data-sensor="${escapeHtml(defaultSensor)}">
              ${SVG_ICONS.chart} Curva 24h OMIRL (${escapeHtml(defaultSensor)})
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
            <div class="station-name">${escapeHtml(hy.name)} <span class="station-code">(${escapeHtml(hy.code)})</span></div>
            <span class="station-dist">${escapeHtml(hy.distance_km)} km</span>
          </div>
          <div class="station-meta-line">Bacino: <strong>${escapeHtml(hy.river)}</strong> (${escapeHtml(hy.municipality || hy.muni || "GE")}) • Ore ${escapeHtml(hy.observed_at)}</div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-top:0.15rem;">
            <span class="hydro-level-val">Livello: ${hy.level_m} m</span>
            <span class="badge-pill ${pillClass}">${hy.status_level === "green" ? "Regolare" : "Guardia idro"}</span>
          </div>
          <!-- Barra Graduata Idrometrica con Tacche Soglia Gialla e Rossa -->
          <div class="hydro-gauge-track" title="Livello ${hy.level_m}m su scala ${maxScale.toFixed(1)}m">
            <div class="hydro-gauge-fill" style="width:${fillPct}%;background:${barColor};"></div>
            <div class="hydro-threshold-mark" style="left:${warnPct}%;background:#fbbf24;" title="Soglia gialla: ${hy.warn_threshold_m}m"></div>
            <div class="hydro-threshold-mark" style="left:${alarmPct}%;background:#ef4444;" title="Soglia rossa: ${hy.alarm_threshold_m}m"></div>
          </div>
          <div class="hydro-thresholds-row">
            <span>0.0 m</span>
            <span style="color:#fbbf24;">Gialla ${hy.warn_threshold_m} m</span>
            <span style="color:#f87171;">Rossa ${hy.alarm_threshold_m} m</span>
          </div>
        </div>
      `;
    })
    .join("");

  // 3. Galleria Webcam Live (Solo Immagine JPEG Live OMIRL o pannello telemetrico piatto senza grafiche finte)
  const camGrid = document.getElementById("live-webcams-grid");
  const cams = obs.nearest_webcams || [];
  const hs = seaCond?.waves?.significant_height_m ?? 0.4;
  const windKt = seaCond?.wind?.speed_knots ?? 6;

  camGrid.innerHTML = cams
    .map((cam) => {
      const safeCamUrl = sanitizeHttpUrl(cam.live_image_url);
      const previewStyle = safeCamUrl
        ? `background: linear-gradient(180deg, rgba(10,13,20,0.18) 0%, rgba(10,13,20,0.88) 100%), url('${safeCamUrl}') center/cover no-repeat;`
        : `background: #0d1522;`;
      return `
        <div class="webcam-card">
          <div class="webcam-preview" style="${previewStyle}">
            <div style="display:flex;justify-content:space-between;align-items:center;z-index:2;gap:0.4rem;">
              <span class="badge-pill ${safeCamUrl ? "level-green" : "level-physics"}">
                ${SVG_ICONS.camera} ${safeCamUrl ? "Immagine live OMIRL" : "Feed esterno"}
              </span>
              <span class="webcam-dist-tag">
                a ${escapeHtml(cam.distance_km)} km
              </span>
            </div>
            <div style="z-index:2;">
              <div style="font-size:0.95rem;font-weight:600;color:#e9edf3;text-shadow:0 1px 4px rgba(0,0,0,0.9);">${escapeHtml(cam.name)}</div>
              <div style="font-size:0.8125rem;color:#e9edf3;margin-top:0.15rem;">Direzione: ${escapeHtml(cam.view_direction)}</div>
              <div style="font-size:0.8125rem;color:#5ab9fc;margin-top:0.15rem;font-variant-numeric:tabular-nums;">
                Condizioni: ${cur?.temp_c?.toFixed(1) ?? "--"}°C • Vento ${windKt} kt • Onda Hs ${hs}m
              </div>
            </div>
          </div>
          <div class="webcam-body">
            <div style="display:flex;justify-content:space-between;color:var(--p-muted);font-size:0.8125rem;">
              <span>Fonte: ${cam.provider}</span>
              <span>${cam.timestamp_label}</span>
            </div>
            <a href="${cam.live_image_url || cam.portal_url}" target="_blank" rel="noopener" class="btn-action" style="justify-content:center;margin-top:0.2rem;">
              ${SVG_ICONS.external} Apri ${cam.live_image_url ? "foto reale HD / portale" : "stream live ufficiale"}
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
            step.rain_rate_mm_h > 0.2 ? "var(--p-accent)" : "var(--p-muted)"
          }; font-weight: 500;">
            ${SVG_ICONS.rain} ${step.rain_rate_mm_h.toFixed(1)} mm/h
          </div>
          <div class="nowcast-meta">${SVG_ICONS.wind} ${windStr}</div>
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

  // Pannello Terra: Fisica + Indicatori Operativi
  const landPanel = document.getElementById("panel-land-details");
  const seaPanel = document.getElementById("panel-sea-details");
  if (landPanel && seaPanel) {
    const isSea = state.mode === "sea";
    landPanel.hidden = isSea;
    seaPanel.hidden = !isSea;
    if (landPanel.parentElement) {
      landPanel.parentElement.style.gridTemplateColumns = "1fr";
    }
  }

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
        <span class="risk-item-title-label">${SVG_ICONS.gauge} Bacini idrografici &amp; sottopassi (Bisagno, Polcevera, Entella, Stura)</span>
        <span>${landRisk.hydrogeological.precip_1h_mm} mm/h</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.hydrogeological.label}:</strong> ${landRisk.hydrogeological.advice}</div>
    </div>

    <div class="risk-item border-${convBorder}">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.spark} Linea di convergenza ligure (Tramontana scura vs Scirocco)</span>
        <span>Score ${conv.convergence_score}/100</span>
      </div>
      <div class="risk-item-desc"><strong>${conv.status}:</strong> ${conv.explanation}</div>
    </div>

    <div class="risk-item border-${landRisk.wind_viability.level}">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.road} Viabilità urbana, Sopraelevata Aldo Moro &amp; viadotti A7/A10/A12/A26</span>
        <span>Raffica ${landRisk.wind_viability.gust_kmh} km/h</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.wind_viability.label}:</strong> ${landRisk.wind_viability.advice}</div>
    </div>

    <div class="risk-item border-${landRisk.appennino_passes.level}">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.mountain} Valichi appenninici (Giovi, Turchino, Scoffera, Bocco, Faiallo)</span>
        <span>ZT ~${landRisk.appennino_passes.freezing_level_m} m</span>
      </div>
      <div class="risk-item-desc"><strong>${landRisk.appennino_passes.label}:</strong> ${landRisk.appennino_passes.advice}</div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.thermometer} Termo-igrometria, punto di rugiada &amp; diagnostica maccaja ligure</span>
        <span>DP ${thermo.dew_point_c ?? "--"}°C | UV ${thermo.uv_index ?? "--"}</span>
      </div>
      <div class="risk-item-desc">
        Percepita: <strong>${thermo.perceived_temp_c ?? "--"}°C</strong> (${thermo.comfort_label || "Regolare"}) •
        Humidex: ${thermo.humidex ?? "--"} • Windchill: ${thermo.windchill_c ?? "--"}°C •
        Radiazione solare: ${thermo.solar_radiation_wm2 ?? "--"} W/m² •
        <strong>${thermo.maccaja_status || ""}</strong>
      </div>
    </div>
  `;

  // Pannello Mare: SOLO Fisica Costiera & Oceanografica Pura (zero semafori soggettivi — ADR-0006)
  const seaContainer = document.getElementById("sea-risk-items");
  const w = seaCond.waves;
  const wind = seaCond.wind;
  const cp = seaCond.coastal_physics;
  const bs = cp.bay_surge;
  const td = cp.tides;
  const cur = cp.surface_current;

  const tideExtremaStr = (td.extrema || [])
    .slice(0, 4)
    .map((ex) => `${ex.type === "HIGH" ? "Alta" : "Bassa"} ${ex.time} (${ex.height_cm} cm)`)
    .join(" • ");

  seaContainer.innerHTML = `
    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.wind} Cinematica del vento &amp; scala Beaufort</span>
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
        <span class="risk-item-title-label">${SVG_ICONS.wave} Spettro completo dell'onda (Hs, Hmax, H1/1000, periodo Tp &amp; ripidità)</span>
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
        <span class="risk-item-title-label">${SVG_ICONS.layers} Partizione spettrale: onda viva da vento vs swell lungo</span>
        <span>Hwind ${w.wind_wave_height_m} m | Hswell ${w.swell_height_m} m</span>
      </div>
      <div class="risk-item-desc">
        • <strong>Onda viva da vento locale:</strong> ${w.wind_wave_height_m} m @ ${w.wind_wave_period_s} s da ${w.wind_wave_cardinal} (${w.wind_wave_dir_deg}°)<br>
        • <strong>Swell primario (mare lungo):</strong> ${w.swell_height_m} m @ ${w.swell_period_s} s da ${w.swell_cardinal} (${w.swell_dir_deg}°)
      </div>
    </div>

    <div class="risk-item border-physics">
      <div class="risk-item-title">
        <span class="risk-item-title-label">${SVG_ICONS.anchor} Fisica costiera di rada: rifrazione (Kr), shoaling (Ks) &amp; risacca a riva</span>
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
        <span class="risk-item-title-label">${SVG_ICONS.clock} Curva di marea${td.is_synthetic ? " (stimata)" : ""}, corrente superficiale &amp; visibilità ottica</span>
        <span>${td.current_height_cm} cm (${td.current_phase})</span>
      </div>
      <div class="risk-item-desc">
        • <strong>Estremi di marea:</strong> ${tideExtremaStr || "In calcolo"} (Escursione ${td.range_cm} cm)<br>
        • <strong>Corrente superficiale:</strong> <strong>${cur.speed_knots} kt</strong> (${cur.speed_ms} m/s) verso ${cur.direction_cardinal} (drift vento ${cur.wind_drift_component_knots} kt)<br>
        • <strong>Temp. acqua (SST):</strong> ${w.sea_surface_temp_c}°C • <strong>Visibilità ottica:</strong> ${cp.visibility_nm} NM (${cp.visibility_m} m)
      </div>
    </div>
  `;
}

function renderWatchBanner(pkg) {
  const banner = document.getElementById("liguria-watch-banner");
  if (!banner || !pkg) return;

  const conv = pkg.nowcast?.ligurian_convergence || {};
  const windKt = pkg.sea?.marine_conditions?.wind?.speed_knots ?? 0;
  const hydros =
    pkg.observations_live?.all_river_hydrometers ||
    pkg.observations_live?.nearest_river_hydrometers ||
    [];
  const alertHydros = hydros.filter(
    (h) => h.status_level === "red" || h.status_level === "orange"
  );

  const reasons = [];
  let isRed = false;
  if (alertHydros.length) {
    if (alertHydros.some((h) => h.status_level === "red")) isRed = true;
    reasons.push(
      `Idrometri in guardia: ${alertHydros
        .slice(0, 3)
        .map((h) => `${h.name} (${h.level_m}m)`)
        .join(", ")}`
    );
  }
  if ((conv.convergence_score || 0) >= 50) {
    if ((conv.convergence_score || 0) >= 75) isRed = true;
    reasons.push(`Convergenza ligure ${conv.convergence_score}/100 (${conv.status || "attiva"})`);
  }
  if (windKt >= 34) {
    isRed = true;
    reasons.push(`Burrasca in mare (${windKt} kt)`);
  }

  if (!reasons.length) {
    banner.hidden = true;
    banner.className = "watch-banner";
    banner.textContent = "";
    return;
  }

  banner.className = isRed ? "watch-banner watch-red" : "watch-banner";
  banner.innerHTML = `<span><strong>Segnale operativo Liguria:</strong> ${escapeHtml(reasons.join(" • "))}</span>`;
  banner.hidden = false;
}

function render5ModelsHourlyTable(hourly48) {
  const summaryEl = document.getElementById("models-divergence-summary");
  if (summaryEl && hourly48 && hourly48.length) {
    const slice24 = hourly48.slice(0, 24);
    let maxSpread = slice24[0];
    let maxLamRain = slice24[0];
    slice24.forEach((h) => {
      if ((h.model_spread?.wind_spread_knots ?? 0) > (maxSpread.model_spread?.wind_spread_knots ?? 0)) {
        maxSpread = h;
      }
      if ((h.precip_max_lam_mm ?? 0) > (maxLamRain.precip_max_lam_mm ?? 0)) {
        maxLamRain = h;
      }
    });
    const maxSpreadKt = maxSpread.model_spread?.wind_spread_knots ?? 0;
    const spreadTime = (maxSpread.time.split("T")[1] || maxSpread.time).slice(0, 5);
    const lamPeak = maxLamRain.precip_max_lam_mm ?? 0;
    const lamTime = (maxLamRain.time.split("T")[1] || maxLamRain.time).slice(0, 5);
    const agreementTxt =
      maxSpreadKt < 5
        ? `<strong>Accordo alto</strong> tra i 5 modelli nelle prossime 24h (Δ vento max ${escapeHtml(maxSpreadKt)} kt)`
        : `<strong>Divergenza vento max Δ ${escapeHtml(maxSpreadKt)} kt</strong> alle ${escapeHtml(spreadTime)}`;
    const rainTxt =
      lamPeak >= 1.0
        ? ` • Picco LAM pioggia: <strong>${escapeHtml(lamPeak)} mm/h</strong> alle ${escapeHtml(lamTime)}`
        : " • Precipitazioni assenti/deboli";
    summaryEl.innerHTML = `${agreementTxt}${rainTxt}`;
  }

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
        return `<strong>${obj.wind_knots} kt</strong> <span style="color:var(--p-muted);font-size:0.8125rem;">(r.${obj.gust_knots ?? "--"})</span>`;
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
          <td style="color:${spreadColor};font-weight:600;">Δ ${spreadKt} kt</td>
          <td>${h.precip_mm} mm <span style="color:#5ab9fc;font-size:0.8125rem;">(max ${h.precip_max_lam_mm})</span></td>
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
        <div class="kpi-label">Distanza costiera (andata / A+R)</div>
        <div class="kpi-value">${plan.one_way_distance_nm} / ${plan.total_distance_nm} NM</div>
        <div class="kpi-sub">Rotta su grafo che non taglia i capi</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Tempo navigazione effettivo</div>
        <div class="kpi-value">${plan.estimated_navigation_minutes} min</div>
        <div class="kpi-sub">+ ${plan.planned_stop_minutes} min sosta = ${plan.estimated_total_minutes} min tot</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Velocità media richiesta</div>
        <div class="kpi-value">${plan.required_average_speed_knots} kt</div>
        <div class="kpi-sub">Per rientrare in ${plan.planned_duration_minutes} min totali</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Orario limite rientro (turnaround)</div>
        <div class="kpi-value" style="color:#fbbf24;">${plan.schedule.latest_turnaround_time}</div>
        <div class="kpi-sub">ETA dest: ${plan.schedule.eta_destination} • Rientro: ${plan.schedule.eta_return_origin}</div>
      </div>
    `;

    const legsList = document.getElementById("route-legs-list");
    const legsHtml = (plan.legs || [])
      .map(
        (leg, i) => `
        <div class="risk-item border-physics">
          <div class="risk-item-title">
            <span>Tratta ${i + 1}: ${escapeHtml(leg.from_name)} → ${escapeHtml(leg.to_name)}</span>
            <span>${escapeHtml(leg.distance_nm)} NM</span>
          </div>
          <div class="risk-item-desc">
            ${
              leg.amp_speed_limit_knots
                ? `<span style="display:inline-flex;align-items:center;gap:4px;color:#fbbf24;">${SVG_ICONS.alert} <strong>Vincolo Area Marina Protetta (AMP Portofino):</strong> velocità limitata a <strong>max ${escapeHtml(leg.amp_speed_limit_knots)} kt</strong></span>`
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
          <span class="risk-item-title-label">${SVG_ICONS.compass} Confronto fisico andata vs ritorno</span>
          <span>Partenza ${escapeHtml(plan.schedule.departure_time)}</span>
        </div>
        <div class="risk-item-desc">${escapeHtml(cmp.delta_summary || "")}</div>
      </div>
    ` + legsHtml;

    if (state.map && plan.waypoints) {
      if (state.routePolyline) {
        state.map.removeLayer(state.routePolyline);
      }
      const latlngs = plan.waypoints.map((w) => [w.lat, w.lon]);
      state.routePolyline = L.polyline(latlngs, {
        color: "#5ab9fc",
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
      ? "Google Gemini — Analista sinottico"
      : "Motore sinottico fisico ligure";

    document.getElementById("ai-headline").textContent = bulletin.headline;
    document.getElementById("ai-synoptic-body").textContent =
      bulletin.synoptic_nowcast_analysis +
      "\n\n" +
      (bulletin.sea_operational_briefing || "");

    const takeawaysGrid = document.getElementById("ai-takeaways-grid");
    takeawaysGrid.innerHTML = (bulletin.key_takeaways || [])
      .map((item) => `<div class="ai-takeaway-item">${escapeHtml(item)}</div>`)
      .join("");
  }

  const arpalBox = document.getElementById("arpal-bulletin-box");
  const arpalBadge = document.getElementById("arpal-issued-badge");
  if (!arpalBox || !arpal) return;

  if (arpalBadge) {
    arpalBadge.textContent = arpal.live_extracted ? "ARPAL live" : "ARPAL sintesi";
  }

  const daysHtml = (arpal.days || [])
    .map(
      (d) => `
      <div class="risk-item border-physics">
        <div class="risk-item-title">
          <span class="risk-item-title-label">${SVG_ICONS.calendar} ${escapeHtml(d.label)}</span>
          <span>Zonizzazione Liguria</span>
        </div>
        <div class="risk-item-desc">
          <strong>Meteo:</strong> ${escapeHtml(d.forecast_text)}<br>
          <strong>Venti:</strong> ${escapeHtml(d.winds)}<br>
          <strong>Mare:</strong> ${escapeHtml(d.sea)}
        </div>
      </div>
    `
    )
    .join("");

  arpalBox.innerHTML =
    `
    <div class="risk-item border-green">
      <div class="risk-item-title">
        <span>Situazione sinottica regionale (${escapeHtml(arpal.source || "ARPAL")})</span>
        <span>${escapeHtml(arpal.issued_at || "")}</span>
      </div>
      <div class="risk-item-desc">${escapeHtml(arpal.synoptic_situation || "")}</div>
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
          label: "Temp consenso (°C)",
          data: consensusTemp,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.15)",
          yAxisID: "yTemp",
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 2,
        },
        {
          label: "AROME 1.3km pioggia (mm/h)",
          data: aromeRain,
          backgroundColor: "rgba(90, 185, 252, 0.82)",
          yAxisID: "yRain",
        },
        {
          label: "ICON-D2 2km pioggia (mm/h)",
          data: iconRain,
          backgroundColor: "rgba(16, 185, 129, 0.75)",
          yAxisID: "yRain",
        },
        {
          label: "ECMWF 9km pioggia (mm/h)",
          data: ecmwfRain,
          backgroundColor: "rgba(2, 132, 199, 0.72)",
          yAxisID: "yRain",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e9edf3", font: { size: 13, family: "IBM Plex Sans, sans-serif" } } },
      },
      scales: {
        x: { ticks: { color: "#8891a1" }, grid: { color: "rgba(233,237,243,0.07)" } },
        yRain: {
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "mm/h", color: "#5ab9fc" },
          ticks: { color: "#5ab9fc" },
          grid: { color: "rgba(233,237,243,0.09)" },
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
          label: useKnots ? "Vento medio (kt)" : "Vento medio (km/h)",
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
          label: "Onda significativa Hs (m)",
          data: waveHsSeries,
          borderColor: "#5ab9fc",
          backgroundColor: "rgba(90, 185, 252, 0.2)",
          fill: true,
          yAxisID: "yWave",
          tension: 0.35,
          borderWidth: 2.5,
        },
        {
          label: "Onda max statistica Hmax (m)",
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
        legend: { labels: { color: "#e9edf3", font: { size: 13, family: "IBM Plex Sans, sans-serif" } } },
      },
      scales: {
        x: { ticks: { color: "#8891a1" }, grid: { color: "rgba(233,237,243,0.07)" } },
        yWind: {
          position: "left",
          beginAtZero: true,
          title: {
            display: true,
            text: useKnots ? "Nodi (kt)" : "km/h",
            color: "#10b981",
          },
          ticks: { color: "#10b981" },
          grid: { color: "rgba(233,237,243,0.09)" },
        },
        yWave: {
          position: "right",
          beginAtZero: true,
          title: { display: true, text: "Onda (m)", color: "#5ab9fc" },
          ticks: { color: "#5ab9fc" },
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
          <td><span style="color:var(--p-muted)">${d.temp_min_c}°</span> / <strong>${d.temp_max_c}°C</strong></td>
          <td><strong>${d.precip_sum_mm} mm</strong> <span style="font-size:0.8125rem;color:#5ab9fc">(LAM max ${d.precip_max_model_mm} mm)</span></td>
          <td>${d.wind_dominant_name} (${d.wind_dominant_cardinal})</td>
          <td>${d.gust_max_kmh} km/h | <strong>${d.gust_max_knots} kt</strong> (F${d.beaufort_max})</td>
          <td><strong>Hs ${d.wave_max_hs_m}m</strong> (Hmax ${d.wave_max_hmax_m}m) @ ${d.wave_period_max_s}s — <em>${d.douglas_max_label}</em></td>
        </tr>
      `;
    })
    .join("");
}

document.addEventListener("DOMContentLoaded", initApp);
