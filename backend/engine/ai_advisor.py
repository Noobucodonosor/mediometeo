"""AI Meteo & Marine Advisor alimentato da Google Gemini (`google-genai`) con Fallback Sinottico Esperto (ADR-0004)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings


def build_deterministic_synoptic_bulletin(
    weather_pkg: dict[str, Any], mode: str = "both"
) -> dict[str, Any]:
    """Genera un bollettino tecnico-sinottico completo basato sulle regole fisiche liguri (Fallback 100% affidabile)."""
    district = weather_pkg["district"]
    now = weather_pkg["nowcast"]["current"]
    conv = weather_pkg["nowcast"]["ligurian_convergence"]
    land = weather_pkg["land"]["risk_assessment"]
    sea = weather_pkg["sea"]["marine_conditions"]
    hourly = weather_pkg["forecast"]["hourly_48h"]

    # Analisi evoluzione prossime 6-12 ore
    next_6h = hourly[:6] if hourly else [now]
    max_rain_6h = max((h["precip_mm"] for h in next_6h), default=0.0)
    max_gust_6h_kmh = max((h["gust_kmh"] for h in next_6h), default=now["gust_kmh"])
    max_gust_6h_kt = max((h["gust_knots"] for h in next_6h), default=sea["wind"]["gust_knots"])
    max_wave_6h_m = max((h["wave_hs_m"] for h in next_6h), default=sea["waves"]["significant_height_m"])

    synoptic_headline = (
        f"Quadro Sinottico su {district['name']}: {now['weather_description']} "
        f"({now['temp_c']:.1f}°C), ventilazione da {now['wind_cardinal']} ({now['wind_ligurian_name']}) "
        f"e affidabilità ensemble {now['confidence_pct']}%."
    )

    if conv["active"]:
        synoptic_analysis = (
            f"ATTENZIONE CONVERGENZA LIGURE (Indice {conv['convergence_score']}/100): "
            f"{conv['explanation']} I modelli LAM ad altissima risoluzione (AROME 1.3km e ICON-D2 2km) "
            f"indicano un picco precipitativo nelle prossime 6 ore fino a {max_rain_6h:.1f} mm/h "
            f"con raffiche fino a {max_gust_6h_kmh:.0f} km/h ({max_gust_6h_kt:.0f} kt)."
        )
    else:
        synoptic_analysis = (
            f"Flusso atmosferico governato da correnti di {now['wind_ligurian_name']} ({now['wind_cardinal']}). "
            f"{sea['wind']['local_note']} Pressione atmosferica a {now['pressure_hpa']:.1f} hPa "
            f"({now['pressure_trend_label'].lower()}). Nelle prossime 6 ore precipitazioni massime attese "
            f"intorno a {max_rain_6h:.1f} mm/h e raffiche massime fino a {max_gust_6h_kmh:.0f} km/h."
        )

    land_briefing = (
        f"• **Stato Bacini & Viabilità ({district['short_name']}):** {land['hydrogeological']['label']}. "
        f"{land['hydrogeological']['advice']}\n"
        f"• **Vento & Infrastrutture Stradali:** {land['wind_viability']['label']} "
        f"(Vento medio {now['wind_kmh']:.0f} km/h, raffiche {now['gust_kmh']:.0f} km/h). "
        f"{land['wind_viability']['advice']}\n"
        f"• **Valichi Appenninici (Giovi / Turchino / A7 / A26 / Aveto):** {land['appennino_passes']['label']}."
    )

    sea_briefing = (
        f"• **Vento & Mare ({district['short_name']}):** {sea['wind']['ligurian_name']} ({sea['wind']['cardinal']}) "
        f"a {sea['wind']['speed_knots']:.0f} kt (raffiche {sea['wind']['gust_knots']:.0f} kt, "
        f"Forza {sea['wind']['beaufort']['force']} Beaufort — {sea['wind']['beaufort']['label']}).\n"
        f"• **Moto Ondoso & Periodo:** Mare {sea['waves']['douglas']['label']} con Hs {sea['waves']['significant_height_m']:.2f} m "
        f"(onda massima Hmax {sea['waves']['max_height_m']:.2f} m, trend 6h fino a {max_wave_6h_m:.2f} m) "
        f"e periodo di picco Tp {sea['waves']['peak_period_s']:.1f} s da {sea['waves']['direction_cardinal']} "
        f"({sea['waves']['steepness_class']}).\n"
        f"• **Consiglio Comandanti & Diporto:** Vela/Diporto: *{sea['activities_safety']['sailing_yachting']['label']}* — "
        f"{sea['activities_safety']['sailing_yachting']['note']} "
        f"Kayak/Costiero: *{sea['activities_safety']['kayak_sup_swimming']['label']}*."
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "deterministic_ligurian_synoptic_engine",
        "ai_powered": False,
        "mode": mode,
        "district_id": district["id"],
        "headline": synoptic_headline,
        "synoptic_nowcast_analysis": synoptic_analysis,
        "land_operational_briefing": land_briefing,
        "sea_operational_briefing": sea_briefing,
        "key_takeaways": [
            f"Nowcast 0-3h: {now['weather_description']}, pioggia {land['hydrogeological']['precip_1h_mm']} mm/h, confidenza modelli {now['confidence_pct']}%.",
            f"Terra ({district['short_name']}): {land['hydrogeological']['label']} | Vento {now['wind_kmh']:.0f} km/h (raffica {now['gust_kmh']:.0f} km/h).",
            f"Mare (Golfo Ligure): {sea['wind']['speed_knots']:.0f} kt (raffica {sea['wind']['gust_knots']:.0f} kt) da {sea['wind']['cardinal']}, Onda Hs {sea['waves']['significant_height_m']:.2f}m @ {sea['waves']['peak_period_s']:.1f}s ({sea['waves']['douglas']['label']}).",
        ],
    }


async def generate_ai_bulletin(
    weather_pkg: dict[str, Any], mode: str = "both"
) -> dict[str, Any]:
    """Genera il bollettino intelligente tramite Google Gemini (`google-genai`) con fallback deterministico immediato."""
    settings = get_settings()
    baseline = build_deterministic_synoptic_bulletin(weather_pkg, mode=mode)

    if not settings.gemini_api_key:
        return baseline

    try:
        from google import genai

        district = weather_pkg["district"]
        now = weather_pkg["nowcast"]["current"]
        conv = weather_pkg["nowcast"]["ligurian_convergence"]
        land = weather_pkg["land"]["risk_assessment"]
        sea = weather_pkg["sea"]["marine_conditions"]

        prompt = (
            "Sei il Previsore Meteo-Marino Senior della Sala Operativa di Genova (MedioMeteo Genova).\n"
            "Redigi un bollettino tecnico ma chiarissimo in italiano per la Provincia di Genova, "
            "suddiviso per chi è a TERRA e per chi è in MARE.\n\n"
            f"DISTRETTO: {district['name']} ({district['arpal_zone']})\n"
            f"MICROCLIMA: {district['microclimate_notes']}\n"
            f"STATO ATTUALE E NOWCAST 0-3H: {now['weather_description']}, Temp {now['temp_c']}°C, "
            f"Pioggia 1h: {land['hydrogeological']['precip_1h_mm']} mm, Cumulata 24h prevista: {land['hydrogeological']['precip_24h_mm']} mm.\n"
            f"VENTO: {now['wind_ligurian_name']} ({now['wind_cardinal']}) {now['wind_kmh']} km/h ({sea['wind']['speed_knots']} kt), "
            f"Raffiche {now['gust_kmh']} km/h ({sea['wind']['gust_knots']} kt), Forza {sea['wind']['beaufort']['force']} Beaufort.\n"
            f"CONVERGENZA LIGURE (Tramontana/Scirocco): {conv['status']} ({conv['explanation']}).\n"
            f"STATO DEL MARE: {sea['waves']['douglas']['label']}, Onda significativa Hs {sea['waves']['significant_height_m']} m, "
            f"Onda max Hmax {sea['waves']['max_height_m']} m, Periodo picco Tp {sea['waves']['peak_period_s']} s da {sea['waves']['direction_cardinal']} "
            f"({sea['waves']['steepness_class']}), Temperatura acqua {sea['waves']['sea_surface_temp_c']}°C.\n\n"
            "Rispondi con 3 brevi paragrafi incisivi (max 160 parole totali): "
            "1) Analisi Sinottica & Nowcast 0-3h; 2) Avvisi Operativi Terra (Genova e Vallate); 3) Avvisi Operativi Mare (Porto, Costa e Largo)."
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
    except Exception:
        return baseline
