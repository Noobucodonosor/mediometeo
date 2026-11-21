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

    orologio_html = (root / "orologio.html").read_text(encoding="utf-8")

    security_js = (root / "js" / "security.js").read_text(encoding="utf-8")

    assert "onclick=" not in index_html
    assert "onclick=" not in orologio_html
    assert "<script>" not in index_html
    assert "<script>" not in orologio_html
    assert "onclick=" not in app_js
    for js_file in (root / "js").glob("*.js"):
        js_src = js_file.read_text(encoding="utf-8")
        assert "onclick=" not in js_src
    assert "function escapeHtml(" in security_js
    assert "function sanitizeHttpUrl(" in security_js
    assert 'id="map-inspector-drawer"' in index_html
    assert 'id="liguria-watch-banner"' in index_html


def test_omirl_chart_validation_and_security_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica regex code su /api/v1/omirl-chart, errori sanitizzati, SRI e security headers (TASK-SEC-03 / #27)."""
    from pathlib import Path

    # 1. Path traversal / caratteri non ammessi -> 422
    bad_resp = client.get("/api/v1/omirl-chart?code=../etc&sensor=Vento")
    assert bad_resp.status_code == 422

    # 2. Errore upstream -> 502 sanitizzato senza leak di eccezioni raw
    async def mock_boom(*args, **kwargs):
        raise RuntimeError("SECRET_INTERNAL_TRACE_123")

    monkeypatch.setattr("backend.main.fetch_omirl_station_chart", mock_boom)
    err_resp = client.get("/api/v1/omirl-chart?code=GEPOA&sensor=Vento")
    assert err_resp.status_code == 502
    assert "SECRET_INTERNAL_TRACE_123" not in err_resp.text

    # 3. Security headers presenti sulle risposte HTTP
    health = client.get("/api/v1/health")
    assert health.headers.get("x-content-type-options") == "nosniff"
    assert health.headers.get("x-frame-options") == "DENY"
    assert "script-src 'self'" in (health.headers.get("content-security-policy") or "")

    # 4. Vendor locali self-hosted in index.html (zero dipendenza da CDN esterni per JS/CSS critici)
    index_html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/static/vendor/leaflet.css" in index_html
    assert "/static/vendor/leaflet.js" in index_html
    assert "/static/vendor/chart.umd.min.js" in index_html


def test_rate_limiter_and_circuit_breaker() -> None:
    """Verifica SlidingWindowRateLimiter (429) e CircuitBreaker (apertura dopo 3 errori) (TASK-SEC-04 / #28)."""
    from fastapi import HTTPException
    from backend.security import CircuitBreaker, SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("1.2.3.4")
    assert exc_info.value.status_code == 429

    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=300.0)
    assert cb.is_open("omirl") is False
    cb.record_failure("omirl")
    cb.record_failure("omirl")
    assert cb.is_open("omirl") is False
    cb.record_failure("omirl")
    assert cb.is_open("omirl") is True
    cb.record_success("omirl")
    assert cb.is_open("omirl") is False


def test_ai_bulletin_cache_key_includes_lon() -> None:
    """Verifica che la cache key di /api/v1/ai-bulletin includa sia lat che lon (TASK-SEC-04 / #28)."""
    from pathlib import Path

    main_src = (Path(__file__).resolve().parent.parent / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'b_key = f"ai:v2:{loc_key}:{mode}:{b_lat:.2f}:{b_lon:.2f}"' in main_src
