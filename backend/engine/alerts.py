"""Generatore di Allerte Sintetiche ARPAL Liguria (Zone B, C, D, E) e Bollettino Fisico METEOMAR (ADR-0003, ADR-0006)."""

from __future__ import annotations

from typing import Any


def build_alerts_summary(weather_pkg: dict[str, Any]) -> dict[str, Any]:
    """Elabora il quadro integrato delle allerte Terra (stile ARPAL) e il Bollettino Fisico Mare (stile Meteomar Mar Ligure).

    In conformità a ADR-0006 (Allineamento /grill-me #2), la sezione Mare riporta solo grandezze
    fisiche oggettive (Vento in kt, Beaufort, Spettro d'onda Hs/Hmax/Tp, Douglas, Risacca e Corrente)
    senza "semafori consiglio" soggettivi.
    """
    district = weather_pkg["district"]
    nowcast = weather_pkg["nowcast"]
    current = nowcast["current"]
    convergence = nowcast["ligurian_convergence"]
    land_risk = weather_pkg["land"]["risk_assessment"]
    sea_cond = weather_pkg["sea"]["marine_conditions"]
    arpal_official = (weather_pkg.get("official_bulletins") or {}).get("arpal") or {}

    active_warnings: list[dict[str, str]] = []

    # 1. Valutazione avvisi operativi TERRA
    hydro = land_risk["hydrogeological"]
    wind_v = land_risk["wind_viability"]
    passes = land_risk["appennino_passes"]

    if hydro["level"] in ("orange", "red"):
        active_warnings.append(
            {
                "domain": "TERRA",
                "severity": hydro["level"].upper(),
                "title": f"Criticità Idrogeologica / Pluviometrica ({district['arpal_zone']})",
                "description": hydro["advice"],
            }
        )
    if convergence["active"]:
        active_warnings.append(
            {
                "domain": "SINOTTICA LIGURE",
                "severity": "ORANGE" if convergence["convergence_score"] < 75 else "RED",
                "title": "Convergenza Ligure Attiva (Tramontana Scura vs Scirocco)",
                "description": convergence["explanation"],
            }
        )
    if wind_v["level"] in ("yellow", "red"):
        active_warnings.append(
            {
                "domain": "TERRA / VIABILITÀ",
                "severity": wind_v["level"].upper(),
                "title": wind_v["label"],
                "description": wind_v["advice"],
            }
        )
    if passes["level"] in ("yellow", "orange", "red"):
        active_warnings.append(
            {
                "domain": "ENTROTERRA / VALICHI",
                "severity": passes["level"].upper(),
                "title": passes["label"],
                "description": passes["advice"],
            }
        )

    # 2. Bollettino Fisico MARE (Stile METEOMAR Settore Mar Ligure — Zero semafori soggettivi)
    wind_kt = sea_cond["wind"]["speed_knots"]
    gust_kt = sea_cond["wind"]["gust_knots"]
    wind_ms = sea_cond["wind"]["speed_ms"]
    beaufort_force = sea_cond["wind"]["beaufort"]["force"]
    beaufort_label = sea_cond["wind"]["beaufort"]["label"]
    hs_m = sea_cond["waves"]["significant_height_m"]
    hmax_m = sea_cond["waves"]["max_height_m"]
    tp_s = sea_cond["waves"]["peak_period_s"]
    wavelength_m = sea_cond["waves"]["wavelength_m"]
    douglas_label = sea_cond["waves"]["douglas"]["label"]
    douglas_deg = sea_cond["waves"]["douglas"]["degree"]
    breaker_m = sea_cond["coastal_physics"]["bay_surge"]["shore_breaker_height_m"]
    curr_kt = sea_cond["coastal_physics"]["surface_current"]["speed_knots"]
    vis_nm = sea_cond["coastal_physics"]["visibility_nm"]

    if beaufort_force >= 8 or gust_kt >= 34 or hs_m >= 2.5:
        meteomar_status = f"AVVISO DI BURRASCA SUL MAR LIGURE (Forza {beaufort_force} Beaufort / Douglas {douglas_deg})"
    elif beaufort_force >= 6 or gust_kt >= 25 or hs_m >= 1.25:
        meteomar_status = f"VENTO FRESCO-FORTE / MARE {douglas_label.upper()} (Forza {beaufort_force} Beaufort)"
    else:
        meteomar_status = f"STATO FISICO ORDINARIO — {beaufort_label.upper()} / MARE {douglas_label.upper()}"

    meteomar_bulletin_text = (
        f"SETTORE MAR LIGURE ({district['short_name']}): "
        f"Vento da {sea_cond['wind']['cardinal']} ({sea_cond['wind']['direction_deg']:.0f}° — {sea_cond['wind']['ligurian_name']}) "
        f"{wind_kt:.1f} kt ({wind_ms:.1f} m/s, Forza {beaufort_force} Beaufort) con raffiche fino a {gust_kt:.1f} kt. "
        f"Mare {douglas_label} con onda significativa Hs {hs_m:.2f} m (onda massima statistica Hmax {hmax_m:.2f} m), "
        f"periodo di picco Tp {tp_s:.1f} s (L = {wavelength_m:.0f} m) da {sea_cond['waves']['direction_cardinal']}. "
        f"Risacca stimata in cala {breaker_m:.2f} m, corrente superficiale {curr_kt:.2f} kt, visibilità {vis_nm:.1f} NM. "
        f"Pressione al livello del mare {current['pressure_hpa']:.1f} hPa ({current['pressure_trend_label']}). "
        f"Temperatura superficiale acqua {sea_cond['waves']['sea_surface_temp_c']:.1f}°C."
    )

    if beaufort_force >= 7 or gust_kt >= 34 or hs_m >= 2.5:
        active_warnings.append(
            {
                "domain": "METEOMAR MAR LIGURE",
                "severity": "RED",
                "title": meteomar_status,
                "description": meteomar_bulletin_text,
            }
        )

    return {
        "arpal_zone": district["arpal_zone"],
        "land_overall_level": land_risk["overall_level"],
        "arpal_official_bulletin": arpal_official,
        "meteomar": {
            "status": meteomar_status,
            "beaufort_force": beaufort_force,
            "douglas_degree": douglas_deg,
            "bulletin": meteomar_bulletin_text,
            "emergency_contacts": {
                "guardia_costiera": "1530 (Numero Blu Emergenza in Mare)",
                "vhf_channel": "Canale 16 VHF (156.8 MHz)",
                "capitaneria_genova": "+39 010 27771",
            },
        },
        "active_warnings_count": len(active_warnings),
        "active_warnings": active_warnings,
    }
