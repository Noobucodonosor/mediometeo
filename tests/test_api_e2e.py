"""Test End-to-End per TASK-UI-01 & TASK-UX-01: API Nowcast/Forecast/Marine/Locations/Observations/Route-ETA, 6 Schede Chiuse e /orologio."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_pwa_root_6tabs_and_smartwatch_view() -> None:
    """Verifica che la Web App PWA serva le 6 schede chiuse (`tab-mappa` attiva all'avvio) e la vista `/orologio`."""
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "MedioMeteo Genova" in r_index.text
    assert 'meta name="color-scheme"' in r_index.text
    assert 'id="tab-adesso"' in r_index.text
    assert 'id="tab-nowcast"' in r_index.text
    assert 'id="tab-mappa" class="tab-panel active"' in r_index.text
    assert 'id="tab-modelli"' in r_index.text
    assert 'id="tab-rotta"' in r_index.text
    assert 'id="tab-bollettini"' in r_index.text
    assert 'class="telemetry-hud"' in r_index.text
    assert 'id="svg-nautical-compass"' in r_index.text
    assert 'class="map-floating-top"' in r_index.text
    assert 'id="loc-picker-btn"' in r_index.text
    assert 'role="toolbar"' in r_index.text
    assert "Verità osservativa" not in r_index.text

    r_watch = client.get("/orologio")
    assert r_watch.status_code == 200
    assert "MEDIOMETEO HUD" in r_watch.text
    assert 'id="watch-svg-compass"' in r_watch.text
    assert 'id="watch-speed"' in r_watch.text
    assert 'IBM Plex Mono' in r_watch.text

    r_manifest = client.get("/manifest.json")
    assert r_manifest.status_code == 200
    assert r_manifest.json()["short_name"] == "MedioMeteo GE"

    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert 'mediometeo-genova-v' in r_sw.text


@pytest.mark.live
def test_locations_observations_forecast_marine_and_route_e2e() -> None:
    """Verifica end-to-end gli endpoint /api/v1/locations, /api/v1/observations, /api/v1/forecast, /api/v1/marine e /api/v1/route-eta."""
    r_locs = client.get("/api/v1/locations")
    assert r_locs.status_code == 200
    locs_data = r_locs.json()
    assert locs_data["count"] == 118
    assert len(locs_data["amp_portofino_zones"]) == 3

    r_obs = client.get("/api/v1/observations?location=COM-GENOVA")
    assert r_obs.status_code == 200
    obs_data = r_obs.json()
    assert "live_sensors_count" in obs_data["observations_live"]
    assert "all_weather_stations" in obs_data["observations_live"]
    assert len(obs_data["observations_live"]["nearest_weather_stations"]) > 0
    assert len(obs_data["observations_live"]["nearest_river_hydrometers"]) > 0
    assert len(obs_data["observations_live"]["nearest_webcams"]) > 0

    r_fc = client.get("/api/v1/forecast?location=COM-PORTOFINO&mode=land")
    assert r_fc.status_code == 200
    fc_data = r_fc.json()
    assert fc_data["location"]["id"] == "COM-PORTOFINO"
    assert "observations_live" in fc_data
    assert "nowcast" in fc_data
    assert "land" in fc_data
    assert "sea" in fc_data
    assert len(fc_data["forecast"]["hourly_48h"]) > 0
    first_hour_models = fc_data["forecast"]["hourly_48h"][0]["models"]
    assert "meteofrance_arome_france_hd" in first_hour_models
    assert "icon_d2" in first_hour_models
    assert "ecmwf_ifs025" in first_hour_models
    assert "gfs_seamless" in first_hour_models
    assert "met_norway" in first_hour_models

    r_mar = client.get("/api/v1/marine?district=MARE-PORTO-DIGA")
    assert r_mar.status_code == 200
    mar_data = r_mar.json()
    assert "waves" in mar_data["current_marine"]
    assert "wind" in mar_data["current_marine"]
    assert "coastal_physics" in mar_data["current_marine"]
    assert "activities_safety" not in mar_data["current_marine"]

    r_route = client.get("/api/v1/route-eta?origin=camogli&dest=portofino&cruise_knots=6&duration_min=90&stop_min=15")
    assert r_route.status_code == 200
    route_data = r_route.json()
    assert route_data["total_distance_nm"] > 4.0
    assert "latest_turnaround_time" in route_data["schedule"]

    r_ai = client.get("/api/v1/ai-bulletin?location=COM-GENOVA&mode=both")
    assert r_ai.status_code == 200
    ai_data = r_ai.json()
    assert "headline" in ai_data


def test_locations_observations_forecast_marine_and_route_offline_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Contract test E2E 100% deterministico offline con payload realistici (TASK-QA-01 / #31)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from backend.cache import SQLiteCache
    from backend.main import app as fastapi_app

    now_rome = datetime.now(ZoneInfo("Europe/Rome")).replace(minute=0, second=0, microsecond=0)
    hourly_times = [(now_rome + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(48)]
    minutely_times = [(now_rome + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(16)]
    daily_times = [(now_rome + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    async def mock_fetch_all_raw_sources(lat: float, lon: float, sea_lat: float, sea_lon: float) -> dict:
        return {
            "multimodel": {
                "hourly": {
                    "time": hourly_times,
                    "temperature_2m_ecmwf_ifs025": [17.5] * 48,
                    "temperature_2m_icon_d2": [17.2] * 48,
                    "precipitation_ecmwf_ifs025": [0.2] * 48,
                    "precipitation_meteofrance_arome_france_hd": [0.4] * 48,
                    "wind_speed_10m_ecmwf_ifs025": [18.0] * 48,
                    "wind_speed_10m_icon_d2": [20.0] * 48,
                    "wind_gusts_10m_ecmwf_ifs025": [28.0] * 48,
                    "wind_direction_10m_ecmwf_ifs025": [160.0] * 48,
                    "relative_humidity_2m_ecmwf_ifs025": [72.0] * 48,
                    "pressure_msl_ecmwf_ifs025": [1014.0] * 48,
                    "cloud_cover_ecmwf_ifs025": [45.0] * 48,
                    "weather_code_ecmwf_ifs025": [2] * 48,
                },
                "minutely_15": {
                    "time": minutely_times,
                    "precipitation": [0.1] * 16,
                    "wind_speed_10m": [18.5] * 16,
                    "wind_gusts_10m": [27.0] * 16,
                    "wind_direction_10m": [155.0] * 16,
                    "temperature_2m": [17.4] * 16,
                },
                "daily": {
                    "time": daily_times,
                    "temperature_2m_max": [20.0] * 7,
                    "temperature_2m_min": [13.0] * 7,
                    "precipitation_sum": [1.5] * 7,
                    "wind_speed_10m_max": [22.0] * 7,
                    "wind_gusts_10m_max": [34.0] * 7,
                    "weather_code": [2] * 7,
                },
            },
            "marine": {
                "hourly": {
                    "time": hourly_times,
                    "wave_height": [0.7] * 48,
                    "wave_period": [5.5] * 48,
                    "wave_direction": [190.0] * 48,
                    "wind_wave_height": [0.5] * 48,
                    "swell_wave_height": [0.3] * 48,
                    "sea_surface_temperature": [18.2] * 48,
                    "ocean_current_velocity": [0.35] * 48,
                    "ocean_current_direction": [285.0] * 48,
                }
            },
            "radar": {"host": "https://tilecache.rainviewer.com", "frames": [], "latest_tile_url": None},
            "commercial": {},
            "metno": {
                hourly_times[0]: {
                    "temp_c": 17.6,
                    "wind_kmh": 19.0,
                    "gust_kmh": 27.0,
                    "wind_dir_deg": 165.0,
                    "precip_mm": 0.1,
                    "pressure_hpa": 1014.5,
                }
            },
            "arpal_bulletins": {"live_extracted": False, "source": "ARPAL", "days": []},
            "omirl_observations": {
                "live_sensors_count": {"wind_stations": 1, "total_weather_stations": 1, "river_hydrometers": 1, "buoys": 1},
                "nearest_weather_stations": [
                    {
                        "code": "GEPOA",
                        "name": "Genova Porto Antico",
                        "muni": "Genova",
                        "lat": 44.4065,
                        "lon": 8.926,
                        "elev_m": 5,
                        "distance_km": 0.5,
                        "observed_at": "12:00",
                        "temp_c": 17.5,
                        "precip_1h_mm": 0.0,
                        "wind_kmh": 18.0,
                        "wind_knots": 9.7,
                        "gust_kmh": 24.8,
                        "gust_knots": 13.4,
                        "wind_dir_deg": 160,
                        "is_live_rest": True,
                    }
                ],
                "all_weather_stations": [],
                "nearest_river_hydrometers": [
                    {
                        "code": "FIRPO",
                        "name": "Genova Firpo",
                        "river": "Bisagno",
                        "lat": 44.4155,
                        "lon": 8.951,
                        "distance_km": 1.2,
                        "observed_at": "12:00",
                        "level_m": 0.65,
                        "warn_threshold_m": 2.5,
                        "alarm_threshold_m": 4.0,
                        "status_level": "green",
                    }
                ],
                "all_river_hydrometers": [],
                "nearest_webcams": [],
                "all_webcams": [],
                "marine_wave_buoy": None,
            },
            "sources_active": ["ecmwf_ifs_9km", "dwd_icon_d2_2km", "met_norway_nordic"],
            "sources_degraded": [],
        }

    old_cache = getattr(fastapi_app.state, "cache", None)
    fastapi_app.state.cache = SQLiteCache(str(tmp_path / "offline_contract.sqlite"))
    monkeypatch.setattr("backend.main.fetch_all_raw_sources", mock_fetch_all_raw_sources)
    try:
        r_fc = client.get("/api/v1/forecast?location=COM-PORTOFINO&mode=land&refresh=true")
        assert r_fc.status_code == 200
        fc_data = r_fc.json()
        assert fc_data["location"]["id"] == "COM-PORTOFINO"
        assert len(fc_data["forecast"]["hourly_48h"]) == 48
        assert "met_norway" in fc_data["forecast"]["hourly_48h"][0]["models"]

        r_mar = client.get("/api/v1/marine?district=MARE-PORTO-DIGA")
        assert r_mar.status_code == 200
        assert "activities_safety" not in r_mar.json()["current_marine"]

        r_route = client.get("/api/v1/route-eta?origin=camogli&dest=portofino&cruise_knots=6&duration_min=90&stop_min=15")
        assert r_route.status_code == 200
        assert r_route.json()["total_distance_nm"] > 4.0

        r_ai = client.get("/api/v1/ai-bulletin?location=COM-GENOVA&mode=both")
        assert r_ai.status_code == 200
        assert "headline" in r_ai.json()
    finally:
        fastapi_app.state.cache = old_cache
