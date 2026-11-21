"""Test unitari per allineamento timezone MET Norway (UTC -> Europe/Rome) e assenza di copia silenziosa (TASK-ENG-02 / #25)."""

from backend.engine.ensemble import fuse_hourly_step
from backend.engine.omirl_arpal import metno_utc_to_rome_hour_key


def test_metno_utc_to_rome_hour_key_cet_and_cest():
    # Inverno (CET = UTC+1)
    assert metno_utc_to_rome_hour_key("2026-01-15T12:00:00Z") == "2026-01-15T13:00"
    assert metno_utc_to_rome_hour_key("2026-01-15T23:00:00Z") == "2026-01-16T00:00"

    # Estate (CEST = UTC+2)
    assert metno_utc_to_rome_hour_key("2026-07-15T12:00:00Z") == "2026-07-15T14:00"
    assert metno_utc_to_rome_hour_key("2026-07-15T23:00:00Z") == "2026-07-16T01:00"


def test_fuse_hourly_step_metno_aligned_and_no_silent_copy():
    hourly = {
        "temperature_2m_ecmwf_ifs025": [18.0, 19.0],
        "precipitation_ecmwf_ifs025": [0.0, 1.2],
        "wind_speed_10m_ecmwf_ifs025": [20.0, 25.0],
        "wind_gusts_10m_ecmwf_ifs025": [30.0, 35.0],
        "wind_direction_10m_ecmwf_ifs025": [180.0, 190.0],
    }
    rome_key = metno_utc_to_rome_hour_key("2026-07-15T12:00:00Z")
    assert rome_key == "2026-07-15T14:00"

    metno_by_hour = {
        rome_key: {
            "temp_c": 21.5,
            "precip_mm": 0.4,
            "wind_kmh": 14.4,
            "gust_kmh": 21.6,
            "wind_dir_deg": 210.0,
            "pressure_hpa": 1014.0,
        }
    }

    # Ora coperta da MET Norway
    step_hit = fuse_hourly_step(
        hourly=hourly,
        idx=0,
        lead_hours=1,
        time_iso="2026-07-15T14:00",
        metno_by_hour=metno_by_hour,
    )
    mn_hit = step_hit["models"]["met_norway"]
    assert mn_hit["available"] is True
    assert mn_hit["temp_c"] == 21.5
    assert mn_hit["wind_kmh"] == 14.4

    # Ora NON coperta da MET Norway: NON deve copiare ECMWF
    step_miss = fuse_hourly_step(
        hourly=hourly,
        idx=1,
        lead_hours=2,
        time_iso="2026-07-15T15:00",
        metno_by_hour=metno_by_hour,
    )
    mn_miss = step_miss["models"]["met_norway"]
    assert mn_miss["available"] is False
    assert mn_miss["temp_c"] is None
    assert mn_miss["wind_kmh"] is None
    assert mn_miss["wind_knots"] is None
