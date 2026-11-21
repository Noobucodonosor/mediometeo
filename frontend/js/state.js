/**
 * Stato applicativo centralizzato e gestione Preferiti localStorage (v3.0).
 */
export const FAV_STORAGE_KEY = "mediometeo_favorites_v1";
export const DEFAULT_FAVORITES = ["COM-GENOVA", "COM-PORTOFINO", "QRT-GENOVA-MARASSI", "COM-ARENZANO"];

export const state = {
  mode: "land",
  activeTab: "tab-mappa",
  selectedLocationId: "COM-GENOVA",
  customCoords: null,
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

export function loadFavorites() {
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

export function saveFavorites(ids) {
  try {
    localStorage.setItem(FAV_STORAGE_KEY, JSON.stringify(ids.slice(0, 5)));
  } catch (_) {}
}
