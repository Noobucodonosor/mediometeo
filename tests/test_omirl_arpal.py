"""Test suite per TASK-OBS-01 (ADR-0005): Connettore REST OMIRL, Idrometri Torrenti, Webcam Live, Parser ARPAL e 5° modello MET Norway."""

from __future__ import annotations

import httpx

from backend.engine.omirl_arpal import (
    GENOVA_HYDROMETERS_META,
    GENOVA_WEBCAMS_CATALOG,
    REFERENCE_OMIRL_STATIONS,
    _OMIRL_BULK_CACHE,
    extract_var_data,
    fetch_omirl_live_observations,
    fetch_omirl_station_chart,
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

    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    rome_now = datetime.now(ZoneInfo("Europe/Rome"))
    fresh_ts = (rome_now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
    stale_same_year_ts = (rome_now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
    future_2028_now = datetime(2028, 5, 1, 12, 30, tzinfo=ZoneInfo("Europe/Rome"))

    # Sensore CHIRI (Chiavari) fermo al 2023 deve essere scartato
    assert is_omirl_refdate_fresh("2023-04-19T14:40:00") is False
    # Sensore fermo da >6h nello stesso anno deve essere scartato
    assert is_omirl_refdate_fresh(stale_same_year_ts) is False
    # Sensore aggiornato entro 6h deve essere considerato fresco
    assert is_omirl_refdate_fresh(fresh_ts) is True
    # Nessuna time-bomb post-2027
    assert is_omirl_refdate_fresh("2028-05-01T12:00:00", now=future_2028_now) is True


async def test_fetch_omirl_station_chart_normalized_output() -> None:
    """Verifica la risposta normalizzata di `fetch_omirl_station_chart` (TASK-DATA-03)."""
    base_ms = 1794816000000  # 2026-11-16T08:00:00Z approx
    raw_points = [[base_ms + i * 600_000, 10.0 + i * 0.5] for i in range(30)]
    raw_points.append([base_ms + 30 * 600_000, -999.0])  # valore sentinella da filtrare

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/EMPTY/Vento"):
            return httpx.Response(200, json={"title": "Vuota", "subTitle": "", "dataSeries": []})
        return httpx.Response(
            200,
            json={
                "title": "Genova - Porto Antico",
                "subTitle": "Sensore reale",
                "dataSeries": [{"name": "Velocità media", "data": raw_points}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res_wind = await fetch_omirl_station_chart(client, "gepoa", "Vento")
        assert res_wind["code"] == "GEPOA"
        assert res_wind["sensor"] == "Vento"
        assert res_wind["available"] is True
        assert res_wind["unit"] == "km/h"
        assert res_wind["min_value"] == 10.0
        assert res_wind["max_value"] == 24.5
        assert len(res_wind["series"]) == 1
        assert len(res_wind["series"][0]["points"]) == 30
        assert len(res_wind["recent_24_points"]) == 24
        assert res_wind["recent_24_points"][-1]["value"] == 24.5
        assert ":" in res_wind["recent_24_points"][0]["timestamp"]

        res_temp = await fetch_omirl_station_chart(client, "gepoa", "Termo")
        assert res_temp["unit"] == "°C"

        res_rain = await fetch_omirl_station_chart(client, "gepoa", "Pluvio")
        assert res_rain["unit"] == "mm"

        res_idro = await fetch_omirl_station_chart(client, "firpo", "Idro")
        assert res_idro["unit"] == "m"

        res_empty = await fetch_omirl_station_chart(client, "empty", "Vento")
        assert res_empty["available"] is False
        assert res_empty["min_value"] is None
        assert res_empty["max_value"] is None
        assert res_empty["recent_24_points"] == []
        assert res_empty["series"] == []


async def test_fetch_omirl_live_observations_multi_sensor_fusion_and_buoy() -> None:
    """Verifica fusione Vento+Termo+Pluvio, flag has_live_*, Boa Capo Mele e total_weather_stations (TASK-DATA-03)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    fresh_date = (datetime.now(ZoneInfo("Europe/Rome")) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")
    stale_date = "2023-04-19T14:40:00"

    bulk_mock: dict[str, list[dict[str, object]]] = {
        "Vento": [
            {
                "shortCode": "GEPOA",
                "name": "Genova Porto Antico",
                "municipality": "Genova",
                "lat": 44.4065,
                "lon": 8.9260,
                "alt": 5,
                "value": 22.2,
                "increment": 180.0,
                "refDate": fresh_date,
            },
            {
                "shortCode": "RIGHI",
                "name": "Genova Righi",
                "municipality": "Genova",
                "lat": 44.4290,
                "lon": 8.9355,
                "alt": 356,
                "value": 18.5,
                "increment": 20.0,
                "refDate": fresh_date,
            },
            {
                "shortCode": "OUTBX",
                "name": "Fuori Provincia",
                "lat": 44.3000,
                "lon": 8.1000,
                "value": 30.0,
                "increment": 90.0,
                "refDate": fresh_date,
            },
        ],
        "Termo": [
            {
                "shortCode": "GEPOA",
                "name": "Genova Porto Antico",
                "municipality": "Genova",
                "lat": 44.4065,
                "lon": 8.9260,
                "alt": 5,
                "value": 17.4,
                "refDate": fresh_date,
            },
            {
                "shortCode": "GEPEG",
                "name": "Genova Pegli",
                "municipality": "Genova",
                "lat": 44.4260,
                "lon": 8.8160,
                "alt": 12,
                "value": 16.8,
                "refDate": fresh_date,
            },
            {
                "shortCode": "CHIRI",
                "name": "Sensore Obsoleto",
                "lat": 44.3160,
                "lon": 9.3200,
                "value": 12.0,
                "refDate": stale_date,
            },
            {
                "shortCode": "BORGZ",
                "name": "Borzonasca Termo",
                "municipality": "Borzonasca",
                "lat": 44.4220,
                "lon": 9.3880,
                "alt": 180,
                "value": 13.5,
                "refDate": fresh_date,
            },
        ],
        "Pluvio": [
            {
                "shortCode": "GEPOA",
                "name": "Genova Porto Antico",
                "municipality": "Genova",
                "lat": 44.4065,
                "lon": 8.9260,
                "value": 1.2,
                "refDate": fresh_date,
            },
            {
                "shortCode": "GEPEG",
                "name": "Genova Pegli",
                "municipality": "Genova",
                "lat": 44.4260,
                "lon": 8.8160,
                "value": 0.4,
                "refDate": fresh_date,
            },
            {
                "shortCode": "PLVONLY",
                "name": "Genova Molassana Pluvio",
                "municipality": "Genova",
                "lat": 44.4550,
                "lon": 8.9720,
                "alt": 60,
                "value": 3.6,
                "refDate": fresh_date,
            },
        ],
        "Idro": [
            {
                "shortCode": "FIRPO",
                "name": "Genova Firpo",
                "municipality": "Genova",
                "lat": 44.4155,
                "lon": 8.9510,
                "alt": 14,
                "value": 0.85,
                "refDate": fresh_date,
            }
        ],
        "Boa": [
            {
                "shortCode": "BOACM",
                "name": "Boa Capo Mele (OMIRL)",
                "value": 1.45,
                "increment": 0.25,
                "refDate": fresh_date,
            }
        ],
        "webcam": [
            {
                "shortCode": "PANES",
                "imgPath": "images/cam_panes.jpg",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        sensor = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=bulk_mock.get(sensor, []))

    old_cache = dict(_OMIRL_BULK_CACHE)
    _OMIRL_BULK_CACHE["ts"] = 0.0
    _OMIRL_BULK_CACHE["payload"] = None
    try:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            obs = await fetch_omirl_live_observations(
                client,
                target_lat=44.407,
                target_lon=8.934,
                fallback_current={"wind_kmh": 11.0, "gust_kmh": 16.0, "wind_dir_deg": 45.0},
            )
    finally:
        _OMIRL_BULK_CACHE.update(old_cache)

    assert obs["live_sensors_count"]["wind_stations"] == 2
    assert obs["live_sensors_count"]["total_weather_stations"] == 5
    assert obs["live_sensors_count"]["river_hydrometers"] == 1
    assert obs["live_sensors_count"]["buoys"] == 1

    by_code = {s["code"]: s for s in obs["all_weather_stations"]}
    assert set(by_code.keys()) == {"GEPOA", "RIGHI", "GEPEG", "BORGZ", "PLVONLY"}

    # Stazione Vento con Termo e Pluvio live coincidenti
    assert by_code["GEPOA"]["sensor"] == "Vento"
    assert by_code["GEPOA"]["has_live_wind"] is True
    assert by_code["GEPOA"]["has_live_temp"] is True
    assert by_code["GEPOA"]["has_live_rain"] is True
    assert by_code["GEPOA"]["temp_c"] == 17.4
    assert by_code["GEPOA"]["precip_1h_mm"] == 1.2

    # Stazione Vento senza Termo/Pluvio coincidenti
    assert by_code["RIGHI"]["has_live_wind"] is True
    assert by_code["RIGHI"]["has_live_temp"] is False
    assert by_code["RIGHI"]["has_live_rain"] is False

    # Stazione Termo+Pluvio vicina a GEPOA (eredita vento di GEPOA)
    assert by_code["GEPEG"]["sensor"] == "Termo/Pluvio"
    assert by_code["GEPEG"]["has_live_wind"] is False
    assert by_code["GEPEG"]["has_live_temp"] is True
    assert by_code["GEPEG"]["has_live_rain"] is True
    assert by_code["GEPEG"]["is_live_rest"] is True
    assert by_code["GEPEG"]["wind_kmh"] == 22.2

    # Stazione Termo lontana (> 20km da anemometri) usa base_wind fallback
    assert by_code["BORGZ"]["sensor"] == "Termo/Pluvio"
    assert by_code["BORGZ"]["has_live_wind"] is False
    assert by_code["BORGZ"]["wind_kmh"] == 11.0

    # Stazione solo Pluvio
    assert by_code["PLVONLY"]["sensor"] == "Termo/Pluvio"
    assert by_code["PLVONLY"]["has_live_wind"] is False
    assert by_code["PLVONLY"]["has_live_temp"] is False
    assert by_code["PLVONLY"]["has_live_rain"] is True
    assert by_code["PLVONLY"]["precip_1h_mm"] == 3.6

    # Boa Capo Mele
    buoy = obs["marine_wave_buoy"]
    assert buoy is not None
    assert buoy["code"] == "BOACM"
    assert buoy["lat"] == 43.918
    assert buoy["lon"] == 8.185
    assert buoy["wave_hs_m"] == 1.45
    assert buoy["increment_m"] == 0.25

    # Idrometro arricchito con GENOVA_HYDROMETERS_META
    hy = obs["all_river_hydrometers"][0]
    assert hy["code"] == "FIRPO"
    assert hy["river"] == GENOVA_HYDROMETERS_META["FIRPO"]["river"]
    assert hy["warn_threshold_m"] == GENOVA_HYDROMETERS_META["FIRPO"]["warn_m"]


