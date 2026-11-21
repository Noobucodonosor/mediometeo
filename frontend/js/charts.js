/**
 * Rendering grafici meteogrammi multi-modello & vento/moto ondoso via Chart.js (v3.0).
 */
export function renderCharts(hourly48, appState) {
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
  if (appState.chartMultiModel) appState.chartMultiModel.destroy();

  appState.chartMultiModel = new Chart(ctx1, {
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

  const useKnots = appState.mode === "sea";
  const windSeries = slice24.map((h) => (useKnots ? h.wind_knots : h.wind_kmh));
  const gustSeries = slice24.map((h) => (useKnots ? h.gust_knots : h.gust_kmh));
  const waveHsSeries = slice24.map((h) => h.wave_hs_m);
  const waveHmaxSeries = slice24.map((h) => h.wave_hmax_m);

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
