"""Generatore di Allerte Sintetiche ARPAL Liguria (Zone B, C, D, E) e Avvisi di Burrasca METEOMAR (ADR-0003)."""

from __future__ import annotations

from typing import Any


def build_alerts_summary(weather_pkg: dict[str, Any]) -> dict[str, Any]:
    """Elabora il quadro integrato delle allerte Terra (stile ARPAL) e Mare (stile Meteomar Mar Ligure)."""
    district = weather_pkg["district"]
    nowcast = weather_pkg["nowcast"]
    current = nowcast["current"]
    convergence = nowcast["ligurian_convergence"]
    land_risk = weather_pkg["land"]["risk_assessment"]
    sea_cond = weather_pkg["sea"]["marine_conditions"]

    active_warnings: list[dict[str, str]] = []

    # 1. Valutazione avvisi TERRA
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
                "domain": "TERRA & MARE",
                "severity": "ORANGE" if convergence["convergence_score"] < 75 else "RED",
                "title": "Convergenza Ligure Attiva (Tramontana Scura vs Scirocco)",
                "description": convergence["explanation"],
            }
        )
    if wind_v["level"] in ("yellow", "red"):
        active_warnings.append(
            {
                "domain": "TERRA",
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

    # 2. Valutazione avvisi MARE (Stile METEOMAR Settore Mar Ligure)
    wind_kt = sea_cond["wind"]["speed_knots"]
    gust_kt = sea_cond["wind"]["gust_knots"]
    beaufort_force = sea_cond["wind"]["beaufort"]["force"]
    hs_m = sea_cond["waves"]["significant_height_m"]
    hmax_m = sea_cond["waves"]["max_height_m"]
    tp_s = sea_cond["waves"]["peak_period_s"]
    douglas_label = sea_cond["waves"]["douglas"]["label"]

    if beaufort_force >= 7 or gust_kt >= 34 or hs_m >= 2.5:
        meteomar_status = "AVVISO DI BURRASCA SUL MAR LIGURE"
        meteomar_level = "red"
    elif beaufort_force >= 5 or gust_kt >= 22 or hs_m >= 1.25 or sea_cond["waves"]["steepness_warning"]:
        meteomar_status = "AVVISO DI VENTO FORTE / MARE MOLTO MOSSO SOTTOCOSTA"
        meteomar_level = "yellow"
    else:
        meteomar_status = "ASSENZA DI AVVISI DI BURRASCA IN CORSO"
        meteomar_level = "green"

    meteomar_bulletin_text = (
        f"SETTORE MAR LIGURE ({district['short_name']}): "
        f"Vento da {sea_cond['wind']['cardinal']} ({sea_cond['wind']['ligurian_name']}) "
        f"{wind_kt:.0f} kt (Forza {beaufort_force} Beaufort) con raffiche fino a {gust_kt:.0f} kt. "
        f"Mare {douglas_label} con onda significativa Hs {hs_m:.2f} m (onda massima stimata Hmax {hmax_m:.2f} m), "
        f"periodo di picco {tp_s:.1f} s da {sea_cond['waves']['direction_cardinal']}. "
        f"Pressione al livello del mare {current['pressure_hpa']:.1f} hPa ({current['pressure_trend_label']}). "
        f"Temperatura superficiale acqua {sea_cond['waves']['sea_surface_temp_c']:.1f}°C."
    )

    if meteomar_level in ("yellow", "red"):
        active_warnings.append(
            {
                "domain": "MARE / NAUTICA",
                "severity": meteomar_level.upper(),
                "title": meteomar_status,
                "description": meteomar_bulletin_text,
            }
        )

    return {
        "arpal_zone": district["arpal_zone"],
        "land_overall_level": land_risk["overall_level"],
        "sea_overall_level": sea_cond["overall_level"],
        "meteomar": {
            "status": meteomar_status,
            "level": meteomar_level,
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
