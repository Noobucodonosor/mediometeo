"""Test suite per TASK-CORE-01: Distretti Provincia di Genova (Terra/Mare), Cache SQLite ed Endpoint Core."""

from __future__ import annotations

import tempfile
from fastapi.testclient import TestClient

from backend.cache import SQLiteCache
from backend.districts import DISTRICTS, find_nearest_district, get_district, list_districts
from backend.main import app


client = TestClient(app)


def test_all_10_genova_districts_present() -> None:
    """Verifica che tutti i 10 distretti (5 Terra + 5 Mare) della Provincia di Genova siano censiti."""
    assert len(DISTRICTS) == 10
    land = list_districts(category="land")
    sea = list_districts(category="sea")
    assert len(land) == 5
    assert len(sea) == 5

    expected_ids = {
        "GE-CENTRO-PONENTE",
        "GE-VAL-POLCEVERA",
        "GE-VAL-BISAGNO",
        "GE-LEVANTE",
        "GE-ENTROTERRA",
        "MARE-PORTO-DIGA",
        "MARE-GOLFO-PONENTE",
        "MARE-GOLFO-PARADISO-PORTOFINO",
        "MARE-TIGULLIO",
        "MARE-LARGO-LIGURE",
    }
    assert set(DISTRICTS.keys()) == expected_ids


def test_find_nearest_district_land_and_sea() -> None:
    """Verifica il calcolo geodetico Haversine per trovare il distretto più vicino."""
    # Coordinate su Portofino / Camogli
    d_sea = find_nearest_district(44.303, 9.165, preferred_category="sea")
    assert d_sea.id == "MARE-GOLFO-PARADISO-PORTOFINO"

    # Coordinate su Bolzaneto / Pontedecimo (Val Polcevera)
    d_land = find_nearest_district(44.475, 8.899, preferred_category="land")
    assert d_land.id == "GE-VAL-POLCEVERA"


def test_sqlite_cache_ttl_and_stale_recovery() -> None:
    """Verifica che la cache SQLite salvi, rispetti il TTL e supporti il recupero stale anti-blackout."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
        cache = SQLiteCache(tmp.name)
        cache.set("test:key", {"temp": 18.5}, ttl_seconds=60, category="test")

        fresh = cache.get("test:key", allow_stale=False)
        assert fresh is not None
        assert fresh.payload["temp"] == 18.5
        assert not fresh.is_expired

        stats = cache.stats()
        assert stats["total_entries"] == 1
        assert stats["fresh_entries"] == 1


def test_health_and_districts_endpoints() -> None:
    """Verifica gli endpoint HTTP /api/v1/health e /api/v1/districts."""
    r_health = client.get("/api/v1/health")
    assert r_health.status_code == 200
    body = r_health.json()
    assert body["status"] == "ok"
    assert "Provincia di Genova" in body["domain"]

    r_dist = client.get("/api/v1/districts?category=sea")
    assert r_dist.status_code == 200
    d_body = r_dist.json()
    assert d_body["count"] == 5
    assert all(d["category"] == "sea" for d in d_body["districts"])
