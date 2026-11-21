"""Analista Sinottico AI alimentato da Google Gemini (`google-genai`) con Fallback Fisico Ligure (ADR-0004, ADR-0006).

REGOLA FONDAMENTALE (Allineamento /grill-me #2 e #12):
- L'AI Advisor opera come **Analista Sinottico Puro**: spiega il *perché fisico* dei fenomeni
  (convergenza Tramontana Scura vs Scirocco, scarto tra AROME 1.3km / ICON-D2 2km / ECMWF / GFS / MET.no,
  evoluzione dello spettro d'onda Hs/Hmax/Tp, fase di marea, risacca in rada e riscontro con le stazioni OMIRL).
- In modalità MARE non esprime mai giudizi soggettivi paternalistici ("esci / non uscire"), lasciando la valutazione
  al comandante sulla base dei parametri fisici completi.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

from backend.config import get_settings

logger = logging.getLogger("mediometeo.ai_advisor")


def build_deterministic_synoptic_bulletin(
    weather_pkg: dict[str, Any], mode: str = "both"
) -> dict[str, Any]:
    """Genera un bollettino tecnico-sinottico completo basato sulle leggi fisiche liguri (Fallback 100% affidabile)."""
    district = weather_pkg["district"]
    loc = weather_pkg.get("location") or district
    now = weather_pkg["nowcast"]["current"]
    conv = weather_pkg["nowcast"]["ligurian_convergence"]
    land = weather_pkg["land"]["risk_assessment"]
    sea = weather_pkg["sea"]["marine_conditions"]
    hourly = weather_pkg["forecast"]["hourly_48h"]
    obs = weather_pkg.get("observations_live") or {}

    next_6h = hourly[:6] if hourly else [now]
    max_rain_6h = max((h["precip_mm"] for h in next_6h), default=0.0)
    max_gust_6h_kmh = max((h["gust_kmh"] for h in next_6h), default=now["gust_kmh"])
    max_gust_6h_kt = max((h["gust_knots"] for h in next_6h), default=sea["wind"]["gust_knots"])
    max_wave_6h_m = max((h["wave_hs_m"] for h in next_6h), default=sea["waves"]["significant_height_m"])

    # Analisi divergenza tra i 5 modelli (AROME, ICON-D2, ECMWF, GFS, MET.no)
    models_now = now.get("models") or {}
    arome_w = (models_now.get("meteofrance_arome_france_hd") or {}).get("wind_knots")
    icond2_w = (models_now.get("icon_d2") or {}).get("wind_knots")
    ecmwf_w = (models_now.get("ecmwf_ifs025") or {}).get("wind_knots")
    metno_w = (models_now.get("met_norway") or {}).get("wind_knots")

    nearest_st = (obs.get("nearest_weather_stations") or [None])[0]
    obs_clause = ""
    if nearest_st:
        obs_clause = (
            f" Stazione reale OMIRL più vicina: {nearest_st['name']} ({nearest_st['distance_km']} km) "
            f"rileva {nearest_st.get('wind_knots', now['wind_knots'])} kt e {nearest_st.get('temp_c', now['temp_c'])}°C."
        )

    synoptic_headline = (
        f"Analisi Sinottica su {loc['name']}: {now['weather_description']} "
        f"({now['temp_c']:.1f}°C), flusso da {now['wind_cardinal']} ({now['wind_ligurian_name']}) "
        f"e convergenza inter-modello {now['confidence_pct']}%."
    )

    if conv["active"]:
        synoptic_analysis = (
            f"CONVERGENZA LIGURE ATTIVA (Indice {conv['convergence_score']}/100): "
            f"{conv['explanation']} I modelli LAM non-idrostatici (AROME 1.3km: {arome_w} kt, ICON-D2 2km: {icond2_w} kt) "
            f"risolvono una linea di taglio orografica con picco precipitativo nelle prossime 6h fino a {max_rain_6h:.1f} mm/h "
            f"e raffiche fino a {max_gust_6h_kmh:.0f} km/h ({max_gust_6h_kt:.1f} kt).{obs_clause}"
        )
    else:
        synoptic_analysis = (
            f"Campo barico a {now['pressure_hpa']:.1f} hPa ({now['pressure_trend_label'].lower()}) "
            f"con ventilazione da {now['wind_ligurian_name']} ({now['wind_cardinal']}, {now['wind_dir_deg']:.0f}°). "
            f"Confronto 5 modelli sul vento attuale: AROME 1.3km={arome_w} kt, ICON-D2 2km={icond2_w} kt, "
            f"ECMWF 9km={ecmwf_w} kt, MET.no={metno_w} kt (Spread Δ={now['model_spread']['wind_spread_knots']} kt). "
            f"Nelle prossime 6h precipitazioni massime attese {max_rain_6h:.1f} mm/h.{obs_clause}"
        )

    thermo = land.get("thermo_comfort") or {}
    land_briefing = (
        f"• **Stato Bacini Idrografici & Sottopassi ({district['short_name']}):** {land['hydrogeological']['label']}. "
        f"{land['hydrogeological']['advice']}\n"
        f"• **Viadotti & Sopraelevata:** {land['wind_viability']['label']} "
        f"(Vento {now['wind_kmh']:.1f} km/h, raffica {now['gust_kmh']:.1f} km/h). "
        f"{land['wind_viability']['advice']}\n"
        f"• **Valichi Appenninici & Termo-Igrometria:** {land['appennino_passes']['label']} "
        f"(Zero termico {land['appennino_passes']['freezing_level_m']} m, Dew Point {thermo.get('dew_point_c', 11.0)}°C, "
        f"Stato: {thermo.get('maccaja_status', 'Assente')})."
    )

    bay_surge = sea["coastal_physics"]["bay_surge"]
    tides = sea["coastal_physics"]["tides"]
    curr = sea["coastal_physics"]["surface_current"]
    sea_briefing = (
        f"• **Cinematica del Vento ({loc['name']}):** {sea['wind']['ligurian_name']} ({sea['wind']['cardinal']}, {sea['wind']['direction_deg']:.0f}°) "
        f"a {sea['wind']['speed_knots']:.1f} kt ({sea['wind']['speed_ms']:.1f} m/s | {sea['wind']['speed_kmh']:.1f} km/h), "
        f"raffiche {sea['wind']['gust_knots']:.1f} kt (Forza {sea['wind']['beaufort']['force']} Beaufort — {sea['wind']['beaufort']['label']}).\n"
        f"• **Moto Ondoso & Spettro Completo dell'Onda:** Mare {sea['waves']['douglas']['label']} — Hs {sea['waves']['significant_height_m']:.2f} m, "
        f"Hmax statistica {sea['waves']['max_height_m']:.2f} m (trend 6h fino a {max_wave_6h_m:.2f} m), "
        f"Onda viva da vento {sea['waves']['wind_wave_height_m']:.2f} m + Swell lungo {sea['waves']['swell_height_m']:.2f} m @ Tp {sea['waves']['peak_period_s']:.1f} s "
        f"da {sea['waves']['direction_cardinal']} (L = {sea['waves']['wavelength_m']:.0f} m, {sea['waves']['steepness_class']}).\n"
        f"• **Fisica Costiera, Risacca & Marea:** Apertura cala {bay_surge['bay_open_axis_deg']}° ({bay_surge['exposure_geometry']}, "
        f"Kr={bay_surge['refraction_kr']}, Ks={bay_surge['shoaling_ks']}) → frangente/risacca a riva {bay_surge['shore_breaker_height_m']:.2f} m. "
        f"Marea {tides['current_height_cm']} cm ({tides['current_phase']}), corrente superficiale {curr['speed_knots']:.2f} kt da {curr['direction_cardinal']}, "
        f"visibilità {sea['coastal_physics']['visibility_nm']:.1f} NM."
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "deterministic_ligurian_synoptic_engine",
        "ai_powered": False,
        "mode": mode,
        "district_id": district["id"],
        "location_id": loc.get("id", district["id"]),
        "headline": synoptic_headline,
        "synoptic_nowcast_analysis": synoptic_analysis,
        "land_operational_briefing": land_briefing,
        "sea_operational_briefing": sea_briefing,
        "key_takeaways": [
            f"Nowcast 0-3h: {now['weather_description']}, rain-rate {land['hydrogeological']['precip_1h_mm']} mm/h, spread vento 5 modelli Δ={now['model_spread']['wind_spread_knots']} kt.",
            f"Terra ({loc['name']}): {land['hydrogeological']['label']} | Vento {now['wind_kmh']:.1f} km/h (raffica {now['gust_kmh']:.1f} km/h).",
            f"Mare (Fisica Pura): {sea['wind']['speed_knots']:.1f} kt (raffica {sea['wind']['gust_knots']:.1f} kt) da {sea['wind']['cardinal']}, Hs {sea['waves']['significant_height_m']:.2f}m (Hmax {sea['waves']['max_height_m']:.2f}m) @ {sea['waves']['peak_period_s']:.1f}s, risacca {bay_surge['shore_breaker_height_m']:.2f}m.",
        ],
    }


async def generate_ai_bulletin(
    weather_pkg: dict[str, Any], mode: str = "both"
) -> dict[str, Any]:
    """Genera l'analisi sinottica tramite Google Gemini (`google-genai`) con fallback deterministico immediato."""
    settings = get_settings()
    baseline = build_deterministic_synoptic_bulletin(weather_pkg, mode=mode)

    if not settings.gemini_api_key:
        return baseline

    try:
        from google import genai

        district = weather_pkg["district"]
        loc = weather_pkg.get("location") or district
        now = weather_pkg["nowcast"]["current"]
        conv = weather_pkg["nowcast"]["ligurian_convergence"]
        land = weather_pkg["land"]["risk_assessment"]
        sea = weather_pkg["sea"]["marine_conditions"]
        bay_surge = sea["coastal_physics"]["bay_surge"]

        prompt = (
            "Sei l'Analista Sinottico Meteo-Marino Senior per la Provincia di Genova (MedioMeteo Genova).\n"
            "REGOLA TASSATIVA: Opera come analista fisico puro. Spiega i meccanismi barici, orografici e oceanografici "
            "senza mai dare consigli paternalistici 'esci / non uscire in barca'.\n\n"
            f"LOCALITÀ: {loc['name']} ({district['arpal_zone']})\n"
            f"STATO ATTUALE & NOWCAST 0-3H: {now['weather_description']}, Temp {now['temp_c']}°C, "
            f"Pressione {now['pressure_hpa']} hPa ({now['pressure_trend_label']}), "
            f"Pioggia 1h: {land['hydrogeological']['precip_1h_mm']} mm, Cumulata 24h: {land['hydrogeological']['precip_24h_mm']} mm.\n"
            f"VENTO: {now['wind_ligurian_name']} ({now['wind_cardinal']}) {sea['wind']['speed_knots']} kt ({now['wind_kmh']} km/h), "
            f"Raffiche {sea['wind']['gust_knots']} kt ({now['gust_kmh']} km/h), Forza {sea['wind']['beaufort']['force']} Beaufort.\n"
            f"CONVERGENZA LIGURE: {conv['status']} ({conv['explanation']}).\n"
            f"FISICA DEL MARE: {sea['waves']['douglas']['label']}, Hs {sea['waves']['significant_height_m']} m, "
            f"Hmax {sea['waves']['max_height_m']} m, Periodo Tp {sea['waves']['peak_period_s']} s da {sea['waves']['direction_cardinal']}, "
            f"Lunghezza d'onda {sea['waves']['wavelength_m']} m, Risacca in cala {bay_surge['shore_breaker_height_m']} m.\n\n"
            "Rispondi con 3 paragrafi tecnici concisi (max 160 parole): "
            "1) Dinamica Sinottica & Confronto Modelli (AROME/ICON-D2/ECMWF); "
            "2) Fisica al Suolo, Bacini e Valichi; "
            "3) Cinematica Marina, Spettro d'Onda e Risacca Costiera."
        )

        def _call_gemini() -> str:
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return resp.text or ""

        ai_text = await asyncio.to_thread(_call_gemini)
        if ai_text.strip():
            baseline["ai_powered"] = True
            baseline["engine"] = f"google_genai ({settings.gemini_model})"
            baseline["synoptic_nowcast_analysis"] = ai_text.strip()
        return baseline
    except Exception as exc:
        logger.warning("Fallback deterministico AI Advisor per errore Gemini: %s", exc)
        return baseline


def _build_deterministic_qa_answer(weather_pkg: dict[str, Any], question: str) -> str:
    """Risposta fisica deterministica basata esclusivamente sui dati reali del punto (fallback / ask)."""
    loc = weather_pkg.get("location") or weather_pkg["district"]
    now = weather_pkg["nowcast"]["current"]
    conv = weather_pkg["nowcast"]["ligurian_convergence"]
    land = weather_pkg["land"]["risk_assessment"]
    sea = weather_pkg["sea"]["marine_conditions"]
    hourly = weather_pkg["forecast"].get("hourly_48h") or []
    obs = weather_pkg.get("observations_live") or {}

    next_12h = hourly[:12] if hourly else [now]
    max_rain_12h = max((h.get("precip_max_lam_mm") or h.get("precip_mm") or 0.0 for h in next_12h), default=0.0)
    max_gust_kt = max((h.get("gust_knots") or 0.0 for h in next_12h), default=sea["wind"]["gust_knots"])
    max_wave_m = max((h.get("wave_hs_m") or 0.0 for h in next_12h), default=sea["waves"]["significant_height_m"])

    q = question.lower()
    st_list = obs.get("nearest_weather_stations") or []
    st_note = (
        f" Stazione OMIRL {st_list[0]['name']}: {st_list[0]['temp_c']}°C, vento {st_list[0]['wind_knots']} kt."
        if st_list
        else ""
    )

    if any(k in q for k in ("mare", "onda", "onde", "barca", "uscire", "rada", "risacca", "marea", "bagno", "porto", "navig")):
        return (
            f"A {loc['name']} adesso soffia {sea['wind']['ligurian_name']} ({sea['wind']['cardinal']}) a {sea['wind']['speed_knots']} kt "
            f"con raffiche fino a {sea['wind']['gust_knots']} kt. Mare {sea['waves']['douglas']['label'].lower()} "
            f"(Hs {sea['waves']['significant_height_m']} m, Hmax {sea['waves']['max_height_m']} m, periodo {sea['waves']['peak_period_s']} s da {sea['waves']['direction_cardinal']}) "
            f"e risacca a riva stimata di {sea['coastal_physics']['bay_surge']['shore_breaker_height_m']} m; nelle prossime 12 ore picco d'onda fino a {max_wave_m} m e raffica max {max_gust_kt} kt."
        )
    if any(k in q for k in ("piov", "piogg", "temporale", "ombrev", "idro", "fiume", "bisagno", "polcevera", "allerta")):
        hy_list = obs.get("nearest_river_hydrometers") or []
        hy_txt = (
            f" Idrometro vicino {hy_list[0]['name']} ({hy_list[0]['river']}): {hy_list[0]['level_m']} m."
            if hy_list
            else ""
        )
        return (
            f"Su {loc['name']} al momento piove {land['hydrogeological']['precip_1h_mm']} mm/h ({now['weather_description']}). "
            f"Nelle prossime 12 ore il picco massimo stimato dai modelli LAM (AROME/ICON-D2) arriva a {max_rain_12h:.1f} mm/h, "
            f"con indice di convergenza ligure a {conv['convergence_score']}/100.{hy_txt}"
        )
    if any(k in q for k in ("vent", "raffic", "tramontana", "scirocco", "libeccio")):
        return (
            f"A {loc['name']} il vento è {sea['wind']['ligurian_name']} ({sea['wind']['cardinal']} {sea['wind']['direction_deg']}°) "
            f"a {now['wind_kmh']} km/h ({sea['wind']['speed_knots']} kt), raffiche {now['gust_kmh']} km/h ({sea['wind']['gust_knots']} kt). "
            f"Nelle prossime 12 ore le raffiche possono toccare {max_gust_kt} kt.{st_note}"
        )

    return (
        f"A {loc['name']}: {now['weather_description']}, {now['temp_c']}°C, pressione {now['pressure_hpa']} hPa ({now['pressure_trend_label']}). "
        f"Vento {sea['wind']['ligurian_name']} {sea['wind']['speed_knots']} kt (raffiche {sea['wind']['gust_knots']} kt), "
        f"picco pioggia LAM 12h fino a {max_rain_12h:.1f} mm/h e onda Hs {sea['waves']['significant_height_m']} m.{st_note}"
    )


async def answer_point_question(weather_pkg: dict[str, Any], question: str) -> dict[str, Any]:
    """Risponde in 2-4 frasi concrete a una domanda contestuale su un punto specifico (ADR-0013)."""
    settings = get_settings()
    fallback_answer = _build_deterministic_qa_answer(weather_pkg, question)
    loc = weather_pkg.get("location") or weather_pkg["district"]

    if not settings.gemini_api_key:
        return {
            "location_name": loc["name"],
            "question": question,
            "answer": fallback_answer,
            "ai_powered": False,
            "engine": "ligurian_synoptic_qa_v4",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        from google import genai  # type: ignore

        now = weather_pkg["nowcast"]["current"]
        conv = weather_pkg["nowcast"]["ligurian_convergence"]
        land = weather_pkg["land"]["risk_assessment"]
        sea = weather_pkg["sea"]["marine_conditions"]
        hourly = weather_pkg["forecast"].get("hourly_48h") or []
        next_6h = [
            f"{h['time'][-5:]}: {h['temp_c']}°C, {h['wind_knots']}kt (r.{h['gust_knots']}), pioggia {h['precip_mm']}mm (LAM max {h.get('precip_max_lam_mm', h['precip_mm'])}), onda {h['wave_hs_m']}m"
            for h in hourly[:6]
        ]

        prompt = (
            "Sei un meteorologo ligure amichevole, preciso e sintetico.\n"
            "Rispondi in italiano naturale in massimo 3 frasi chiare usando SOLO i dati reali forniti sotto. "
            "In mare riporta i numeri fisici senza dare ordini paternalistici.\n\n"
            f"LOCALITÀ: {loc['name']} | MODO: {loc.get('category', 'land')}\n"
            f"ADESSO: {now['weather_description']}, {now['temp_c']}°C, pioggia 1h {land['hydrogeological']['precip_1h_mm']}mm, "
            f"vento {sea['wind']['ligurian_name']} {sea['wind']['speed_knots']}kt (raffiche {sea['wind']['gust_knots']}kt), "
            f"onda Hs {sea['waves']['significant_height_m']}m / Hmax {sea['waves']['max_height_m']}m Tp {sea['waves']['peak_period_s']}s, "
            f"risacca {sea['coastal_physics']['bay_surge']['shore_breaker_height_m']}m, "
            f"convergenza {conv['convergence_score']}/100, confidenza 5 modelli {now['confidence_pct']}%.\n"
            f"PROSSIME 6 ORE: {' | '.join(next_6h)}\n\n"
            f"DOMANDA UTENTE: {question}\n"
        )

        def _call_gemini_qa() -> str:
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return resp.text or ""

        ai_text = await asyncio.to_thread(_call_gemini_qa)
        if ai_text.strip():
            return {
                "location_name": loc["name"],
                "question": question,
                "answer": ai_text.strip(),
                "ai_powered": True,
                "engine": f"google_genai ({settings.gemini_model})",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.warning("Fallback QA deterministico per errore Gemini: %s", exc)

    return {
        "location_name": loc["name"],
        "question": question,
        "answer": fallback_answer,
        "ai_powered": False,
        "engine": "ligurian_synoptic_qa_v4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
