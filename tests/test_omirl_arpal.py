"""Test suite per TASK-OBS-01 (ADR-0005): Connettore REST OMIRL, Idrometri Torrenti, Webcam Live, Parser ARPAL e 5° modello MET Norway."""

from __future__ import annotations

from backend.engine.omirl_arpal import (
    GENOVA_HYDROMETERS_META,
    GENOVA_WEBCAMS_CATALOG,
    REFERENCE_OMIRL_STATIONS,
    extract_var_data,
    is_omirl_refdate_fresh,
)


def test_extract_var_data_deterministic_brace_matcher() -> None:
    """Verifica che il brace-matcher `extract_var_data` estragga correttamente il JSON dal blocco `var data = {...};` di ARPAL Liguria."""
    sample_html = """
    <html><head><script>
    var other = 123;
    var data = {"previsioni": [{"dataPrevisione": "2026-11-09", "statoCielo": {"valore": "Cielo sereno o poco nuvoloso"}, "venti": {"valore": "Deboli settentrionali"}, "mare": {"valore": "Poco mosso"}}], "situazioneEdEvoluzione": {"valore": "Alta pressione sul Mar Ligure"}};
    </script></head></html>
    """
    extracted = extract_var_data(sample_html)
    assert extracted is not None
    assert extracted["situazioneEdEvoluzione"]["valore"] == "Alta pressione sul Mar Ligure"
    assert len(extracted["previsioni"]) == 1
    assert extracted["previsioni"][0]["mare"]["valore"] == "Poco mosso"


def test_omirl_stations_hydrometers_and_webcams_catalog() -> None:
    """Verifica la presenza delle stazioni reali OMIRL, degli idrometri con soglie in metri e delle webcam live."""
    hydrometers = [s for s in REFERENCE_OMIRL_STATIONS if s["sensor"] == "Idro"]
    weather_stations = [s for s in REFERENCE_OMIRL_STATIONS if s["sensor"] != "Idro"]

    assert len(hydrometers) >= 8
    assert len(weather_stations) >= 8
    for hy in hydrometers:
        assert hy["warn_m"] > 0
        assert hy["alarm_m"] > hy["warn_m"]
        assert "basin" in hy

    assert len(GENOVA_WEBCAMS_CATALOG) >= 10
    for cam in GENOVA_WEBCAMS_CATALOG:
        assert cam["stream_page_url"].startswith("https://")
        assert 44.1 <= cam["lat"] <= 44.7


def test_omirl_bulk_hydrometers_meta_and_freshness_filter() -> None:
    """Verifica i metadati dei 23+ idrometri reali genovesi e il filtro anti-sensori obsoleti (TASK-DATA-02)."""
    assert len(GENOVA_HYDROMETERS_META) >= 20
    assert "FIRPO" in GENOVA_HYDROMETERS_META
    assert "GEFER" in GENOVA_HYDROMETERS_META
    assert "GERIV" in GENOVA_HYDROMETERS_META
    assert "CARPB" in GENOVA_HYDROMETERS_META

    # Sensore CHIRI (Chiavari) fermo al 2023 deve essere scartato
    assert is_omirl_refdate_fresh("2023-04-19T14:40:00") is False
    # Sensore del 2026 deve essere considerato fresco
    assert is_omirl_refdate_fresh("2026-11-09T22:00:00") is True

