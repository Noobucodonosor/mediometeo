"""Test suite per TASK-PHY-01 (ADR-0006): Fisica Costiera Pura (Zero Semafori in Mare, Maree, Risacca Rade, Correnti) e Calcolatore Rotta ETA su Grafo AMP."""

from __future__ import annotations

from backend.engine.coastal_route import (
    compute_coastal_route_eta,
    find_shortest_coastal_path,
)
from backend.engine.marine import (
    compute_bay_surge_physics,
    compute_wave_dynamics,
    extract_tides_from_sea_level,
)


def test_zero_subjective_traffic_lights_in_marine_engine() -> None:
    """Verifica che in modalità MARE non esista alcun semaforo soggettivo `activities_safety` o `overall_level`, ma solo fisica pura."""
    res = compute_wave_dynamics(
        hs_m=1.2,
        period_s=7.5,
        wave_dir_deg=200.0,
        wind_wave_m=0.5,
        swell_wave_m=1.05,
        swell_period_s=8.0,
        swell_dir_deg=200.0,
        wind_speed_kmh=28.0,
        wind_gust_kmh=42.0,
        wind_dir_deg=195.0,
        bay_open_deg=200,
    )
    assert "activities_safety" not in res
    assert "overall_level" not in res
    assert res["wind"]["speed_knots"] > 0
    assert res["wind"]["speed_ms"] > 0
    assert res["waves"]["significant_height_m"] == 1.2
    assert res["waves"]["max_height_m"] == 1.98
    assert res["waves"]["extreme_height_1_1000_m"] > res["waves"]["max_height_m"]
    assert res["coastal_physics"]["bay_surge"]["shore_breaker_height_m"] > 1.0
    assert res["coastal_physics"]["surface_current"]["speed_knots"] > 0
    assert res["coastal_physics"]["visibility_nm"] > 0


def test_bay_surge_frontal_vs_sheltered() -> None:
    """Una cala aperta a 200° (es. San Fruttuoso) con swell da 200° subisce risacca molto maggiore di una cala riparata a 120° (Portofino)."""
    frontal = compute_bay_surge_physics(
        swell_hs_m=1.0,
        swell_period_s=8.5,
        swell_dir_deg=200.0,
        bay_open_deg=200,
        tide_phase="Crescente (Flusso ↑)",
    )
    sheltered = compute_bay_surge_physics(
        swell_hs_m=1.0,
        swell_period_s=8.5,
        swell_dir_deg=200.0,
        bay_open_deg=60,
        tide_phase="Calante (Riflusso ↓)",
    )
    assert frontal["refraction_kr"] == 1.0
    assert frontal["shore_breaker_height_m"] > sheltered["shore_breaker_height_m"] * 2.5


def test_tides_extraction_from_sea_level() -> None:
    """Verifica l'estrazione degli estremi HIGH/LOW e della fase di marea da `sea_level_height_msl`."""
    times = [f"2026-11-09T{h:02d}:00" for h in range(12)]
    levels = [0.05, 0.12, 0.25, 0.34, 0.28, 0.15, 0.04, 0.01, 0.08, 0.19, 0.31, 0.27]
    tides = extract_tides_from_sea_level(times, levels, current_idx=1)
    assert "Crescente" in tides["current_phase"]
    assert tides["range_cm"] == 33
    assert any(e["type"] == "HIGH" for e in tides["extrema"])
    assert any(e["type"] == "LOW" for e in tides["extrema"])


def test_coastal_route_never_cuts_across_portofino_promontory() -> None:
    """Da Camogli a Portofino la rotta deve circumnavigare Punta Chiappa, San Fruttuoso e il Faro di Portofino rispettando i limiti AMP."""
    path = find_shortest_coastal_path("camogli", "portofino")
    wp_ids = [w["id"] for w in path["waypoints"]]
    assert wp_ids == [
        "camogli",
        "punta_chiappa",
        "san_fruttuoso",
        "faro_portofino",
        "portofino",
    ]

    eta_plan = compute_coastal_route_eta(
        origin_id="portofino",
        dest_id="san_fruttuoso",
        cruise_speed_knots=12.0,  # Verrà limitato a 5 kt nei segmenti AMP Zona B
        duration_minutes=90,
        stop_minutes=20,
        round_trip=True,
    )
    assert eta_plan["total_distance_nm"] > 2.0
    assert eta_plan["required_average_speed_knots"] > 0
    assert "latest_turnaround_time" in eta_plan["schedule"]
