"""Test suite per TASK-ENG-01 (ADR-0003): Fusione Multi-Modello (AROME, ICON-D2, ECMWF) e Convergenza Ligure."""

from __future__ import annotations

from backend.districts import get_district
from backend.engine.ensemble import build_complete_weather_package, fuse_hourly_step
from backend.engine.ligurian_diagnostics import (
    detect_ligurian_convergence,
    evaluate_land_risk,
    ligurian_wind_name,
    vector_mean_deg,
)


def test_vector_mean_deg_handles_north_wraparound() -> None:
    """La media vettoriale tra 350° e 10° (Tramontana) deve essere 0° (Nord), non 180° (Sud)."""
    mean_dir = vector_mean_deg([350.0, 10.0], [0.5, 0.5])
    assert mean_dir == 0.0 or mean_dir == 360.0


def test_ligurian_wind_names() -> None:
    """Verifica la corretta identificazione di Tramontana Scura, Scirocco e Libeccio."""
    tramontana = ligurian_wind_name(5.0, speed_kmh=42.0)
    assert tramontana["name"] == "Tramontana Scura"
    assert tramontana["cardinal"] == "N"

    scirocco = ligurian_wind_name(135.0, speed_kmh=28.0)
    assert scirocco["name"] == "Scirocco"
    assert scirocco["cardinal"] == "SE"

    libeccio = ligurian_wind_name(225.0, speed_kmh=50.0)
    assert libeccio["name"] == "Libeccio"
    assert libeccio["cardinal"] == "SW"


def test_convergence_detector_triggers_on_tramontana_scirocco_shear() -> None:
    """Simula una classica convergenza su Genova (alto shear tra modelli LAM + pioggia + umidità)."""
    conv = detect_ligurian_convergence(
        wind_dir_deg=140.0,
        wind_speed_kmh=25.0,
        gust_kmh=52.0,
        precip_mm_h=12.5,
        humidity_pct=88.0,
        cape_j_kg=650.0,
        model_dir_spread_deg=135.0,
    )
    assert conv["active"] is True
    assert conv["convergence_score"] >= 65
    assert conv["level"] == "high"


def test_fuse_hourly_step_peak_preservation() -> None:
    """Se AROME 1.3km vede un nubifragio (24 mm/h) mentre GFS vede 2 mm/h, la fusione preserva il segnale intenso."""
    mock_hourly = {
        "temperature_2m_meteofrance_arome_france_hd": [15.0],
        "temperature_2m_icon_d2": [15.5],
        "temperature_2m_ecmwf_ifs025": [16.0],
        "temperature_2m_gfs_seamless": [16.2],
        "precipitation_meteofrance_arome_france_hd": [24.0],
        "precipitation_icon_d2": [18.0],
        "precipitation_ecmwf_ifs025": [6.0],
        "precipitation_gfs_seamless": [2.0],
        "wind_speed_10m_meteofrance_arome_france_hd": [35.0],
        "wind_gusts_10m_meteofrance_arome_france_hd": [68.0],
        "wind_direction_10m_meteofrance_arome_france_hd": [10.0],
        "wind_direction_10m_icon_d2": [145.0],
    }
    fused = fuse_hourly_step(mock_hourly, idx=0, lead_hours=1)
    assert fused["precip_max_lam_mm"] == 24.0
    assert fused["precip_mm"] >= 16.0
    assert fused["wind_dir_spread_deg"] >= 120.0


def test_land_risk_red_on_flash_flood_val_bisagno() -> None:
    """Con pioggia intensa (>35 mm/h) e convergenza attiva il rischio idrogeologico deve essere RED."""
    risk = evaluate_land_risk(
        precip_1h_mm=42.0,
        precip_3h_mm=85.0,
        precip_24h_mm=140.0,
        wind_kmh=40.0,
        gust_kmh=65.0,
        temp_c=14.0,
        visibility_m=2000.0,
        convergence_score=80,
        elevation_m=55,
    )
    assert risk["hydrogeological"]["level"] == "red"
    assert risk["overall_level"] == "red"
