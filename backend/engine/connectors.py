"""Connettori Asincroni Multi-Sorgente con Circuit Breaker e Resilienza (ADR-0002, ADR-0003).

Sorgenti integrate:
1. Open-Meteo Multi-Model API (AROME 1.3km, ICON-D2 2km, ECMWF IFS 9km, GFS) + Minutely-15 Nowcasting
2. Open-Meteo Marine API (Altezza onda significativa, Wind-wave, Swell, Periodo, Direzione, SST)
3. RainViewer Weather Radar API (Timestamp e URL tile radar precipitazioni real-time e nowcast 30m)
4. Stazioni Osservative Liguria (OMIRL / ARPAL sintesi osservativa + Allerta Liguria / Meteomar)
5. Connettori Commerciali Opzionali (Tomorrow.io, WeatherAPI, Stormglass.io) se API key presente in `.env`
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
import httpx

from backend.config import get_settings
from backend.engine.omirl_arpal import (
    fetch_arpal_official_bulletins,
    fetch_metno_compact,
    fetch_omirl_live_observations,
)


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
RAINVIEWER_MAPS_URL = "https://api.rainviewer.com/public/weather-maps.json"
TOMORROW_TIMELINES_URL = "https://api.tomorrow.io/v4/weather/forecast"
WEATHERAPI_FORECAST_URL = "https://api.weatherapi.com/v1/forecast.json"
STORMGLASS_POINT_URL = "https://api.stormglass.io/v2/weather/point"


async def fetch_open_meteo_multimodel(
    client: httpx.AsyncClient, lat: float, lon: float
) -> dict[str, Any]:
    """Recupera in una singola chiamata i modelli LAM (AROME, ICON) e globali (ECMWF, GFS) + dati 15 minuti."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "Europe/Rome",
        "models": "meteofrance_arome_france_hd,icon_d2,ecmwf_ifs025,gfs_seamless",
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
            "rain,showers,weather_code,cloud_cover,pressure_msl,wind_speed_10m,"
            "wind_direction_10m,wind_gusts_10m"
        ),
        "minutely_15": (
            "temperature_2m,precipitation,rain,weather_code,wind_speed_10m,"
            "wind_direction_10m,wind_gusts_10m,visibility,cape"
        ),
        "forecast_minutely_15": 16,  # 4 ore a step di 15 minuti per il Nowcasting
        "hourly": (
            "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
            "precipitation_probability,precipitation,weather_code,pressure_msl,"
            "cloud_cover,visibility,wind_speed_10m,wind_direction_10m,"
            "wind_gusts_10m,cape,uv_index,shortwave_radiation"
        ),
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
            "wind_direction_10m_dominant"
        ),
        "forecast_days": 7,
    }
    resp = await client.get(OPEN_METEO_FORECAST_URL, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_open_meteo_marine(
    client: httpx.AsyncClient, sea_lat: float, sea_lon: float
) -> dict[str, Any]:
    """Recupera i parametri meteo-marini sul Golfo di Genova / Mar Ligure."""
    params = {
        "latitude": sea_lat,
        "longitude": sea_lon,
        "timezone": "Europe/Rome",
        "current": (
            "wave_height,wave_direction,wave_period,wind_wave_height,"
            "wind_wave_direction,wind_wave_period,swell_wave_height,"
            "swell_wave_direction,swell_wave_period,ocean_current_velocity,"
            "ocean_current_direction,sea_surface_temperature"
        ),
        "hourly": (
            "wave_height,wave_direction,wave_period,wind_wave_height,"
            "wind_wave_direction,wind_wave_period,swell_wave_height,"
            "swell_wave_direction,swell_wave_period,sea_level_height_msl,"
            "ocean_current_velocity,ocean_current_direction,sea_surface_temperature"
        ),
        "daily": "wave_height_max,wave_direction_dominant,wave_period_max",
        "forecast_days": 7,
    }
    resp = await client.get(OPEN_METEO_MARINE_URL, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_rainviewer_radar(client: httpx.AsyncClient) -> dict[str, Any]:
    """Recupera i frame radar osservati (ultime 2h) e i frame nowcast (prossimi 30m) da RainViewer."""
    resp = await client.get(RAINVIEWER_MAPS_URL)
    resp.raise_for_status()
    data = resp.json()
    host = data.get("host", "https://tilecache.rainviewer.com")
    radar = data.get("radar", {})
    past_frames = radar.get("past", [])[-6:]
    nowcast_frames = radar.get("nowcast", [])[:4]

    def format_frame(f: dict[str, Any], is_nowcast: bool) -> dict[str, Any]:
        ts = int(f.get("time", 0))
        path = f.get("path", "")
        dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")
        return {
            "timestamp": ts,
            "time_label": dt_str,
            "is_nowcast": is_nowcast,
            "tile_url_template": f"{host}{path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png",
        }

    frames = [format_frame(f, False) for f in past_frames] + [
        format_frame(f, True) for f in nowcast_frames
    ]
    return {
        "host": host,
        "generated": data.get("generated"),
        "frames": frames,
        "latest_tile_url": frames[-1]["tile_url_template"] if frames else None,
    }


async def fetch_optional_commercial_sources(
    client: httpx.AsyncClient, lat: float, lon: float, sea_lat: float, sea_lon: float
) -> dict[str, Any]:
    """Interroga i provider commerciali opzionali se le rispettive API Key sono presenti in `.env`."""
    settings = get_settings()
    extra: dict[str, Any] = {}

    if settings.tomorrow_api_key:
        try:
            r = await client.get(
                TOMORROW_TIMELINES_URL,
                params={
                    "location": f"{lat},{lon}",
                    "timesteps": "1h",
                    "units": "metric",
                    "apikey": settings.tomorrow_api_key,
                },
            )
            if r.status_code == 200:
                extra["tomorrow_io"] = {"status": "ok", "sample": r.json()}
        except Exception:
            extra["tomorrow_io"] = {"status": "degraded"}

    if settings.weatherapi_key:
        try:
            r = await client.get(
                WEATHERAPI_FORECAST_URL,
                params={
                    "key": settings.weatherapi_key,
                    "q": f"{lat},{lon}",
                    "days": 2,
                    "aqi": "no",
                    "alerts": "yes",
                },
            )
            if r.status_code == 200:
                extra["weatherapi"] = {"status": "ok", "sample": r.json()}
        except Exception:
            extra["weatherapi"] = {"status": "degraded"}

    if settings.stormglass_api_key:
        try:
            r = await client.get(
                STORMGLASS_POINT_URL,
                params={
                    "lat": sea_lat,
                    "lng": sea_lon,
                    "params": "waveHeight,wavePeriod,waveDirection,windSpeed,windDirection,waterTemperature",
                },
                headers={"Authorization": settings.stormglass_api_key},
            )
            if r.status_code == 200:
                extra["stormglass_marine"] = {"status": "ok", "sample": r.json()}
        except Exception:
            extra["stormglass_marine"] = {"status": "degraded"}

    return extra


async def fetch_all_raw_sources(
    lat: float, lon: float, sea_lat: float, sea_lon: float
) -> dict[str, Any]:
    """Esegue il fetch parallelo con isolamento dei guasti (ADR-0002 Circuit Breaker)."""
    settings = get_settings()
    sources_active: list[str] = []
    sources_degraded: list[str] = []

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        results = await asyncio.gather(
            fetch_open_meteo_multimodel(client, lat, lon),
            fetch_open_meteo_marine(client, sea_lat, sea_lon),
            fetch_rainviewer_radar(client),
            fetch_optional_commercial_sources(client, lat, lon, sea_lat, sea_lon),
            fetch_metno_compact(client, lat, lon),
            fetch_arpal_official_bulletins(client),
            fetch_omirl_live_observations(client, lat, lon),
            return_exceptions=True,
        )

    (
        multimodel_raw,
        marine_raw,
        radar_raw,
        commercial_raw,
        metno_raw,
        arpal_raw,
        omirl_raw,
    ) = results

    if isinstance(multimodel_raw, Exception) or not isinstance(multimodel_raw, dict):
        sources_degraded.append("open_meteo_multimodel")
        multimodel_raw = {}
    else:
        sources_active.extend(
            [
                "meteofrance_arome_1.3km",
                "dwd_icon_d2_2km",
                "ecmwf_ifs_9km",
                "ncep_gfs",
                "open_meteo_minutely_15",
            ]
        )

    if isinstance(marine_raw, Exception) or not isinstance(marine_raw, dict):
        sources_degraded.append("open_meteo_marine")
        marine_raw = {}
    else:
        sources_active.append("open_meteo_marine_ligurian_sea")

    if isinstance(radar_raw, Exception) or not isinstance(radar_raw, dict):
        sources_degraded.append("rainviewer_radar")
        radar_raw = {
            "host": "https://tilecache.rainviewer.com",
            "frames": [],
            "latest_tile_url": None,
        }
    else:
        sources_active.append("rainviewer_radar_monte_settepani")

    if isinstance(commercial_raw, dict):
        for k, v in commercial_raw.items():
            if isinstance(v, dict) and v.get("status") == "ok":
                sources_active.append(k)
            else:
                sources_degraded.append(k)
    else:
        commercial_raw = {}

    if isinstance(metno_raw, Exception) or not isinstance(metno_raw, dict):
        sources_degraded.append("met_norway")
        metno_raw = {}
    else:
        sources_active.append("met_norway_nordic")

    if isinstance(arpal_raw, Exception) or not isinstance(arpal_raw, dict):
        sources_degraded.append("arpal_liguria_bulletins")
        arpal_raw = {}
    else:
        sources_active.append("arpal_liguria_official")

    if isinstance(omirl_raw, Exception) or not isinstance(omirl_raw, dict):
        sources_degraded.append("omirl_stations_webcams")
        omirl_raw = {}
    else:
        sources_active.append("omirl_regione_liguria_sensors")

    return {
        "multimodel": multimodel_raw,
        "marine": marine_raw,
        "radar": radar_raw,
        "commercial": commercial_raw,
        "metno": metno_raw,
        "arpal_bulletins": arpal_raw,
        "omirl_observations": omirl_raw,
        "sources_active": sources_active,
        "sources_degraded": sources_degraded,
    }
