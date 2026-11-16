"""Test End-to-End per TASK-UI-01 & TASK-UX-01: API Nowcast/Forecast/Marine/Locations/Observations/Route-ETA, 6 Schede Chiuse e /orologio."""

from __future__ import annotations

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
