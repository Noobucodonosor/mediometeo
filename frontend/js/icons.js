/**
 * Costanti UI e set di icone SVG inline (ADR-0008 / TASK-UX-03).
 */
export const LEVEL_LABELS = {
  green: "Regolare",
  yellow: "Attenzione / cautela",
  orange: "Criticità moderata-alta",
  red: "Allerta / criticità elevata",
};

export const SVG_ICONS = {
  radar: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.5"/><path d="M8 8l4-4"/></svg>`,
  wind: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 6h8.5a2 2 0 1 0-2-2"/><path d="M2 10h10.5a2 2 0 1 1-2 2"/><path d="M2 8h6"/></svg>`,
  camera: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="4.5" width="12" height="8.5" rx="1.5"/><circle cx="8" cy="8.75" r="2.2"/><path d="M5.5 4.5L6.5 3h3l1 1.5"/></svg>`,
  anchor: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="3.5" r="1.5"/><path d="M8 5v8.5M5 7.5h6M3.5 10.5a4.5 4.5 0 0 0 9 0"/></svg>`,
  play: `<svg class="ui-icon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M4.5 3.2L12.5 8l-8 4.8V3.2z"/></svg>`,
  pause: `<svg class="ui-icon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><rect x="4" y="3.2" width="3" height="9.6"/><rect x="9" y="3.2" width="3" height="9.6"/></svg>`,
  pin: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="4.5"/><circle cx="8" cy="8" r="1.2" fill="currentColor" stroke="none"/></svg>`,
  compass: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><polygon points="10.2,5.8 8.8,9.2 5.8,10.2 7.2,6.8" fill="currentColor" stroke="none"/></svg>`,
  station: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 13V6"/><circle cx="8" cy="5" r="1.5"/><path d="M4.8 7.8a4.5 4.5 0 0 1 0-5.6M11.2 2.2a4.5 4.5 0 0 1 0 5.6"/></svg>`,
  wave: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 6.5c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 3-1.5 4.5 0"/><path d="M1.5 10.5c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 3-1.5 4.5 0"/></svg>`,
  rain: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9.5h8a2.5 2.5 0 0 0 .3-5A3.5 3.5 0 0 0 5.6 3.8 2.8 2.8 0 0 0 4 9.5z"/><path d="M5.5 11.8l-.8 2M8.5 11.8l-.8 2M11.5 11.8l-.8 2"/></svg>`,
  thermometer: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 9.2V3.5a1.5 1.5 0 0 0-3 0v5.7a2.8 2.8 0 1 0 3 0z"/></svg>`,
  mountain: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 13L6 4.5l3.5 5 2-2.5L14.5 13H1.5z"/></svg>`,
  alert: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2.2L14 13H2L8 2.2z"/><path d="M8 6.5v3M8 11.3v.2"/></svg>`,
  chart: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12.5h12"/><polyline points="2.5,10 6,6.5 9,8.5 13.5,3.5"/></svg>`,
  external: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 2.5h4v4M13.5 2.5L7 9M6.5 4H3.5a1 1 0 0 0-1 1v7.5a1 1 0 0 0 1 1H11a1 1 0 0 0 1-1v-3"/></svg>`,
  spark: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2v12M2 8h12M4.2 4.2l7.6 7.6M11.8 4.2l-7.6 7.6"/></svg>`,
  layers: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="8,2 14.5,5.5 8,9 1.5,5.5"/><path d="M1.5 8.5L8 12l6.5-3.5M1.5 11.2L8 14.5l6.5-3.3"/></svg>`,
  clock: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/></svg>`,
  calendar: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="12" height="11" rx="1.2"/><path d="M5 1.5v3M11 1.5v3M2 6.5h12"/></svg>`,
  gauge: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5v11M3 5h2.5M3 8h3.5M3 11h2.5"/><path d="M7.5 11.5c1.2-1 2.4-1 3.6 0s2.4 1 3.4 0"/></svg>`,
  road: `<svg class="ui-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 2L2.5 14M11 2l2.5 12M8 3.5v2M8 8v2M8 12.2v1.5"/></svg>`,
};
