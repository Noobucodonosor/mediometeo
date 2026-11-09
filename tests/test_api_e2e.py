"""Test End-to-End per TASK-UI-01: API Nowcast/Forecast/Marine/Alerts, PWA assets e Mappa Genova."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_pwa_root_and_static_assets() -> None:
    """Verifica che la Web App PWA serva correttamente HTML, CSS, JS, manifest e service worker."""
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "MedioMeteo Genova" in r_index.text
    assert 'meta name="color-scheme"' in r_index.text

    r_manifest = client.get("/manifest.json")
    assert r_manifest.status_code == 200
    assert r_manifest.json()["short_name"] == "MedioMeteo GE"

    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert "mediometeo-genova-v1" in r_sw.text


def test_forecast_and_marine_endpoints_e2e() -> None:
    """Verifica end-to-end gli endpoint /api/v1/forecast, /api/v1/marine e /api/v1/ai-bulletin."""
    r_fc = client.get("/api/v1/forecast?district=GE-CENTRO-PONENTE&mode=land")
    assert r_fc.status_code == 200
    fc_data = r_fc.json()
    assert fc_data["district"]["id"] == "GE-CENTRO-PONENTE"
    assert "nowcast" in fc_data
    assert "land" in fc_data
    assert "sea" in fc_data
    assert len(fc_data["forecast"]["hourly_48h"]) > 0

    r_mar = client.get("/api/v1/marine?district=MARE-PORTO-DIGA")
    assert r_mar.status_code == 200
    mar_data = r_mar.json()
    assert mar_data["district"]["id"] == "MARE-PORTO-DIGA"
    assert "waves" in mar_data["current_marine"]
    assert "wind" in mar_data["current_marine"]
    assert "activities_safety" in mar_data["current_marine"]

    r_ai = client.get("/api/v1/ai-bulletin?district=GE-VAL-POLCEVERA&mode=both")
    assert r_ai.status_code == 200
    ai_data = r_ai.json()
    assert ai_data["district_id"] == "GE-VAL-POLCEVERA"
    assert "headline" in ai_data
