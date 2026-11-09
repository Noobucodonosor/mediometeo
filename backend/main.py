"""Entrypoint FastAPI per MedioMeteo Genova — Piattaforma Forecast & Nowcast Terra e Mare (ADR-0001..0004)."""

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
from backend.engine.connectors import fetch_all_raw_sources
from backend.engine.ensemble import build_complete_weather_package
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
        "Sistema Multi-Modello ad altissima risoluzione (AROME 1.3km, ICON-D2 2km, ECMWF 9km, GFS, "
        "Open-Meteo Marine, RainViewer Radar & AI Advisor) per la Provincia di Genova e il Golfo Ligure."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def _get_cache() -> SQLiteCache:
    settings = get_settings()
    return SQLiteCache(settings.db_path)


def _resolve_target(
    district_id: str | None,
    lat: float | None,
    lon: float | None,
    mode: str = "land",
) -> tuple[District, tuple[float, float] | None]:
    """Risolve il distretto e/o le coordinate personalizzate validate nel dominio Ligure."""
    custom_coords: tuple[float, float] | None = None
    if lat is not None and lon is not None:
        v_lat, v_lon = validate_ligurian_coordinates(lat, lon)
        custom_coords = (v_lat, v_lon)
        if district_id:
            d = get_district(district_id)
            if not d:
                raise HTTPException(
                    status_code=404, detail=f"Distretto '{district_id}' non trovato."
                )
            return d, custom_coords
        nearest = find_nearest_district(
            v_lat, v_lon, preferred_category=mode if mode in ("land", "sea") else None
        )
        return nearest, custom_coords

    target_id = district_id or ("MARE-PORTO-DIGA" if mode == "sea" else "GE-CENTRO-PONENTE")
    d = get_district(target_id)
    if not d:
        raise HTTPException(
            status_code=404,
            detail=f"Distretto '{target_id}' non censito nella Provincia di Genova.",
        )
    return d, None


async def _load_or_compute_weather_package(
    district: District,
    custom_coords: tuple[float, float] | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Carica il pacchetto meteo dalla cache SQLite o interroga i modelli in parallelo con fallback."""
    settings = get_settings()
    cache = _get_cache()
    lat, lon = custom_coords if custom_coords else (district.lat, district.lon)
    sea_lat, sea_lon = (
        (custom_coords[0], custom_coords[1])
        if (custom_coords and district.category == "sea")
        else (district.sea_lat, district.sea_lon)
    )
    cache_key = f"pkg:{district.id}:{lat:.3f}:{lon:.3f}"

    if not force_refresh:
        cached = cache.get(cache_key, allow_stale=False)
        if cached:
            payload = dict(cached.payload)
            payload["data_age_seconds"] = cached.age_seconds
            payload["from_cache"] = True
            return payload

    raw = await fetch_all_raw_sources(lat, lon, sea_lat, sea_lon)

    # Se la rete esterna ha fallito completamente, controlla se esiste una copia stale in SQLite (ADR-0002)
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

    pkg = build_complete_weather_package(district, raw, custom_coords=custom_coords)
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
    return sanitize_metadata(
        {
            "status": "ok",
            "app_name": settings.app_name,
            "version": settings.version,
            "domain": "Provincia di Genova & Golfo Ligure (Terra + Mare)",
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


@app.get("/api/v1/districts")
async def api_list_districts(
    category: str | None = Query(
        default=None, description="Filtra per 'land' (Terra) o 'sea' (Mare)"
    ),
) -> dict[str, Any]:
    """Restituisce i distretti operativi Terra e Mare della Provincia di Genova."""
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


@app.get("/api/v1/nowcast")
async def api_get_nowcast(
    district: str | None = Query(default=None, description="ID distretto es. GE-CENTRO-PONENTE o MARE-PORTO-DIGA"),
    lat: float | None = Query(default=None, description="Latitudine opzionale nel dominio Ligure"),
    lon: float | None = Query(default=None, description="Longitudine opzionale nel dominio Ligure"),
    mode: str = Query(default="land", pattern="^(land|sea)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Nowcasting ad alta frequenza (0-3 ore, step 15m, Radar RainViewer, Convergenza Ligure, Stato Terra & Mare)."""
    d, custom_coords = _resolve_target(district, lat, lon, mode=mode)
    pkg = await _load_or_compute_weather_package(d, custom_coords=custom_coords, force_refresh=refresh)
    return {
        "generated_at": pkg["generated_at"],
        "data_age_seconds": pkg["data_age_seconds"],
        "is_stale": pkg["is_stale"],
        "stale_warning": pkg["stale_warning"],
        "district": pkg["district"],
        "coordinates": pkg["coordinates"],
        "sources": pkg["sources"],
        "nowcast": pkg["nowcast"],
        "land": pkg["land"],
        "sea": pkg["sea"],
        "alerts": pkg["alerts"],
    }


@app.get("/api/v1/forecast")
async def api_get_forecast(
    district: str | None = Query(default=None, description="ID distretto"),
    lat: float | None = Query(default=None, description="Latitudine opzionale nel dominio Ligure"),
    lon: float | None = Query(default=None, description="Longitudine opzionale nel dominio Ligure"),
    mode: str = Query(default="land", pattern="^(land|sea)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Restituisce il pacchetto completo Nowcast + Forecast 48h Multi-Modello (AROME/ICON-D2/ECMWF/GFS) + 7 giorni."""
    d, custom_coords = _resolve_target(district, lat, lon, mode=mode)
    pkg = await _load_or_compute_weather_package(d, custom_coords=custom_coords, force_refresh=refresh)
    return pkg


@app.get("/api/v1/marine")
async def api_get_marine(
    district: str | None = Query(default="MARE-PORTO-DIGA", description="ID settore marino del Golfo di Genova"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Endpoint specialistico per la navigazione e la sicurezza in mare nel Golfo di Genova."""
    d, custom_coords = _resolve_target(district, lat, lon, mode="sea")
    pkg = await _load_or_compute_weather_package(d, custom_coords=custom_coords, force_refresh=refresh)
    return {
        "generated_at": pkg["generated_at"],
        "data_age_seconds": pkg["data_age_seconds"],
        "is_stale": pkg["is_stale"],
        "district": pkg["district"],
        "coordinates": pkg["coordinates"],
        "current_marine": pkg["sea"]["marine_conditions"],
        "meteomar": pkg["alerts"]["meteomar"],
        "hourly_marine_48h": [
            {
                "time": h["time"],
                "wind_knots": h["wind_knots"],
                "gust_knots": h["gust_knots"],
                "wind_cardinal": h["wind_cardinal"],
                "wind_name": h["wind_ligurian_name"],
                "beaufort_force": h["beaufort_force"],
                "wave_hs_m": h["wave_hs_m"],
                "wave_hmax_m": h["wave_hmax_m"],
                "wave_period_s": h["wave_period_s"],
                "wave_dir_cardinal": h["wave_dir_cardinal"],
                "douglas_degree": h["douglas_degree"],
                "douglas_label": h["douglas_label"],
                "steepness_warning": h["steepness_warning"],
                "pressure_hpa": h["pressure_hpa"],
            }
            for h in pkg["forecast"]["hourly_48h"]
        ],
        "safety_disclaimer": SAFETY_DISCLAIMER_SEA,
    }


@app.get("/api/v1/alerts")
async def api_get_alerts(
    district: str | None = Query(default="GE-CENTRO-PONENTE"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
) -> dict[str, Any]:
    """Quadro sinottico delle allerte Terra (ARPAL Zone B/C/D/E) e Mare (Meteomar Mar Ligure)."""
    d, custom_coords = _resolve_target(district, lat, lon)
    pkg = await _load_or_compute_weather_package(d, custom_coords=custom_coords)
    return pkg["alerts"]


@app.get("/api/v1/ai-bulletin")
async def api_get_ai_bulletin(
    district: str | None = Query(default="GE-CENTRO-PONENTE"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    mode: str = Query(default="both", pattern="^(land|sea|both)$"),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Bollettino sinottico esperto generato da Google Gemini (o fallback sinottico ligure)."""
    settings = get_settings()
    cache = _get_cache()
    d, custom_coords = _resolve_target(district, lat, lon)
    b_key = f"ai:{d.id}:{mode}:{custom_coords[0] if custom_coords else d.lat:.2f}"
    if not refresh:
        cached = cache.get(b_key, allow_stale=False)
        if cached:
            return cached.payload

    pkg = await _load_or_compute_weather_package(d, custom_coords=custom_coords)
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
        return FileResponse(str(index_file))
    return {"message": "MedioMeteo Genova Backend Active. Visit /docs for OpenAPI UI."}


@app.get("/manifest.json", include_in_schema=False)
async def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(str(manifest_file), media_type="application/manifest+json")
    raise HTTPException(status_code=404)


@app.get("/sw.js", include_in_schema=False)
async def serve_service_worker():
    sw_file = FRONTEND_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(str(sw_file), media_type="application/javascript")
    raise HTTPException(status_code=404)
