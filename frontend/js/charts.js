/**
 * Rendering meteogrammi Chart.js v4.0 adattivi a tema Chiaro / Scuro.
 */
export function renderCharts(hourly48, appState) {
  if (typeof Chart === "undefined" || !hourly48 || !hourly48.length) return;

  const isDark = appState.theme === "dark";
  const textCol = isDark ? "#e2e8f0" : "#0f172a";
  const mutedCol = isDark ? "#94a3b8" : "#64748b";
  const gridCol = isDark ? "rgba(241, 245, 249, 0.08)" : "rgba(15, 23, 42, 0.08)";

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
  if (appState.chartMultiModel) appState.chartMultiModel.destroy();

  appState.chartMultiModel = new Chart(ctx1, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "Temp (°C)",
          data: consensusTemp,
          borderColor: "#d97706",
          yAxisID: "yTemp",
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 1.5,
        },
        {
          label: "AROME (mm/h)",
          data: aromeRain,
          backgroundColor: "rgba(2, 132, 199, 0.8)",
          yAxisID: "yRain",
        },
        {
          label: "ICON-D2 (mm/h)",
          data: iconRain,
          backgroundColor: "rgba(16, 185, 129, 0.72)",
          yAxisID: "yRain",
        },
        {
          label: "ECMWF (mm/h)",
          data: ecmwfRain,
          backgroundColor: "rgba(99, 102, 241, 0.65)",
          yAxisID: "yRain",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: textCol, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: mutedCol }, grid: { color: gridCol } },
        yRain: { position: "left", beginAtZero: true, ticks: { color: "#0284c7" }, grid: { color: gridCol } },
        yTemp: { position: "right", ticks: { color: "#d97706" }, grid: { drawOnChartArea: false } },
      },
    },
  });

  const useKnots = appState.mode === "sea";
  const windSeries = slice24.map((h) => (useKnots ? h.wind_knots : h.wind_kmh));
  const gustSeries = slice24.map((h) => (useKnots ? h.gust_knots : h.gust_kmh));
  const waveHsSeries = slice24.map((h) => h.wave_hs_m);

  const canvas2 = document.getElementById("chart-wind-wave");
  if (!canvas2) return;
  const ctx2 = canvas2.getContext("2d");
  if (appState.chartWindWave) appState.chartWindWave.destroy();

  appState.chartWindWave = new Chart(ctx2, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: useKnots ? "Vento (kt)" : "Vento (km/h)",
          data: windSeries,
          borderColor: "#059669",
          yAxisID: "yWind",
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 1.5,
        },
        {
          label: useKnots ? "Raffiche (kt)" : "Raffiche (km/h)",
          data: gustSeries,
          borderColor: "#dc2626",
          borderDash: [4, 4],
          yAxisID: "yWind",
          tension: 0.3,
          borderWidth: 1.5,
          pointRadius: 0,
        },
        {
          label: "Onda Hs (m)",
          data: waveHsSeries,
          borderColor: "#0284c7",
          backgroundColor: "rgba(2, 132, 199, 0.14)",
          fill: true,
          yAxisID: "yWave",
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: textCol, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: mutedCol }, grid: { color: gridCol } },
        yWind: { position: "left", beginAtZero: true, ticks: { color: "#059669" }, grid: { color: gridCol } },
        yWave: { position: "right", beginAtZero: true, ticks: { color: "#0284c7" }, grid: { drawOnChartArea: false } },
      },
    },
  });
}
