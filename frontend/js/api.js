/**
 * Client HTTP centralizzato verso gli endpoint FastAPI `/api/v1/*` (v4.0).
 */
export async function fetchLocationsCatalog() {
  const res = await fetch("/api/v1/locations");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchWeatherAndBulletin(appState, forceRefresh = false) {
  const params = new URLSearchParams();
  params.set("mode", appState.mode);
  if (forceRefresh) params.set("refresh", "true");

  if (appState.customCoords) {
    params.set("lat", appState.customCoords.lat);
    params.set("lon", appState.customCoords.lon);
  } else {
    params.set("location", appState.selectedLocationId);
  }

  const [forecastRes, aiRes] = await Promise.all([
    fetch(`/api/v1/forecast?${params.toString()}`),
    fetch(`/api/v1/ai-bulletin?${params.toString()}`),
  ]);

  return { forecastRes, aiRes };
}

export async function fetchCoastalRoute(params) {
  const res = await fetch(`/api/v1/route-eta?${params.toString()}`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchOmirlChart(code, sensor) {
  return fetch(
    `/api/v1/omirl-chart?code=${encodeURIComponent(code)}&sensor=${encodeURIComponent(sensor)}`
  );
}

export async function askPointQuestion({ question, location, lat, lon, mode }) {
  const res = await fetch("/api/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, location, lat, lon, mode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
