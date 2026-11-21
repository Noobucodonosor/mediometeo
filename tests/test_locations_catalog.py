"""Test suite per TASK-GEO-01 (ADR-0005): Catalogo Geografico Completo della Provincia di Genova (67 Comuni + 25 Quartieri + 20 Rade + 6 Valichi + Poligoni AMP Portofino)."""

from __future__ import annotations

from backend.locations import (
    AMP_PORTOFINO_ZONES,
    LOCATIONS_CATALOG,
    find_nearest_location,
    get_location,
    search_locations,
)


def test_complete_catalog_counts() -> None:
    """Verifica che il catalogo contenga tutti i 67 Comuni della Città Metropolitana di Genova, i 25 Quartieri, le 20 Rade/Porti e i 6 Valichi."""
    comuni = search_locations(loc_type="comune")
    quartieri = search_locations(loc_type="quartiere")
    rade = search_locations(loc_type="rada_porto")
    valichi = search_locations(loc_type="valico")

    assert len(comuni) == 67
    assert len(quartieri) == 25
    assert len(rade) == 20
    assert len(valichi) == 6
    assert len(LOCATIONS_CATALOG) == 118


def test_rade_have_bay_open_deg_and_amp_zones() -> None:
    """Ogni rada/porto deve avere l'angolo di apertura della cala `bay_open_deg` per il calcolo fisico della risacca."""
    rade = search_locations(loc_type="rada_porto")
    for r in rade:
        assert r["bay_open_deg"] is not None
        assert 0 <= r["bay_open_deg"] <= 360

    assert len(AMP_PORTOFINO_ZONES) == 3
    zone_ids = {z["id"] for z in AMP_PORTOFINO_ZONES}
    assert {"AMP-ZONA-A", "AMP-ZONA-B", "AMP-ZONA-C"} == zone_ids


def test_search_and_nearest_location_lookup() -> None:
    """Verifica la ricerca testuale e la prossimità geodetica."""
    res_portofino = search_locations(q="Portofino")
    assert len(res_portofino) >= 2

    loc_genova = get_location("COM-GENOVA")
    assert loc_genova is not None
    assert loc_genova.name == "Genova"

    near_sf = find_nearest_location(44.3152, 9.1748, preferred_category="sea")
    assert "San Fruttuoso" in near_sf.name
