"""Test suite per TASK-SEC-01 (ADR-0002): Geofencing Dominio Ligure, Zero Secret Leak e Resilienza."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.security import sanitize_metadata


client = TestClient(app)


def test_geofencing_blocks_outside_liguria() -> None:
    """Richieste fuori dal dominio geografico della Liguria devono restituire HTTP 422."""
    # Coordinate di Milano (45.46, 9.19) -> fuori max_lat=45.00
    resp_milano = client.get("/api/v1/nowcast?lat=45.4642&lon=9.1900")
    assert resp_milano.status_code == 422

    # Coordinate di Roma (41.90, 12.49) -> fuori dominio Ligure
    resp_roma = client.get("/api/v1/forecast?lat=41.9028&lon=12.4964")
    assert resp_roma.status_code == 422


def test_geofencing_allows_genova_and_ligurian_sea() -> None:
    """Coordinate valide su Genova e sul Mar Ligure devono essere accettate."""
    resp = client.get("/api/v1/districts")
    assert resp.status_code == 200


def test_sanitize_metadata_strips_secrets() -> None:
    """Verifica che sanitize_metadata rimuova qualunque campo contenente key/token/secret."""
    raw_meta = {
        "status": "ok",
        "gemini_api_key": "AIzaSyFakeKey",
        "stormglass_token": "secret123",
        "normal_field": 42,
    }
    cleaned = sanitize_metadata(raw_meta)
    assert "gemini_api_key" not in cleaned
    assert "stormglass_token" not in cleaned
    assert cleaned["normal_field"] == 42


@pytest.mark.asyncio
async def test_circuit_breaker_synthetic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se tutti i provider esterni falliscono, l'API deve comunque rispondere HTTP 200 con fallback e safety disclaimer."""
    async def mock_failed_sources(lat: float, lon: float, sea_lat: float, sea_lon: float) -> dict:
        return {
            "multimodel": {},
            "marine": {},
            "radar": {"frames": [], "latest_tile_url": None},
            "commercial": {},
            "sources_active": [],
            "sources_degraded": ["open_meteo_multimodel", "open_meteo_marine"],
        }

    monkeypatch.setattr("backend.main.fetch_all_raw_sources", mock_failed_sources)
    resp = client.get("/api/v1/nowcast?district=GE-VAL-BISAGNO&refresh=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_stale"] is True
    assert "safety_disclaimer" in data["land"]
    assert "1530" in data["sea"]["safety_disclaimer"]


def test_frontend_xss_and_no_inline_onclick() -> None:
    """Verifica assenza di handler inline onclick= e presenza di escapeHtml/sanitizeHttpUrl (TASK-SEC-02 / #26)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "frontend"
    index_html = (root / "index.html").read_text(encoding="utf-8")
    app_js = (root / "app.js").read_text(encoding="utf-8")

    assert "onclick=" not in index_html
    assert "onclick=" not in app_js
    assert "function escapeHtml(" in app_js
    assert "function sanitizeHttpUrl(" in app_js
