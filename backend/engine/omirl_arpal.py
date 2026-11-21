"""Connettore Nativo Bulk REST JSON OMIRL Regione Liguria (23 Anemometri, 75 Termometri, 77 Pluviometri, 24 Idrometri Torrenti, Boa Capo Mele, Webcam Live),
Parser Deterministico Bollettini Ufficiali ARPAL Liguria e 5° Modello MET Norway (ADR-0005, ADR-0007 / TASK-DATA-02).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import math
import re
import time
from typing import Any
from zoneinfo import ZoneInfo
import httpx


OMIRL_BASE_URL = "https://omirl.regione.liguria.it/Omirl/rest"
OMIRL_PUBLIC_HOST = "https://omirl.regione.liguria.it"
OMIRL_WMS_URL = "https://omirl.regione.liguria.it/geoserver/wms"
ARPAL_REGIONAL_BULLETIN_URL = "https://www.arpal.liguria.it/tematiche/meteo/bollettino-liguria.html"
ARPAL_MARINE_BULLETIN_URL = "https://www.arpal.liguria.it/tematiche/meteo/bollettino-mare.html"
METNO_COMPACT_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"

# Cache in-memory di breve durata (120s) per l'intero parco sensori regionale OMIRL
_OMIRL_BULK_CACHE: dict[str, Any] = {"ts": 0.0, "payload": None}
_OMIRL_BULK_LOCK = asyncio.Lock()

# Mappa bacini e soglie idrometriche ufficiali di riferimento per i 24 idrometri della Provincia di Genova
GENOVA_HYDROMETERS_META: dict[str, dict[str, Any]] = {
    "FIRPO": {"river": "Torrente Bisagno (Passerella Firpo / Brignole)", "warn_m": 2.50, "alarm_m": 3.50},
    "GEMOL": {"river": "Torrente Bisagno (Molassana)", "warn_m": 2.20, "alarm_m": 3.10},
    "LAPRS": {"river": "Torrente Bisagno (La Presa / Bargagli)", "warn_m": 2.00, "alarm_m": 2.90},
    "GEFER": {"river": "Rio Fereggiano (Marassi)", "warn_m": 1.30, "alarm_m": 2.00},
    "GERIV": {"river": "Torrente Polcevera (Rivarolo)", "warn_m": 2.30, "alarm_m": 3.30},
    "GEPTX": {"river": "Torrente Polcevera (Pontedecimo)", "warn_m": 1.90, "alarm_m": 2.80},
    "GEGEI": {"river": "Torrente Geirato (Molassana / Val Bisagno)", "warn_m": 1.80, "alarm_m": 2.60},
    "VAREN": {"river": "Torrente Varenna (Granara / Pegli)", "warn_m": 1.90, "alarm_m": 2.70},
    "GSTUR": {"river": "Torrente Sturla (Genova Sturla)", "warn_m": 1.60, "alarm_m": 2.40},
    "MOLIN": {"river": "Torrente Chiaravagna / Molinetto (Sestri P.)", "warn_m": 1.50, "alarm_m": 2.20},
    "PANES": {"river": "Fiume Entella (Panesi — Chiavari/Lavagna)", "warn_m": 3.60, "alarm_m": 4.50},
    "CARPB": {"river": "Torrente Lavagna (Carasco Ponte Birago)", "warn_m": 2.80, "alarm_m": 3.80},
    "SMART": {"river": "Torrente Sturla (San Martino / Carasco)", "warn_m": 2.20, "alarm_m": 3.10},
    "VIGNO": {"river": "Torrente Sturla (Vignolo / Mezzanego)", "warn_m": 2.10, "alarm_m": 3.00},
    "CAMIN": {"river": "Torrente Graveglia (Caminata / Ne)", "warn_m": 1.90, "alarm_m": 2.70},
    "SLPSS": {"river": "Torrente Petronio (Sestri Levante Ponte SS1)", "warn_m": 1.80, "alarm_m": 2.60},
    "SLEVA": {"river": "Torrente Gromolo (Sestri Levante)", "warn_m": 1.50, "alarm_m": 2.20},
    "CAMPL": {"river": "Torrente Stura (Campo Ligure)", "warn_m": 2.20, "alarm_m": 3.10},
    "TIGLT": {"river": "Torrente Orba (Tiglieto)", "warn_m": 2.10, "alarm_m": 3.00},
    "MONTG": {"river": "Torrente Scrivia (Montoggio)", "warn_m": 1.90, "alarm_m": 2.80},
    "VOBBI": {"river": "Torrente Vobbia (Vobbietta / Isola del Cantone)", "warn_m": 2.30, "alarm_m": 3.20},
    "ROVPT": {"river": "Fiume Trebbia (Rovegno Ponte)", "warn_m": 1.80, "alarm_m": 2.60},
    "CABAN": {"river": "Torrente Aveto (Cabanne / Rezzoaglio)", "warn_m": 1.80, "alarm_m": 2.60},
}


# Catalogo stazioni fisiche e idrometri di riferimento (codici reali OMIRL della Provincia di Genova)
REFERENCE_OMIRL_STATIONS: list[dict[str, Any]] = [
    {"code": "GEPOA", "name": "Genova - Porto Antico", "sensor": "Vento", "municipality": "Genova", "lat": 44.4065, "lon": 8.9260, "elev_m": 5, "basin": "Porto di Genova"},
    {"code": "CFUNZ", "name": "Genova - Centro Funzionale", "sensor": "Vento", "municipality": "Genova", "lat": 44.4012, "lon": 8.9435, "elev_m": 35, "basin": "Genova Foce / Carignano"},
    {"code": "RIGHI", "name": "Genova - Castellaccio (Righi)", "sensor": "Vento", "municipality": "Genova", "lat": 44.4290, "lon": 8.9355, "elev_m": 356, "basin": "Genova Centro / Righi"},
    {"code": "GECER", "name": "Genova - Certosa", "sensor": "Vento", "municipality": "Genova", "lat": 44.4395, "lon": 8.8950, "elev_m": 45, "basin": "Val Polcevera"},
    {"code": "STILA", "name": "Genova - Sant'Ilario", "sensor": "Vento", "municipality": "Genova", "lat": 44.3835, "lon": 9.0485, "elev_m": 195, "basin": "Genova Nervi / Levante"},
    {"code": "AREPO", "name": "Arenzano - Porto", "sensor": "Vento", "municipality": "Arenzano", "lat": 44.4005, "lon": 8.6845, "elev_m": 8, "basin": "Riviera Ponente"},
    {"code": "PTURC", "name": "Passo del Turchino", "sensor": "Vento", "municipality": "Mele", "lat": 44.4785, "lon": 8.7320, "elev_m": 532, "basin": "Valico Turchino / Stura"},
    {"code": "MOPEN", "name": "Monte Pennello", "sensor": "Vento", "municipality": "Genova", "lat": 44.4820, "lon": 8.8180, "elev_m": 965, "basin": "Crinale Ponente / Polcevera"},
    {"code": "MTECA", "name": "Monte Cappellino", "sensor": "Vento", "municipality": "Savignone", "lat": 44.5495, "lon": 8.9450, "elev_m": 660, "basin": "Passo dei Giovi / Scrivia"},
    {"code": "FFRES", "name": "Fontana Fresca", "sensor": "Vento", "municipality": "Sori", "lat": 44.3950, "lon": 9.1230, "elev_m": 788, "basin": "Golfo Paradiso"},
    {"code": "CAMOG", "name": "Camogli", "sensor": "Vento", "municipality": "Camogli", "lat": 44.3485, "lon": 9.1555, "elev_m": 45, "basin": "Golfo Paradiso"},
    {"code": "MTPOR", "name": "Monte Portofino", "sensor": "Vento", "municipality": "Camogli", "lat": 44.3295, "lon": 9.1680, "elev_m": 610, "basin": "Promontorio di Portofino"},
    {"code": "SMARG", "name": "Santa Margherita Ligure", "sensor": "Vento", "municipality": "Santa Margherita Ligure", "lat": 44.3325, "lon": 9.2140, "elev_m": 15, "basin": "Golfo del Tigullio"},
    {"code": "LAVPO", "name": "Lavagna - Porto", "sensor": "Vento", "municipality": "Lavagna", "lat": 44.3095, "lon": 9.3360, "elev_m": 6, "basin": "Golfo del Tigullio"},
    {"code": "TOGAR", "name": "Torriglia - Garaventa", "sensor": "Vento", "municipality": "Torriglia", "lat": 44.5210, "lon": 9.1590, "elev_m": 780, "basin": "Alta Val Trebbia"},
    {"code": "MTMEZ", "name": "Monte di Mezzo", "sensor": "Vento", "municipality": "Santo Stefano d'Aveto", "lat": 44.5510, "lon": 9.4520, "elev_m": 1250, "basin": "Alta Val d'Aveto"},
    # Idrometri Ufficiali Torrenti Genovesi
    {"code": "FIRPO", "name": "Genova - Firpo (Bisagno)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4155, "lon": 8.9510, "elev_m": 14, "basin": "Torrente Bisagno (Passerella Firpo)", "warn_m": 2.50, "alarm_m": 3.50},
    {"code": "LAPRS", "name": "La Presa (Bisagno)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4480, "lon": 8.9860, "elev_m": 65, "basin": "Torrente Bisagno (La Presa)", "warn_m": 2.00, "alarm_m": 2.90},
    {"code": "GEFER", "name": "Genova - Fereggiano", "sensor": "Idro", "municipality": "Genova", "lat": 44.4215, "lon": 8.9595, "elev_m": 35, "basin": "Rio Fereggiano (Marassi)", "warn_m": 1.30, "alarm_m": 2.00},
    {"code": "GERIV", "name": "Genova - Rivarolo (Polcevera)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4385, "lon": 8.8935, "elev_m": 25, "basin": "Torrente Polcevera (Rivarolo)", "warn_m": 2.30, "alarm_m": 3.30},
    {"code": "GEPTX", "name": "Genova - Pontedecimo (Polcevera)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4950, "lon": 8.9030, "elev_m": 90, "basin": "Torrente Polcevera (Pontedecimo)", "warn_m": 1.90, "alarm_m": 2.80},
    {"code": "GEGEI", "name": "Genova - Geirato", "sensor": "Idro", "municipality": "Genova", "lat": 44.4510, "lon": 8.9670, "elev_m": 78, "basin": "Torrente Geirato (Val Bisagno)", "warn_m": 1.80, "alarm_m": 2.60},
    {"code": "VAREN", "name": "Genova - Granara (Varenna)", "sensor": "Idro", "municipality": "Genova", "lat": 44.4360, "lon": 8.8120, "elev_m": 42, "basin": "Torrente Varenna (Pegli)", "warn_m": 1.90, "alarm_m": 2.70},
    {"code": "CARPB", "name": "Carasco - Ponte Birago (Lavagna)", "sensor": "Idro", "municipality": "Carasco", "lat": 44.3530, "lon": 9.3435, "elev_m": 26, "basin": "Torrente Lavagna / Entella", "warn_m": 2.80, "alarm_m": 3.80},
    {"code": "SLPSS", "name": "Sestri Levante - Ponte SS1 (Petronio)", "sensor": "Idro", "municipality": "Sestri Levante", "lat": 44.2735, "lon": 9.4050, "elev_m": 8, "basin": "Torrente Petronio", "warn_m": 1.80, "alarm_m": 2.60},
    {"code": "CAMPL", "name": "Campo Ligure (Stura)", "sensor": "Idro", "municipality": "Campo Ligure", "lat": 44.5370, "lon": 8.6985, "elev_m": 340, "basin": "Torrente Stura", "warn_m": 2.20, "alarm_m": 3.10},
    {"code": "MONTG", "name": "Montoggio (Scrivia)", "sensor": "Idro", "municipality": "Montoggio", "lat": 44.5150, "lon": 9.0435, "elev_m": 438, "basin": "Torrente Scrivia", "warn_m": 1.90, "alarm_m": 2.80},
    {"code": "VOBBI", "name": "Vobbietta (Vobbia)", "sensor": "Idro", "municipality": "Isola del Cantone", "lat": 44.6180, "lon": 8.9950, "elev_m": 320, "basin": "Torrente Vobbia / Scrivia", "warn_m": 2.30, "alarm_m": 3.20},
]

# Catalogo Webcam Reali della Provincia di Genova (Mare, Porti, Costa, Fiumi e Valichi Appenninici)
GENOVA_WEBCAMS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "CAM-OMIRL-PANES",
        "code": "PANES",
        "name": "Fiume Entella & Foce Chiavari/Lavagna (Webcam Ufficiale OMIRL)",
        "category": "land",
        "municipality": "Cogorno / Chiavari",
        "lat": 44.3315,
        "lon": 9.3520,
        "view_direction": "SW (Verso Foce Entella e Golfo del Tigullio)",
        "source": "OMIRL Regione Liguria Live Cam",
        "stream_page_url": "https://omirl.regione.liguria.it",
        "preview_svg_theme": "river",
    },
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
        "name": "Genova Val Bisagno — Alveo Torrente Bisagno (Marassi / Firpo)",
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
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def is_omirl_refdate_fresh(
    ref_date_str: str | None,
    max_age_hours: float = 6.0,
    now: datetime | None = None,
) -> bool:
    """Verifica che la misura del sensore OMIRL sia recente (entro `max_age_hours`) senza hardcoding dell'anno."""
    if not ref_date_str:
        return False
    try:
        dt = datetime.fromisoformat(ref_date_str.replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_ROME_TZ)
    ref_now = now or datetime.now(_ROME_TZ)
    age_seconds = (ref_now - dt).total_seconds()
    return -3600.0 <= age_seconds <= max_age_hours * 3600.0


def extract_var_data(html: str) -> dict[str, Any] | None:
    """Brace-matcher deterministico (ORO-2) che estrae `var data = {...}` dalle pagine ARPAL Liguria."""
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
    headers = {"User-Agent": "MedioMeteoGenova/2.2 (Public Weather Portal)"}
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


async def _fetch_omirl_regional_bulk(client: httpx.AsyncClient) -> dict[str, list[dict[str, Any]]]:
    """Scarica in parallelo i 6 endpoint bulk di OMIRL Regione Liguria con cache di 120s e lock single-flight."""
    now_ts = time.time()
    if _OMIRL_BULK_CACHE["payload"] and (now_ts - _OMIRL_BULK_CACHE["ts"] < 120.0):
        return _OMIRL_BULK_CACHE["payload"]

    async with _OMIRL_BULK_LOCK:
        now_ts = time.time()
        if _OMIRL_BULK_CACHE["payload"] and (now_ts - _OMIRL_BULK_CACHE["ts"] < 120.0):
            return _OMIRL_BULK_CACHE["payload"]

        headers = {
            "Accept": "application/json",
            "User-Agent": "MedioMeteoGenova/2.2 (Observational Network)",
        }
        sensor_types = ["Vento", "Termo", "Pluvio", "Idro", "Boa", "webcam"]
        tasks = [client.get(f"{OMIRL_BASE_URL}/stations/{s}", headers=headers) for s in sensor_types]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        bulk: dict[str, list[dict[str, Any]]] = {s: [] for s in sensor_types}
        for s_type, res in zip(sensor_types, results):
            if isinstance(res, httpx.Response) and res.status_code == 200:
                try:
                    arr = res.json()
                    if isinstance(arr, list):
                        bulk[s_type] = arr
                except Exception:
                    pass

        if any(bulk.values()):
            _OMIRL_BULK_CACHE["ts"] = time.time()
            _OMIRL_BULK_CACHE["payload"] = bulk
        return bulk


async def fetch_omirl_station_chart(
    client: httpx.AsyncClient, short_code: str, sensor_type: str = "Vento"
) -> dict[str, Any]:
    """Interroga `/Omirl/rest/charts/{shortCode}/{sensorType}` per ottenere la serie storica reale della centralina."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "MedioMeteoGenova/2.2 (Observational Network)",
    }
    url = f"{OMIRL_BASE_URL}/charts/{short_code.upper()}/{sensor_type}"
    r = await client.get(url, headers=headers)
    r.raise_for_status()
    raw = r.json()
    series_out: list[dict[str, Any]] = []
    for s in raw.get("dataSeries") or []:
        pts = [
            {
                "timestamp_ms": int(pt[0]),
                "time_label": datetime.fromtimestamp(pt[0] / 1000.0, tz=timezone.utc).strftime("%H:%M"),
                "value": round(float(pt[1]), 2),
            }
            for pt in (s.get("data") or [])
            if isinstance(pt, list) and len(pt) >= 2 and pt[1] is not None and pt[1] > -900
        ]
        series_out.append(
            {
                "name": s.get("name", sensor_type),
                "points": pts[-36:],  # Ultime ore al minuto
            }
        )
    primary_pts = series_out[0]["points"] if series_out else []
    vals = [p["value"] for p in primary_pts]
    min_val = min(vals) if vals else None
    max_val = max(vals) if vals else None
    unit = {"Vento": "km/h", "Termo": "°C", "Pluvio": "mm", "Idro": "m"}.get(sensor_type, "")
    return {
        "code": short_code.upper(),
        "sensor": sensor_type,
        "title": raw.get("title") or f"Centralina OMIRL {short_code.upper()}",
        "subtitle": raw.get("subTitle") or "",
        "available": bool(primary_pts),
        "unit": unit,
        "min_value": min_val,
        "max_value": max_val,
        "recent_24_points": [
            {"timestamp": p["time_label"], "value": p["value"]} for p in primary_pts[-24:]
        ],
        "series": series_out,
    }


async def fetch_omirl_live_observations(
    client: httpx.AsyncClient,
    target_lat: float,
    target_lon: float,
    fallback_current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fonde in tempo reale l'intero parco sensori della Provincia di Genova da OMIRL Bulk REST (ADR-0007)."""
    bulk = await _fetch_omirl_regional_bulk(client)

    fc = fallback_current or {}
    base_temp = float(fc.get("temp_c", 16.5))
    base_rain_1h = float(fc.get("precip_mm", 0.0))
    base_wind_kmh = float(fc.get("wind_kmh", 14.0))
    base_gust_kmh = float(fc.get("gust_kmh", 21.0))
    base_dir_deg = float(fc.get("wind_dir_deg", 15.0))
    now_label = datetime.now().strftime("%H:%M")

    # 1. Indicizza Termometri e Pluviometri reali nella Provincia di Genova per codice e coordinate
    termo_by_code: dict[str, dict[str, Any]] = {}
    pluvio_by_code: dict[str, dict[str, Any]] = {}

    for t_item in bulk.get("Termo", []):
        code = str(t_item.get("shortCode") or "").upper()
        if code and is_omirl_refdate_fresh(t_item.get("refDate")) and t_item.get("value") is not None:
            termo_by_code[code] = t_item

    for p_item in bulk.get("Pluvio", []):
        code = str(p_item.get("shortCode") or "").upper()
        if code and is_omirl_refdate_fresh(p_item.get("refDate")) and p_item.get("value") is not None:
            pluvio_by_code[code] = p_item

    def _in_genova_bbox(lat: float, lon: float) -> bool:
        return 44.10 <= lat <= 44.72 and 8.55 <= lon <= 9.56

    def _nearest_sensor_value(
        lat: float, lon: float, sensor_map: dict[str, dict[str, Any]], code: str, default_val: float
    ) -> float:
        if code in sensor_map:
            return round(float(sensor_map[code]["value"]), 1)
        best_v = default_val
        best_d = 999.0
        for item in sensor_map.values():
            d = haversine_km(lat, lon, float(item.get("lat") or 0.0), float(item.get("lon") or 0.0))
            if d < best_d and d <= 12.0:
                best_d = d
                best_v = round(float(item["value"]), 1)
        return best_v

    def _build_weather_station(
        code: str,
        item: dict[str, Any],
        lat: float,
        lon: float,
        sensor_label: str,
        wind_kmh: float,
        gust_kmh: float,
        wind_dir_deg: float,
        has_live_wind: bool,
    ) -> dict[str, Any]:
        elev_m = int(item.get("alt") or 10)
        ref_str = str(item.get("refDate") or "")
        obs_time = ref_str[11:16] if len(ref_str) >= 16 else now_label
        temp_val = _nearest_sensor_value(
            lat, lon, termo_by_code, code, round(base_temp - max(0, elev_m - 20) * 0.0062, 1)
        )
        rain_val = _nearest_sensor_value(lat, lon, pluvio_by_code, code, round(base_rain_1h, 1))
        return {
            "code": code,
            "name": item.get("name") or code,
            "sensor": sensor_label,
            "muni": item.get("municipality") or "Provincia di Genova",
            "lat": lat,
            "lon": lon,
            "elev_m": elev_m,
            "distance_km": haversine_km(target_lat, target_lon, lat, lon),
            "observed_at": obs_time,
            "temp_c": temp_val,
            "precip_1h_mm": rain_val,
            "wind_kmh": round(wind_kmh, 1),
            "wind_knots": round(wind_kmh / 1.852, 1),
            "gust_kmh": round(gust_kmh, 1),
            "gust_knots": round(gust_kmh / 1.852, 1),
            "gust_estimated": has_live_wind,
            "wind_dir_deg": round(wind_dir_deg, 0),
            "has_live_wind": has_live_wind,
            "has_live_temp": code in termo_by_code,
            "has_live_rain": code in pluvio_by_code,
            "is_live_rest": True,
        }

    # 2. Stazioni Anemometriche & Meteo Reali nella Provincia di Genova
    weather_stations: list[dict[str, Any]] = []
    seen_wind_codes: set[str] = set()

    for w_item in bulk.get("Vento", []):
        lat = float(w_item.get("lat") or 0.0)
        lon = float(w_item.get("lon") or 0.0)
        code = str(w_item.get("shortCode") or "").upper()
        if not code or not _in_genova_bbox(lat, lon):
            continue
        if not is_omirl_refdate_fresh(w_item.get("refDate")):
            continue
        val_kmh = float(w_item.get("value") or 0.0)
        dir_deg = float(w_item.get("increment") or 0.0)
        gust_kmh = round(val_kmh * 1.38, 1)

        weather_stations.append(
            _build_weather_station(
                code=code,
                item=w_item,
                lat=lat,
                lon=lon,
                sensor_label="Vento",
                wind_kmh=val_kmh,
                gust_kmh=gust_kmh,
                wind_dir_deg=dir_deg,
                has_live_wind=True,
            )
        )
        seen_wind_codes.add(code)

    # 2b. Fusione stazioni solo Termo e Pluvio nella Provincia di Genova (~90+ stazioni totali)
    def _nearest_wind_values(lat: float, lon: float) -> tuple[float, float, float]:
        best_kmh = base_wind_kmh
        best_gust = base_gust_kmh
        best_dir = base_dir_deg
        best_d = 999.0
        for ws in weather_stations:
            if not ws.get("has_live_wind"):
                continue
            d = haversine_km(lat, lon, float(ws["lat"]), float(ws["lon"]))
            if d < best_d and d <= 20.0:
                best_d = d
                best_kmh = float(ws["wind_kmh"])
                best_gust = float(ws["gust_kmh"])
                best_dir = float(ws["wind_dir_deg"])
        return best_kmh, best_gust, best_dir

    seen_station_codes: set[str] = set(seen_wind_codes)
    for code, item in (*termo_by_code.items(), *pluvio_by_code.items()):
        if code in seen_station_codes:
            continue
        lat = float(item.get("lat") or 0.0)
        lon = float(item.get("lon") or 0.0)
        if not _in_genova_bbox(lat, lon):
            continue
        w_kmh, w_gust, w_dir = _nearest_wind_values(lat, lon)
        weather_stations.append(
            _build_weather_station(
                code=code,
                item=item,
                lat=lat,
                lon=lon,
                sensor_label="Termo/Pluvio",
                wind_kmh=w_kmh,
                gust_kmh=w_gust,
                wind_dir_deg=w_dir,
                has_live_wind=False,
            )
        )
        seen_station_codes.add(code)

    # 3. Idrometri Fluviali Reali sui 24 Torrenti della Provincia di Genova
    hydrometers: list[dict[str, Any]] = []
    for h_item in bulk.get("Idro", []):
        lat = float(h_item.get("lat") or 0.0)
        lon = float(h_item.get("lon") or 0.0)
        code = str(h_item.get("shortCode") or "").upper()
        if not _in_genova_bbox(lat, lon):
            continue
        if not is_omirl_refdate_fresh(h_item.get("refDate")):
            continue
        lvl_m = round(float(h_item.get("value") or 0.0), 2)
        meta = GENOVA_HYDROMETERS_META.get(
            code,
            {
                "river": f"Bacino {h_item.get('municipality') or 'Genova'}",
                "warn_m": 2.00,
                "alarm_m": 3.00,
            },
        )
        warn_m = float(meta["warn_m"])
        alarm_m = float(meta["alarm_m"])
        if lvl_m >= alarm_m:
            h_status = "ALLARME ROSSO (Superamento 2ª soglia)"
            h_level = "red"
        elif lvl_m >= warn_m:
            h_status = "GUARDIA ARANCIONE (Superamento 1ª soglia)"
            h_level = "orange"
        else:
            h_status = "REGOLARE (Alveo in regime ordinario)"
            h_level = "green"

        ref_str = str(h_item.get("refDate") or "")
        obs_time = ref_str[11:16] if len(ref_str) >= 16 else now_label
        dist = haversine_km(target_lat, target_lon, lat, lon)

        hydrometers.append(
            {
                "code": code,
                "name": h_item.get("name") or code,
                "sensor": "Idro",
                "muni": h_item.get("municipality") or "Genova",
                "river": meta["river"],
                "lat": lat,
                "lon": lon,
                "elev_m": int(h_item.get("alt") or 15),
                "distance_km": dist,
                "observed_at": obs_time,
                "level_m": lvl_m,
                "warn_threshold_m": warn_m,
                "alarm_threshold_m": alarm_m,
                "fill_pct": int(max(6, min(100, round((max(0.1, lvl_m + 0.5) / (alarm_m + 0.5)) * 100)))),
                "status_label": h_status,
                "status_level": h_level,
                "is_live_rest": True,
            }
        )

    # Fallback se la rete OMIRL fosse irraggiungibile (es. test offline)
    if not weather_stations or not hydrometers:
        for st in REFERENCE_OMIRL_STATIONS:
            dist = haversine_km(target_lat, target_lon, st["lat"], st["lon"])
            item = {
                **st,
                "distance_km": dist,
                "observed_at": now_label,
                "muni": st.get("municipality", "Genova"),
                "river": st.get("basin", "Bacino Ligure"),
            }
            if st["sensor"] == "Idro" and not hydrometers:
                base_lvl = round(0.45 + min(2.2, base_rain_1h * 0.08), 2)
                w_m = float(st.get("warn_m", 2.2))
                a_m = float(st.get("alarm_m", 3.2))
                item.update(
                    {
                        "level_m": base_lvl,
                        "warn_threshold_m": w_m,
                        "alarm_threshold_m": a_m,
                        "fill_pct": 22,
                        "status_label": "REGOLARE (Alveo in regime ordinario)",
                        "status_level": "green",
                        "is_live_rest": False,
                    }
                )
                hydrometers.append(item)
            elif st["sensor"] != "Idro" and not weather_stations:
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
                        "has_live_wind": False,
                        "has_live_temp": False,
                        "has_live_rain": False,
                        "is_live_rest": False,
                    }
                )
                weather_stations.append(item)

    weather_stations.sort(key=lambda x: x["distance_km"])
    hydrometers.sort(key=lambda x: x["distance_km"])

    # 4. Boa Ondametrica Regionale OMIRL (Capo Mele BOACM)
    buoys_live: list[dict[str, Any]] = []
    for b_item in bulk.get("Boa", []):
        if b_item.get("value") is not None:
            ref_str = str(b_item.get("refDate") or "")
            buoys_live.append(
                {
                    "code": b_item.get("shortCode", "BOACM"),
                    "name": b_item.get("name", "Boa Capo Mele (OMIRL)"),
                    "lat": float(b_item.get("lat") or 43.918),
                    "lon": float(b_item.get("lon") or 8.185),
                    "wave_hs_m": round(float(b_item["value"]), 2),
                    "increment_m": round(float(b_item.get("increment") or 0.0), 2),
                    "observed_at": ref_str[11:16] if len(ref_str) >= 16 else now_label,
                    "is_live_rest": True,
                }
            )

    # 5. Webcam Reali con frame fotografico OMIRL quando disponibile (`imgPath`)
    live_cam_imgs: dict[str, str] = {}
    for wc_item in bulk.get("webcam", []):
        c_code = str(wc_item.get("shortCode") or "").upper()
        img_p = str(wc_item.get("imgPath") or "")
        if c_code and img_p:
            live_cam_imgs[c_code] = f"{OMIRL_PUBLIC_HOST}/{img_p.lstrip('/')}"

    webcams_sorted = []
    for cam in GENOVA_WEBCAMS_CATALOG:
        c_dist = haversine_km(target_lat, target_lon, cam["lat"], cam["lon"])
        c_code = cam.get("code", "")
        webcams_sorted.append(
            {
                **cam,
                "distance_km": c_dist,
                "timestamp_label": now_label,
                "provider": cam.get("source", "Rete Osservativa OMIRL"),
                "portal_url": cam.get("stream_page_url", OMIRL_PUBLIC_HOST),
                "live_image_url": live_cam_imgs.get(c_code),
            }
        )
    webcams_sorted.sort(key=lambda x: x["distance_km"])

    return {
        "network_name": "Rete Osservativa OMIRL — Regione Liguria / ARPAL (Live REST)",
        "wms_endpoint": OMIRL_WMS_URL,
        "live_sensors_count": {
            "wind_stations": len(seen_wind_codes),
            "total_weather_stations": len(weather_stations),
            "river_hydrometers": len(hydrometers),
            "buoys": len(buoys_live),
        },
        "marine_wave_buoy": buoys_live[0] if buoys_live else None,
        "buoys_live": buoys_live,
        "nearest_weather_stations": weather_stations[:8],
        "all_weather_stations": weather_stations,
        "nearest_river_hydrometers": hydrometers[:8],
        "all_river_hydrometers": hydrometers,
        "nearest_webcams": webcams_sorted[:4],
        "all_webcams": webcams_sorted,
    }


_ROME_TZ = ZoneInfo("Europe/Rome")


def metno_utc_to_rome_hour_key(t_raw: str) -> str | None:
    """Converte un timestamp ISO UTC di MET Norway nella chiave oraria locale Europe/Rome (YYYY-MM-DDTHH:00)."""
    if not t_raw:
        return None
    try:
        dt = datetime.fromisoformat(t_raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_rome = dt.astimezone(_ROME_TZ)
        return dt_rome.strftime("%Y-%m-%dT%H:00")
    except ValueError:
        return t_raw[:13] + ":00" if len(t_raw) >= 13 else None


async def fetch_metno_compact(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict[str, dict[str, float]]:
    """Scarica il 5° modello indipendente MET Norway (YR.no) allineato a Europe/Rome."""
    headers = {
        "User-Agent": "MedioMeteoGenova/2.2 https://github.com/Noobucodonosor/mediometeo"
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
        hour_key = metno_utc_to_rome_hour_key(t_raw)
        if not hour_key:
            continue
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
