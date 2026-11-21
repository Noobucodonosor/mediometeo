"""Test suite per TASK-MAR-01 (ADR-0003, ADR-0006): Motore Meteo-Marino, Beaufort, Douglas, Wave Steepness e Fisica Costiera."""

from __future__ import annotations

from backend.engine.marine import (
    compute_wave_dynamics,
    hs_to_douglas,
    kmh_to_knots,
    knots_to_beaufort,
)


def test_knots_and_beaufort_scale() -> None:
    """Verifica la conversione km/h -> nodi e la classificazione Beaufort."""
    kt = kmh_to_knots(55.56)  # ~30 nodi
    assert 29.8 <= kt <= 30.2
    bf = knots_to_beaufort(kt)
    assert bf["force"] == 7
    assert "Vento forte" in bf["label"]


def test_douglas_sea_scale() -> None:
    """Verifica la corrispondenza altezza significativa Hs -> Scala Douglas."""
    assert hs_to_douglas(0.3)["degree"] == 2  # Poco mosso
    assert hs_to_douglas(0.9)["degree"] == 3  # Mosso
    assert hs_to_douglas(1.8)["degree"] == 4  # Molto mosso
    assert hs_to_douglas(3.2)["degree"] == 5  # Agitato


def test_wave_steepness_warning_on_short_chop() -> None:
    """Un'onda di 1.3m con periodo corto di 3.8s (tipica di Tramontana/Grecale fuori diga) deve attivare lo steepness warning."""
    res = compute_wave_dynamics(
        hs_m=1.3,
        period_s=3.8,
        wave_dir_deg=15.0,
        wind_speed_kmh=45.0,
        wind_gust_kmh=68.0,
        wind_dir_deg=10.0,
        sst_c=16.5,
    )
    assert res["waves"]["steepness_warning"] is True
    assert res["waves"]["max_height_m"] > 2.0
    assert res["waves"]["steepness_pct"] > 5.0


def test_calm_summer_sea_pure_physics() -> None:
    """Con mare quasi calmo (Hs 0.2m, vento 5 kt) verifica che i parametri fisici siano calcolati senza semafori soggettivi."""
    res = compute_wave_dynamics(
        hs_m=0.2,
        period_s=5.0,
        wave_dir_deg=210.0,
        wind_speed_kmh=9.0,
        wind_gust_kmh=12.0,
        wind_dir_deg=190.0,
        sst_c=23.0,
    )
    assert "activities_safety" not in res
    assert res["waves"]["douglas"]["degree"] == 2
    assert res["waves"]["steepness_warning"] is False
    assert res["coastal_physics"]["visibility_nm"] > 0
