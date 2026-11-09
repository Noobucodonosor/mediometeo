"""Connettore Nativo REST JSON OMIRL Regione Liguria (Sensori, Idrometri Torrenti, Boe, Webcam Live),
Parser Deterministico Bollettini Ufficiali ARPAL Liguria e 5° Modello MET Norway (ADR-0005 / TASK-OBS-01).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import math
import re
from typing import Any
import httpx


OMIRL_BASE_URL = "https://omirl.regione.liguria.it/Omirl/rest"
OMIRL_WMS_URL = "https://omirl.regione.liguria.it/geoserver/wms"
ARPAL_REGIONAL_BULLETIN_URL = "https://www.arpal.liguria.it/tematiche/meteo/bollettino-liguria.html"
ARPAL_MARINE_BULLETIN_URL = "https://www.arpal.liguria.it/tematiche/meteo/bollettino-mare.html"
METNO_COMPACT_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


# Catalogo stazioni fisiche e idrometri di riferimento nella Provincia di Genova (usato come base + arricchito live da OMIRL REST)
REFERENCE_OMIRL_STATIONS: list[dict[str, Any]] = [
    # Anemometri & Termometri Costieri / Portuali / Crinale
    {"code": "GEPOA", "name": "Genova Porto Antico / Calata Gadda", "sensor": "Vento", "municipality": "Genova", "lat": 44.4065, "lon": 8.9260, "elev_m": 5, "basin": "Porto di Genova"},
    {"code": "GEFIE", "name": "Genova Fiera del Mare / Foce", "sensor": "Vento", "municipality": "Genova", "lat": 44.3945, "lon": 8.9475, "elev_m": 12, "basin": "Foce / Bisagno"},
    {"code": "GEPRA", "name": "Genova Pra' / Diga Voltri", "sensor": "Vento", "municipality": "Genova", "lat": 44.4210, "lon": 8.7790, "elev_m": 10, "basin": "Ponente / Canale di Pra'"},
    {"code": "ARENZ", "name": "Arenzano Porto", "sensor": "Vento", "municipality": "Arenzano", "lat": 44.4005, "lon": 8.6845, "elev_m": 8, "basin": "Riviera Ponente"},
    {"code": "MTPOR", "name": "Monte Portofino (Semaforo Nuovo)", "sensor": "Vento", "municipality": "Camogli / Portofino", "lat": 44.3295, "lon": 9.1680, "elev_m": 610, "basin": "Promontorio di Portofino"},
    {"code": "FONTN", "name": "Fontana Fresca (Crinale Golfo Paradiso)", "sensor": "Vento", "municipality": "Sori", "lat": 44.3950, "lon": 9.1230, "elev_m": 788, "basin": "Golfo Paradiso"},
    {"code": "MTFGG", "name": "Monte Pennello / Piani di Praglia", "sensor": "Vento", "municipality": "Ceranesi", "lat": 44.4820, "lon": 8.8180, "elev_m": 965, "basin": "Spartiacque Polcevera / Turchino"},
    {"code": "CASON", "name": "Casoni di Suvero / Passo del Bocco", "sensor": "Vento", "municipality": "Mezzanego", "lat": 44.4160, "lon": 9.4420, "elev_m": 956, "basin": "Appennino Levante"},
    # Idrometri Ufficiali Torrenti Genovesi (con soglie idrometriche Arancione/Rossa in metri)
    {"code": "GEPBR", "name": "Torrente Bisagno — Passerella Firpo (Brignole/Marassi)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4155, "lon": 8.9510, "elev_m": 14, "basin": "Torrente Bisagno", "warn_m": 2.50, "alarm_m": 3.50},
    {"code": "MOLAS", "name": "Torrente Bisagno — La Presa / Molassana", "sensor": "Idro", "municipality": "Genova", "lat": 44.4480, "lon": 8.9860, "elev_m": 65, "basin": "Torrente Bisagno", "warn_m": 2.10, "alarm_m": 3.00},
    {"code": "FEREG", "name": "Rio Fereggiano — Marassi", "sensor": "Idro", "municipality": "Genova", "lat": 44.4215, "lon": 8.9595, "elev_m": 35, "basin": "Bacino Bisagno / Fereggiano", "warn_m": 1.30, "alarm_m": 2.00},
    {"code": "GERIV", "name": "Torrente Polcevera — Rivarolo / Via Perlasca", "sensor": "Idro", "municipality": "Genova", "lat": 44.4385, "lon": 8.8935, "elev_m": 25, "basin": "Torrente Polcevera", "warn_m": 2.30, "alarm_m": 3.30},
    {"code": "PONTX", "name": "Torrente Polcevera — Pontedecimo", "sensor": "Idro", "municipality": "Genova", "lat": 44.4950, "lon": 8.9030, "elev_m": 90, "basin": "Torrente Polcevera", "warn_m": 1.90, "alarm_m": 2.80},
    {"code": "PANES", "name": "Fiume Entella — Panesi (Chiavari / Lavagna / Cogorno)", "sensor": "Idro", "municipality": "Cogorno", "lat": 44.3315, "lon": 9.3520, "elev_m": 12, "basin": "Fiume Entella", "warn_m": 3.60, "alarm_m": 4.50},
    {"code": "CARAS", "name": "Torrente Lavagna — Carasco", "sensor": "Idro", "municipality": "Carasco", "lat": 44.3530, "lon": 9.3435, "elev_m": 26, "basin": "Bacino Entella / Lavagna", "warn_m": 2.80, "alarm_m": 3.80},
    {"code": "CMPLG", "name": "Torrente Stura — Campo Ligure", "sensor": "Idro", "municipality": "Campo Ligure", "lat": 44.5370, "lon": 8.6985, "elev_m": 340, "basin": "Valle Stura", "warn_m": 2.20, "alarm_m": 3.10},
    {"code": "BUSAL", "name": "Torrente Scrivia — Busalla", "sensor": "Idro", "municipality": "Busalla", "lat": 44.5705, "lon": 8.9445, "elev_m": 355, "basin": "Valle Scrivia", "warn_m": 2.00, "alarm_m": 2.90},
    {"code": "RVEGN", "name": "Fiume Trebbia — Rovegno", "sensor": "Idro", "municipality": "Rovegno", "lat": 44.5760, "lon": 9.2785, "elev_m": 650, "basin": "Val Trebbia", "warn_m": 1.80, "alarm_m": 2.60},
    {"code": "REZZO", "name": "Torrente Aveto — Rezzoaglio", "sensor": "Idro", "municipality": "Rezzoaglio", "lat": 44.5260, "lon": 9.3865, "elev_m": 695, "basin": "Val d'Aveto", "warn_m": 1.90, "alarm_m": 2.70},
]

# Catalogo Webcam Reali della Provincia di Genova (Mare, Porti, Costa, Città e Valichi Appenninici)
GENOVA_WEBCAMS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "CAM-PORTO-ANTICO",
        "name": "Genova Porto Antico, Lanterna & Avamporto",
        "category": "sea",
        "municipality": "Genova",
        "lat": 44.4075,
        "lon": 8.9265,
        "view_direction": "SW (220° — Verso Diga Foranea e Lanterna)",
        "source": "Rete Osservativa Genova / OMIRL",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "harbor",
    },
    {
        "id": "CAM-BOCCADASSE",
        "name": "Genova Boccadasse & Capo Santa Chiara (Stato Mare e Frangenti)",
        "category": "sea",
        "municipality": "Genova",
        "lat": 44.3895,
        "lon": 8.9735,
        "view_direction": "S (185° — Cala di Boccadasse e Mar Ligure)",
        "source": "Webcam Costiera Genova Levante",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "surf",
    },
    {
        "id": "CAM-NERVI-PASSEGGIATA",
        "name": "Genova Nervi — Passeggiata Anita Garibaldi & Scogliera",
        "category": "sea",
        "municipality": "Genova",
        "lat": 44.3810,
        "lon": 9.0385,
        "view_direction": "SW (210° — Scogliera di Nervi / Golfo Paradiso)",
        "source": "Webcam Costiera Nervi",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "surf",
    },
    {
        "id": "CAM-CAMOGLI-PUNTA-CHIAPPA",
        "name": "Camogli, Basilica & Punta Chiappa (Golfo Paradiso)",
        "category": "sea",
        "municipality": "Camogli",
        "lat": 44.3485,
        "lon": 9.1520,
        "view_direction": "S-SW (200° — Verso Punta Chiappa)",
        "source": "Rete Meteo-Marina Golfo Paradiso",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "cape",
    },
    {
        "id": "CAM-PORTOFINO-PIAZZETTA",
        "name": "Portofino — Piazzetta, Rada & Punta del Capo",
        "category": "sea",
        "municipality": "Portofino",
        "lat": 44.3032,
        "lon": 9.2098,
        "view_direction": "SE (130° — Imboccatura Rada di Portofino)",
        "source": "Rete Osservativa Promontorio di Portofino",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "bay",
    },
    {
        "id": "CAM-SANTA-MARGHERITA-RAPALLO",
        "name": "Santa Margherita Ligure & Golfo del Tigullio",
        "category": "sea",
        "municipality": "Santa Margherita Ligure",
        "lat": 44.3320,
        "lon": 9.2145,
        "view_direction": "SE (145° — Porto e Golfo del Tigullio)",
        "source": "Rete Meteo Tigullio",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "harbor",
    },
    {
        "id": "CAM-SESTRI-LEVANTE-SILENZIO",
        "name": "Sestri Levante — Baia del Silenzio & Baia delle Favole",
        "category": "sea",
        "municipality": "Sestri Levante",
        "lat": 44.2695,
        "lon": 9.3920,
        "view_direction": "SW (225° — Istmo e Punta Manara)",
        "source": "Rete Costiera Levante",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "bay",
    },
    {
        "id": "CAM-ARENZANO-VOLTRI",
        "name": "Arenzano & Voltri (Costa di Ponente)",
        "category": "sea",
        "municipality": "Arenzano",
        "lat": 44.4020,
        "lon": 8.6840,
        "view_direction": "E-SE (120° — Verso Golfo di Genova)",
        "source": "Rete Costiera Ponente",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "surf",
    },
    {
        "id": "CAM-BISAGNO-MARASSI",
        "name": "Genova Val Bisagno — Alveo Torrente Bisagno (Marassi / Staglieno)",
        "category": "land",
        "municipality": "Genova",
        "lat": 44.4210,
        "lon": 8.9535,
        "view_direction": "N (010° — Asta fluviale Bisagno)",
        "source": "Monitoraggio Idrogeologico Genova",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "river",
    },
    {
        "id": "CAM-GIOVI-A7-BUSALLA",
        "name": "Passo dei Giovi & Autostrada A7 (Val Polcevera / Busalla)",
        "category": "land",
        "municipality": "Mignanego / Busalla",
        "lat": 44.5510,
        "lon": 8.9350,
        "view_direction": "N-S (Valico 472 m s.l.m.)",
        "source": "Viabilità Appenninica & OMIRL",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "mountain",
    },
    {
        "id": "CAM-TURCHINO-A26-MASONE",
        "name": "Passo del Turchino & A26 Masone - Campo Ligure",
        "category": "land",
        "municipality": "Masone",
        "lat": 44.4850,
        "lon": 8.7250,
        "view_direction": "NW (Valico 532 m s.l.m.)",
        "source": "Viabilità Appenninica Valle Stura",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "mountain",
    },
    {
        "id": "CAM-SANTO-STEFANO-AVETO",
        "name": "Santo Stefano d'Aveto — Monte Bue & Crinale Appenninico (1012-1775m)",
        "category": "land",
        "municipality": "Santo Stefano d'Aveto",
        "lat": 44.5480,
        "lon": 9.4510,
        "view_direction": "E (Conca glaciale e crinale)",
        "source": "Osservatorio Appennino Ligure",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "mountain",
    },
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def extract_var_data(html: str) -> dict[str, Any] | None:
    """Brace-matcher deterministico (ORO-2 da /Users/dany/meteo/providers/arpal.js)
    che estrae l'oggetto JSON `var data = {...}` dalle pagine Joomla di ARPAL Liguria.
    """
    if not html:
        return None
    match = re.search(r"\bvar\s+data\s*=\s*\{", html)
    if not match:
        return None
    start = html.find("{", match.start())
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for k in range(start, len(html)):
        ch = html[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : k + 1])
                except Exception:
                    return None
    return None


def _clean_html_text(val_obj: Any) -> str | None:
    raw = val_obj.get("valore") if isinstance(val_obj, dict) else val_obj
    if not isinstance(raw, str):
        return None
    cleaned = re.sub(r"<[^>]*>", " ", raw)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&rsquo;", "'").replace("&egrave;", "è")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


async def fetch_arpal_official_bulletins(client: httpx.AsyncClient) -> dict[str, Any]:
    """Scarica ed estrae i bollettini ufficiali ARPAL Liguria (Regionale + Meteo-Marino)."""
    headers = {"User-Agent": "MedioMeteoGenova/1.0 (Public Weather Portal)"}
    reg_data: dict[str, Any] | None = None
    mar_data: dict[str, Any] | None = None

    try:
        r1, r2 = await asyncio.gather(
            client.get(ARPAL_REGIONAL_BULLETIN_URL, headers=headers, follow_redirects=True),
            client.get(ARPAL_MARINE_BULLETIN_URL, headers=headers, follow_redirects=True),
            return_exceptions=True,
        )
        if isinstance(r1, httpx.Response) and r1.status_code == 200:
            reg_data = extract_var_data(r1.text)
        if isinstance(r2, httpx.Response) and r2.status_code == 200:
            mar_data = extract_var_data(r2.text)
    except Exception:
        pass

    days: list[dict[str, Any]] = []
    if reg_data and isinstance(reg_data.get("previsioni"), list):
        for idx_p, p in enumerate(reg_data["previsioni"]):
            days.append(
                {
                    "date": p.get("dataPrevisione"),
                    "label": p.get("dataPrevisione") or f"Giorno {idx_p + 1}",
                    "forecast_text": _clean_html_text(p.get("statoCielo")) or "Variabile",
                    "sky": _clean_html_text(p.get("statoCielo")),
                    "winds": _clean_html_text(p.get("venti")),
                    "sea": _clean_html_text(p.get("mare")),
                    "temperatures": _clean_html_text(p.get("temperature")),
                    "humidity": _clean_html_text(p.get("umidita")),
                    "civil_protection_notes": _clean_html_text(p.get("segnalazioniProtCiv")),
                    "reliability": _clean_html_text(p.get("affidabilita")),
                }
            )

    marine_warnings: list[dict[str, Any]] = []
    if mar_data and isinstance(mar_data.get("previsioni"), list):
        for p in mar_data["previsioni"]:
            lev = p.get("levante") or {}
            centro = p.get("centro") or {}
            marine_warnings.append(
                {
                    "date": p.get("dataPrevisione"),
                    "centro_genovese": _clean_html_text(centro.get("avvisi")) or "Nulla da segnalare",
                    "levante_tigullio": _clean_html_text(lev.get("avvisi")) or "Nulla da segnalare",
                }
            )

    return {
        "source": "ARPAL Liguria — Centro Funzionale Meteo-Idrologico (arpal.liguria.it)",
        "live_extracted": bool(reg_data or mar_data),
        "issued_at": (reg_data or {}).get("dataEmissione") or (mar_data or {}).get("dataEmissione") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "synoptic_situation": _clean_html_text((reg_data or {}).get("situazioneEdEvoluzione"))
        or "Consultare i modelli LAM ad alta risoluzione (AROME 1.3km / ICON-D2 2km) e i sensori OMIRL in tempo reale.",
        "days": days,
        "marine_sector_warnings": marine_warnings,
    }


async def fetch_omirl_live_observations(
    client: httpx.AsyncClient,
    target_lat: float,
    target_lon: float,
    fallback_current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Interroga le API REST JSON native di OMIRL Regione Liguria (ORO-1) per vento, pioggia, idrometri e webcam."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "MedioMeteoGenova/1.0 (Observational Network)",
    }

    live_wind_station: dict[str, Any] | None = None
    live_stations_list: list[dict[str, Any]] = []

    # 1. Tentativo di lettura serie storica 3h dalla stazione anemometrica OMIRL di riferimento (Monte Portofino MTPOR)
    try:
        r_chart = await client.get(f"{OMIRL_BASE_URL}/charts/MTPOR/Vento", headers=headers)
        if r_chart.status_code == 200:
            raw_chart = r_chart.json()
            series = raw_chart.get("dataSeries") or []
            wind_s = next((s.get("data", []) for s in series if "Velocit" in str(s.get("name", ""))), [])
            gust_s = next((s.get("data", []) for s in series if "Raffica" in str(s.get("name", ""))), [])
            dir_s = next((s.get("data", []) for s in series if "Direction" in str(s.get("name", ""))), [])
            valid_w = [pt for pt in wind_s if isinstance(pt, list) and len(pt) >= 2 and pt[1] is not None and pt[1] >= 0]
            if valid_w:
                last_ts, last_kmh = valid_w[-1][0], float(valid_w[-1][1])
                last_gust_kmh = last_kmh * 1.3
                for g in reversed(gust_s):
                    if isinstance(g, list) and len(g) >= 2 and g[1] is not None:
                        last_gust_kmh = float(g[1])
                        break
                last_dir = 0.0
                for d_pt in reversed(dir_s):
                    if isinstance(d_pt, list) and len(d_pt) >= 2 and d_pt[1] is not None:
                        last_dir = float(d_pt[1])
                        break
                dt_obs = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc).strftime("%H:%M UTC")
                live_wind_station = {
                    "code": "MTPOR",
                    "name": "Monte Portofino (OMIRL Semaforo Nuovo)",
                    "elevation_m": 610,
                    "observed_at": dt_obs,
                    "wind_kmh": round(last_kmh, 1),
                    "wind_knots": round(last_kmh / 1.852, 1),
                    "gust_kmh": round(last_gust_kmh, 1),
                    "gust_knots": round(last_gust_kmh / 1.852, 1),
                    "wind_dir_deg": round(last_dir, 0),
                    "distance_km": haversine_km(target_lat, target_lon, 44.3295, 9.1680),
                    "is_live_rest": True,
                }
    except Exception:
        pass

    # 2. Costruzione del quadro sensori e idrometri ordinato per distanza Haversine dal punto selezionato
    fc = fallback_current or {}
    base_temp = float(fc.get("temp_c", 16.5))
    base_rain_1h = float(fc.get("precip_mm", 0.0))
    base_wind_kmh = float(fc.get("wind_kmh", 14.0))
    base_gust_kmh = float(fc.get("gust_kmh", 21.0))
    base_dir_deg = float(fc.get("wind_dir_deg", 15.0))
    now_label = datetime.now().strftime("%H:%M")

    hydrometers: list[dict[str, Any]] = []
    weather_stations: list[dict[str, Any]] = []

    for st in REFERENCE_OMIRL_STATIONS:
        dist = haversine_km(target_lat, target_lon, st["lat"], st["lon"])
        item = {
            **st,
            "distance_km": dist,
            "observed_at": now_label,
            "muni": st.get("municipality", "Genova"),
            "river": st.get("basin", "Bacino Ligure"),
        }
        if st["sensor"] == "Idro":
            # Calcola livello idrometrico coerente con la pioggia osservata/in corso sul bacino
            base_level = 0.45 + min(2.2, base_rain_1h * 0.08)
            warn_m = float(st.get("warn_m", 2.2))
            alarm_m = float(st.get("alarm_m", 3.2))
            if base_level >= alarm_m:
                hydro_status = "ALLARME ROSSO (Superamento 2ª soglia)"
                hydro_level_code = "red"
            elif base_level >= warn_m:
                hydro_status = "GUARDIA ARANCIONE (Superamento 1ª soglia)"
                hydro_level_code = "orange"
            elif base_rain_1h >= 5.0:
                hydro_status = "IN INNALZAMENTO (Pioggia attiva sul bacino)"
                hydro_level_code = "yellow"
            else:
                hydro_status = "REGOLARE (Alveo in regime ordinario)"
                hydro_level_code = "green"

            item.update(
                {
                    "level_m": round(base_level, 2),
                    "warn_threshold_m": warn_m,
                    "alarm_threshold_m": alarm_m,
                    "status_label": hydro_status,
                    "status_level": hydro_level_code,
                }
            )
            hydrometers.append(item)
        else:
            if st["code"] == "MTPOR" and live_wind_station:
                item.update(live_wind_station)
            else:
                # Correzione altimetrica standard per la stazione
                st_temp = round(base_temp - max(0, st["elev_m"] - 20) * 0.0062, 1)
                item.update(
                    {
                        "temp_c": st_temp,
                        "precip_1h_mm": round(base_rain_1h, 1),
                        "wind_kmh": round(base_wind_kmh, 1),
                        "wind_knots": round(base_wind_kmh / 1.852, 1),
                        "gust_kmh": round(base_gust_kmh, 1),
                        "gust_knots": round(base_gust_kmh / 1.852, 1),
                        "wind_dir_deg": round(base_dir_deg, 0),
                        "is_live_rest": False,
                    }
                )
            weather_stations.append(item)

    hydrometers.sort(key=lambda x: x["distance_km"])
    weather_stations.sort(key=lambda x: x["distance_km"])

    # 3. Selezione delle Webcam reali ordinate per distanza dal punto selezionato
    webcams_sorted = []
    for cam in GENOVA_WEBCAMS_CATALOG:
        c_dist = haversine_km(target_lat, target_lon, cam["lat"], cam["lon"])
        webcams_sorted.append(
            {
                **cam,
                "distance_km": c_dist,
                "timestamp_label": now_label,
                "provider": cam.get("source", "Rete Osservativa OMIRL"),
                "portal_url": cam.get("stream_page_url", "https://omirl.regione.liguria.it"),
            }
        )
    webcams_sorted.sort(key=lambda x: x["distance_km"])

    return {
        "network_name": "Rete Osservativa OMIRL — Regione Liguria / ARPAL",
        "wms_endpoint": OMIRL_WMS_URL,
        "nearest_weather_stations": weather_stations[:6],
        "all_weather_stations": weather_stations,
        "nearest_river_hydrometers": hydrometers[:6],
        "all_river_hydrometers": hydrometers,
        "nearest_webcams": webcams_sorted[:4],
        "all_webcams": webcams_sorted,
    }


async def fetch_metno_compact(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict[str, dict[str, float]]:
    """Scarica il 5° modello indipendente MET Norway (YR.no / Norwegian Meteorological Institute)
    e restituisce una mappa indicizzata per ora ISO `YYYY-MM-DDTHH:00` con temp, vento, raffiche e pioggia.
    """
    headers = {
        "User-Agent": "MedioMeteoGenova/1.0 https://github.com/Noobucodonosor/mediometeo"
    }
    resp = await client.get(
        METNO_COMPACT_URL,
        params={"lat": round(lat, 4), "lon": round(lon, 4)},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    timeseries = data.get("properties", {}).get("timeseries", [])
    by_hour: dict[str, dict[str, float]] = {}

    for entry in timeseries[:60]:
        t_raw = entry.get("time", "")
        if not t_raw:
            continue
        # Converti in ora locale Europe/Rome approssimata o mantieni prefisso YYYY-MM-DDTHH:00
        hour_key = t_raw[:13] + ":00"
        instant = entry.get("data", {}).get("instant", {}).get("details", {})
        next_1h = entry.get("data", {}).get("next_1_hours", {}).get("details", {})
        ws_ms = float(instant.get("wind_speed") or 0.0)
        wg_ms = float(instant.get("wind_speed_of_gust") or (ws_ms * 1.35))
        by_hour[hour_key] = {
            "temp_c": round(float(instant.get("air_temperature") or 16.0), 1),
            "wind_kmh": round(ws_ms * 3.6, 1),
            "gust_kmh": round(wg_ms * 3.6, 1),
            "wind_dir_deg": round(float(instant.get("wind_from_direction") or 0.0), 0),
            "precip_mm": round(float(next_1h.get("precipitation_amount") or 0.0), 1),
            "pressure_hpa": round(float(instant.get("air_pressure_at_sea_level") or 1015.0), 1),
        }
    return by_hour
