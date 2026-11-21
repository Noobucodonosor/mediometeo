"""Entrypoint FastAPI per MedioMeteo Genova — Piattaforma Forecast & Nowcast Terra e Mare (ADR-0001..0006)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.cache import SQLiteCache
from backend.config import get_settings
from backend.districts import (
    District,
    find_nearest_district,
    get_district,
    list_districts,
)
from backend.engine.ai_advisor import generate_ai_bulletin
from backend.engine.alerts import build_alerts_summary
from backend.engine.coastal_route import COASTAL_WAYPOINTS, compute_coastal_route_eta
from backend.engine.connectors import fetch_all_raw_sources
from backend.engine.ensemble import build_complete_weather_package
from backend.engine.omirl_arpal import fetch_omirl_station_chart
from backend.locations import (
    AMP_PORTOFINO_ZONES,
    GeoLocation,
    find_nearest_location,
    get_location,
    search_locations,
)
from backend.security import (
    SAFETY_DISCLAIMER_LAND,
    SAFETY_DISCLAIMER_SEA,
    sanitize_metadata,
    validate_ligurian_coordinates,
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="MedioMeteo Genova — Forecast & Nowcast Terra/Mare",
    description=(
        "Sistema Multi-Modello a 5 Membri (AROME 1.3km, ICON-D2 2km, ECMWF 9km, GFS, MET Norway), "
        "Rete Osservativa Reale OMIRL (Stazioni, Idrometri Torrenti, Boe, Webcam Live), "
        "Fisica Costiera Pura e Calcolatore Rotta ETA per i 67 Comuni della Città Metropolitana di Genova e il Golfo Ligure."
    ),
    version="2.0.0",
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list(),
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Applica header di sicurezza HTTP (ADR-0011)."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com "
        "https://tilecache.rainviewer.com https://omirl.regione.liguria.it https://unpkg.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'",
    )
    return response


def _get_cache() -> SQLiteCache:
    settings = get_settings()
    return SQLiteCache(settings.db_path)


def _resolve_target(
    district_or_loc_id: str | None,
    lat: float | None,
    lon: float | None,
    mode: str = "land",
) -> tuple[District, GeoLocation | None, tuple[float, float] | None]:
    """Risolve il distretto, la località granulare (tra le 118 censite) e/o le coordinate personalizzate."""
    custom_coords: tuple[float, float] | None = None
    loc_obj: GeoLocation | None = None

    if district_or_loc_id:
        loc_obj = get_location(district_or_loc_id)

    if lat is not None and lon is not None:
        v_lat, v_lon = validate_ligurian_coordinates(lat, lon)
        custom_coords = (v_lat, v_lon)
        if loc_obj:
            d = get_district(loc_obj.district_id) or find_nearest_district(v_lat, v_lon)
            return d, loc_obj, custom_coords
        if district_or_loc_id:
            d = get_district(district_or_loc_id)
            if not d:
                raise HTTPException(
                    status_code=404, detail=f"Località o distretto '{district_or_loc_id}' non trovato."
                )
            near_loc = find_nearest_location(v_lat, v_lon, preferred_category=mode)
            return d, near_loc, custom_coords
        near_loc = find_nearest_location(
            v_lat, v_lon, preferred_category=mode if mode in ("land", "sea") else None
        )
        d = get_district(near_loc.district_id) or find_nearest_district(
            v_lat, v_lon, preferred_category=mode if mode in ("land", "sea") else None
        )
        return d, near_loc, custom_coords

    if loc_obj:
        d = get_district(loc_obj.district_id) or find_nearest_district(loc_obj.lat, loc_obj.lon)
        return d, loc_obj, None

    target_id = district_or_loc_id or ("MARE-PORTO-DIGA" if mode == "sea" else "GE-CENTRO-PONENTE")
    d = get_district(target_id)
    if not d:
        raise HTTPException(
            status_code=404,
            detail=f"Località o distretto '{target_id}' non censito nella Provincia di Genova.",
        )
    loc_fallback = get_location(target_id)
    return d, loc_fallback, None


async def _load_or_compute_weather_package(
    district: District,
    location_meta: GeoLocation | None = None,
    custom_coords: tuple[float, float] | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Carica il pacchetto meteo dalla cache SQLite o interroga i 5 modelli + OMIRL + ARPAL in parallelo."""
    settings = get_settings()
    cache = _get_cache()
    lat, lon = (
        custom_coords
        if custom_coords
        else (
            (location_meta.lat, location_meta.lon)
            if location_meta
            else (district.lat, district.lon)
        )
    )
    sea_lat, sea_lon = (
        (custom_coords[0], custom_coords[1])
        if (custom_coords and ((location_meta and location_meta.category == "sea") or district.category == "sea"))
        else (
            (location_meta.sea_lat, location_meta.sea_lon)
            if location_meta
            else (district.sea_lat, district.sea_lon)
        )
    )
    loc_key = location_meta.id if location_meta else district.id
    cache_key = f"pkg:v2.5:{loc_key}:{lat:.3f}:{lon:.3f}"

    if not force_refresh:
        cached = cache.get(cache_key, allow_stale=False)
        if cached:
            payload = dict(cached.payload)
            payload["data_age_seconds"] = cached.age_seconds
            payload["from_cache"] = True
            return payload

    raw = await fetch_all_raw_sources(lat, lon, sea_lat, sea_lon)

    if not raw.get("multimodel"):
        stale = cache.get(cache_key, allow_stale=True)
        if stale:
            payload = dict(stale.payload)
            payload["is_stale"] = True
            payload["stale_warning"] = (
                "Dati serviti dalla cache di resilienza SQLite — connessione verso i provider esterni temporaneamente degradata."
            )
            payload["data_age_seconds"] = stale.age_seconds
            payload["from_cache"] = True
            return payload

    pkg = build_complete_weather_package(
        district,
        raw,
        custom_coords=custom_coords,
        location_meta=location_meta,
    )
    pkg["alerts"] = build_alerts_summary(pkg)
    pkg["data_age_seconds"] = 0
    pkg["from_cache"] = False

    if raw.get("multimodel"):
        cache.set(cache_key, pkg, ttl_seconds=settings.nowcast_ttl_seconds, category="weather_pkg")
    else:
        pkg["is_stale"] = True
        pkg["stale_warning"] = (
            "Modalità Fallback Sinottico Attiva: reti meteo esterne non raggiungibili, valori di baseline."
        )

    return pkg


@app.get("/api/v1/health")
async def health_check() -> dict[str, Any]:
    """Stato di salute del sistema, della cache SQLite e dei provider configurati (senza mai esporre segreti)."""
    settings = get_settings()
    cache = _get_cache()
    all_locs = search_locations()
    return sanitize_metadata(
        {
            "status": "ok",
            "app_name": settings.app_name,
            "version": "2.0.0",
            "domain": "Provincia di Genova (67 Comuni + 25 Quartieri + 20 Rade/Porti + 6 Valichi)",
            "locations_catalog_count": len(all_locs),
            "geofence_bbox": {
                "min_lat": settings.min_lat,
                "max_lat": settings.max_lat,
                "min_lon": settings.min_lon,
                "max_lon": settings.max_lon,
            },
            "ai_advisor_ready": bool(settings.gemini_api_key),
            "commercial_plugins_configured": settings.configured_commercial_providers(),
            "cache_stats": cache.stats(),
        }
    )


@app.get("/api/v1/locations")
async def api_list_locations(
    q: str | None = Query(default=None, description="Ricerca testuale su Comune, Quartiere, Rada o Vallata"),
    loc_type: str | None = Query(default=None, description="Filtra per 'comune', 'quartiere', 'rada_porto', 'valico'"),
    category: str | None = Query(default=None, description="Filtra per 'land' o 'sea'"),
) -> dict[str, Any]:
    """Restituisce il catalogo granulare delle 118 località della Provincia di Genova (67 Comuni, 25 Quartieri, 20 Rade, 6 Valichi) + Zone AMP + Waypoint Rotta."""
    items = search_locations(q=q, loc_type=loc_type, category=category)
    return {
        "count": len(items),
        "locations": items,
        "amp_portofino_zones": AMP_PORTOFINO_ZONES,
        "coastal_waypoints": list(COASTAL_WAYPOINTS.values()),
    }


@app.get("/api/v1/districts")
async def api_list_districts(
    category: str | None = Query(
        default=None, description="Filtra per 'land' (Terra) o 'sea' (Mare)"
    ),
) -> dict[str, Any]:
    """Restituisce i macro-distretti operativi Terra e Mare della Provincia di Genova."""
    items = list_districts(category=category)
    return {
        "count": len(items),
        "category_filter": category,
        "districts": items,
        "disclaimers": {
            "land": SAFETY_DISCLAIMER_LAND,
            "sea": SAFETY_DISCLAIMER_SEA,
        },
    }


@app.get("/api/v1/observations")
async def api_get_observations(
    location: str | None = Query(default=None, description="ID località o Comune (es. COM-GENOVA, SEA-BAIA-DI-SAN-FRUTTUOSO)"),
    district: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Restituisce esclusivamente la verità osservativa (`1. ADESSO`): Stazioni reali OMIRL, Idrometri Torrenti e Webcam Live ordinate per distanza."""
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon)
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords, force_refresh=refresh)
    return {
        "generated_at": pkg["generated_at"],
        "location": pkg["location"],
        "coordinates": pkg["coordinates"],
        "observations_live": pkg["observations_live"],
    }


@app.get("/api/v1/omirl-chart")
async def api_get_omirl_station_chart(
    code: str = Query(
        ...,
        min_length=2,
        max_length=12,
        pattern="^[A-Za-z0-9_-]{2,12}$",
        description="ShortCode centralina OMIRL (es. GEPOA, MTPOR, FIRPO)",
    ),
    sensor: str = Query(default="Vento", pattern="^(Vento|Termo|Pluvio|Idro)$", description="Tipo sensore OMIRL"),
) -> dict[str, Any]:
    """Restituisce la serie storica reale al minuto di una centralina OMIRL Regione Liguria."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            return await fetch_omirl_station_chart(client, short_code=code, sensor_type=sensor)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Serie storica OMIRL temporaneamente non disponibile.",
        ) from exc


@app.get("/api/v1/nowcast")
async def api_get_nowcast(
    location: str | None = Query(default=None, description="ID località (67 Comuni, 25 Quartieri, 20 Rade, 6 Valichi)"),
    district: str | None = Query(default=None, description="ID distretto legacy"),
    lat: float | None = Query(default=None, description="Latitudine opzionale nel dominio Ligure"),
    lon: float | None = Query(default=None, description="Longitudine opzionale nel dominio Ligure"),
    mode: str = Query(default="land", pattern="^(land|sea)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Nowcasting ad alta frequenza (0-3 ore, step 15m, Sensori OMIRL, Radar RainViewer, Convergenza Ligure, Fisica Terra & Mare)."""
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon, mode=mode)
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords, force_refresh=refresh)
    return {
        "generated_at": pkg["generated_at"],
        "data_age_seconds": pkg["data_age_seconds"],
        "is_stale": pkg["is_stale"],
        "stale_warning": pkg["stale_warning"],
        "district": pkg["district"],
        "location": pkg["location"],
        "coordinates": pkg["coordinates"],
        "sources": pkg["sources"],
        "observations_live": pkg["observations_live"],
        "nowcast": pkg["nowcast"],
        "land": pkg["land"],
        "sea": pkg["sea"],
        "official_bulletins": pkg["official_bulletins"],
        "alerts": pkg["alerts"],
    }


@app.get("/api/v1/forecast")
async def api_get_forecast(
    location: str | None = Query(default=None, description="ID località (es. COM-GENOVA, COM-PORTOFINO, QRT-GENOVA-NERI)"),
    district: str | None = Query(default=None, description="ID distretto"),
    lat: float | None = Query(default=None, description="Latitudine opzionale nel dominio Ligure"),
    lon: float | None = Query(default=None, description="Longitudine opzionale nel dominio Ligure"),
    mode: str = Query(default="land", pattern="^(land|sea)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Restituisce il pacchetto completo: Osservazioni Reali OMIRL + Nowcast 0-3h + Forecast 48h a 5 Modelli + 7 giorni."""
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon, mode=mode)
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords, force_refresh=refresh)
    return pkg


@app.get("/api/v1/marine")
async def api_get_marine(
    location: str | None = Query(default=None, description="ID rada/porto del Golfo di Genova"),
    district: str | None = Query(default="MARE-PORTO-DIGA", description="ID settore marino del Golfo di Genova"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Endpoint di Fisica Costiera e Marina Pura (Zero semafori soggettivi — Spettro d'onda, Maree, Risacca, Correnti)."""
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon, mode="sea")
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords, force_refresh=refresh)
    return {
        "generated_at": pkg["generated_at"],
        "data_age_seconds": pkg["data_age_seconds"],
        "is_stale": pkg["is_stale"],
        "district": pkg["district"],
        "location": pkg["location"],
        "coordinates": pkg["coordinates"],
        "current_marine": pkg["sea"]["marine_conditions"],
        "meteomar": pkg["alerts"]["meteomar"],
        "hourly_marine_48h": [
            {
                "time": h["time"],
                "wind_knots": h["wind_knots"],
                "gust_knots": h["gust_knots"],
                "wind_ms": h["wind_ms"],
                "wind_cardinal": h["wind_cardinal"],
                "wind_name": h["wind_ligurian_name"],
                "beaufort_force": h["beaufort_force"],
                "wave_hs_m": h["wave_hs_m"],
                "wave_hmax_m": h["wave_hmax_m"],
                "wave_wind_m": h["wave_wind_m"],
                "wave_swell_m": h["wave_swell_m"],
                "wave_period_s": h["wave_period_s"],
                "wave_wavelength_m": h["wave_wavelength_m"],
                "wave_steepness_pct": h["wave_steepness_pct"],
                "wave_dir_cardinal": h["wave_dir_cardinal"],
                "douglas_degree": h["douglas_degree"],
                "douglas_label": h["douglas_label"],
                "steepness_warning": h["steepness_warning"],
                "shore_breaker_m": h["shore_breaker_m"],
                "current_knots": h["current_knots"],
                "pressure_hpa": h["pressure_hpa"],
            }
            for h in pkg["forecast"]["hourly_48h"]
        ],
        "safety_disclaimer": SAFETY_DISCLAIMER_SEA,
    }


@app.get("/api/v1/route-eta")
async def api_calculate_coastal_route_eta(
    origin: str = Query(default="portofino", description="Waypoint di partenza (es. genova_porto, camogli, portofino)"),
    dest: str = Query(default="san_fruttuoso", description="Waypoint di destinazione (es. san_fruttuoso, punta_chiappa, sestri_levante)"),
    cruise_knots: float = Query(default=6.0, ge=1.0, le=45.0, description="Velocità di crociera desiderata in nodi"),
    duration_min: int = Query(default=90, ge=15, le=720, description="Durata totale pianificata dell'uscita in minuti"),
    stop_min: int = Query(default=20, ge=0, le=360, description="Sosta / bagno previsto a destinazione in minuti"),
    round_trip: bool = Query(default=True, description="Calcola Andata + Ritorno"),
) -> dict[str, Any]:
    """Calcolatore Nautico Costiero Golfo di Genova: percorso su grafo che non taglia i promontori, limiti AMP Portofino, ETA, Turnaround e Delta fisico A/R."""
    if origin not in COASTAL_WAYPOINTS or dest not in COASTAL_WAYPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"Waypoint non valido. Waypoint disponibili: {list(COASTAL_WAYPOINTS.keys())}",
        )
    dest_wp = COASTAL_WAYPOINTS[dest]
    d, loc_meta, custom_coords = _resolve_target(None, dest_wp["lat"], dest_wp["lon"], mode="sea")
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords)
    route_plan = compute_coastal_route_eta(
        origin_id=origin,
        dest_id=dest,
        cruise_speed_knots=cruise_knots,
        duration_minutes=duration_min,
        stop_minutes=stop_min,
        round_trip=round_trip,
        hourly_forecast=pkg["forecast"]["hourly_48h"],
    )
    return route_plan


@app.get("/api/v1/alerts")
async def api_get_alerts(
    location: str | None = Query(default=None),
    district: str | None = Query(default="GE-CENTRO-PONENTE"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
) -> dict[str, Any]:
    """Quadro sinottico delle allerte Terra (ARPAL Zone B/C/D/E) e Bollettino Fisico Mare (Meteomar Mar Ligure)."""
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon)
    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords)
    return pkg["alerts"]


@app.get("/api/v1/ai-bulletin")
async def api_get_ai_bulletin(
    location: str | None = Query(default=None),
    district: str | None = Query(default="GE-CENTRO-PONENTE"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    mode: str = Query(default="both", pattern="^(land|sea|both)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Analisi sinottica pura generata da Google Gemini (o motore sinottico ligure deterministico)."""
    settings = get_settings()
    cache = _get_cache()
    target = location or district
    d, loc_meta, custom_coords = _resolve_target(target, lat, lon)
    loc_key = loc_meta.id if loc_meta else d.id
    b_key = f"ai:v2:{loc_key}:{mode}:{custom_coords[0] if custom_coords else d.lat:.2f}"
    if not refresh:
        cached = cache.get(b_key, allow_stale=False)
        if cached:
            return cached.payload

    pkg = await _load_or_compute_weather_package(d, location_meta=loc_meta, custom_coords=custom_coords)
    bulletin = await generate_ai_bulletin(pkg, mode=mode)
    cache.set(b_key, bulletin, ttl_seconds=settings.ai_bulletin_ttl_seconds, category="ai_bulletin")
    return bulletin


# Mount static files per la Web App / PWA se la cartella frontend esiste
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_pwa_root():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    return {"message": "MedioMeteo Genova Backend Active. Visit /docs for OpenAPI UI."}


@app.get("/orologio", include_in_schema=False)
async def serve_smartwatch_view():
    """Vista Smartwatch / Polso ad alto contrasto per la navigazione costiera (ADR-0006)."""
    watch_file = FRONTEND_DIR / "orologio.html"
    if watch_file.exists():
        return FileResponse(
            str(watch_file),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    raise HTTPException(status_code=404, detail="Vista Smartwatch /orologio non trovata.")


@app.get("/manifest.json", include_in_schema=False)
async def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(
            str(manifest_file),
            media_type="application/manifest+json",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    raise HTTPException(status_code=404)


@app.get("/sw.js", include_in_schema=False)
async def serve_service_worker():
    sw_file = FRONTEND_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(
            str(sw_file),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    raise HTTPException(status_code=404)
