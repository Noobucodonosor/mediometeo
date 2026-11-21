/**
 * Stato applicativo centralizzato v4.0 e Preferiti localStorage.
 */
export const FAV_STORAGE_KEY = "mediometeo_favorites_v1";
export const THEME_STORAGE_KEY = "mediometeo_theme_v4";
export const DEFAULT_FAVORITES = ["COM-GENOVA", "COM-PORTOFINO", "QRT-GENOVA-MARASSI", "COM-ARENZANO"];

export const state = {
  mode: "land",
  activeLayer: "wind", // 'wind' | 'radar' | 'waves' | 'stations'
  sheetState: "medium", // 'peek' | 'medium' | 'expanded'
  theme: "light", // 'light' | 'dark'
  selectedLocationId: "COM-GENOVA",
  customCoords: null,
  locations: [],
  ampZones: [],
  coastalWaypoints: [],
  weatherPkg: null,
  aiBulletin: null,
  routePlan: null,
  map: null,
  baseTileLayer: null,
  seamarkLayer: null,
  vectorLandLayer: null,
  radarLayer: null,
  radarPlaying: false,
  radarTimer: null,
  radarFrameIndex: 0,
  overlayGroup: null,
  routeGroup: null,
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
