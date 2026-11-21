"""Motore Fisico Meteo-Marino Puro per il Golfo di Genova e l'Alto Mar Ligure (ADR-0006 / TASK-PHY-01).

REGOLA FONDAMENTALE (Allineamento /grill-me #2):
- In modalità MARE sono ABOLITI i "semafori consiglio" soggettivi ("esci / non uscire").
- Il motore restituisce esclusivamente parametri fisici, cinematici e oceanografici oggettivi al massimo dettaglio:
  1. Vento: velocità media e raffica in Nodi (kt), km/h e m/s, direzione in gradi e quadrante, nome tradizionale ligure, grado Beaufort (0-12).
  2. Spettro Completo dell'Onda: altezza significativa (Hs), onda massima statistica (Hmax = 1.65*Hs), onda da vento locale (Hwind) separata dallo Swell primario (Hswell), periodo medio e di picco (Tp in s), lunghezza d'onda (L in m), ripidità adimensionale e percentuale (H/L %), grado Douglas (0-9).
  3. Fisica Costiera, Maree & Correnti:
     - Curva di Marea ed estremi giornalieri (`HIGH` / `LOW` in cm sopra il chart datum locale e fase `Crescente` / `Calante` da `sea_level_height_msl`, ORO-5).
     - Calcolo Fisico di Risacca e Rifrazione nelle Rade/Cale (`compute_bay_surge_physics`, ORO-4): calcola l'angolo di incidenza dello swell rispetto all'apertura della cala (`bay_open_deg`), il coefficiente di amplificazione da periodo lungo (`Tp >= 7s`) e marea, e l'altezza d'onda frangente equivalente a riva (`breaker_height_m`).
     - Corrente superficiale marina (velocità in nodi e direzione + componente di promontorio `headland_current_knots`).
  4. Visibilità ottica espressa in Miglia Nautiche (NM) e metri.
"""

from __future__ import annotations

import math
from typing import Any
from backend.engine.ligurian_diagnostics import angular_difference_deg, ligurian_wind_name


def kmh_to_knots(speed_kmh: float) -> float:
    """Converte km/h in nodi nautici (kt)."""
    return round(float(speed_kmh) / 1.852, 1)


def kmh_to_ms(speed_kmh: float) -> float:
    """Converte km/h in metri al secondo (m/s)."""
    return round(float(speed_kmh) / 3.6, 1)


def meters_to_nautical_miles(meters: float) -> float:
    """Converte metri in Miglia Nautiche (NM, 1 NM = 1852 m)."""
    return round(max(0.0, float(meters)) / 1852.0, 1)


def knots_to_beaufort(knots: float) -> dict[str, Any]:
    """Restituisce il grado della Scala Internazionale Beaufort (0-12) e la descrizione marina."""
    thresholds = [
        (1.0, 0, "Calma", "Mare a specchio"),
        (3.5, 1, "Bava di vento", "Increspature minute senza schiuma"),
        (6.5, 2, "Brezza leggera", "Onde piccole corte che non rompono"),
        (10.5, 3, "Brezza tesa", "Creste che iniziano a rompere, prime pecorelle"),
        (16.5, 4, "Vento moderato", "Onde piccole più allungate, numerose pecorelle"),
        (21.5, 5, "Vento teso", "Onde moderate allungate, spruzzi"),
        (27.5, 6, "Vento fresco", "Si formano onde grandi, creste di schiuma bianca estese"),
        (33.5, 7, "Vento forte", "Il mare ingrossa, schiuma striata nella direzione del vento"),
        (40.5, 8, "Burrasca moderata", "Onde alte con creste che frangono in vortici di spruzzi"),
        (47.5, 9, "Burrasca forte", "Onde grosse, densa schiuma lungo il vento"),
        (55.5, 10, "Tempesta", "Onde molto grosse con lunghe creste a pennacchio"),
        (63.5, 11, "Tempesta violenta", "Onde eccezionalmente alte, mare coperto di schiuma"),
    ]
    for limit, degree, label, sea_desc in thresholds:
        if knots < limit:
            return {"force": degree, "label": label, "sea_effect": sea_desc}
    return {"force": 12, "label": "Uragano", "sea_effect": "Mare interamente bianco di schiuma e spruzzi"}


def hs_to_douglas(hs_m: float) -> dict[str, Any]:
    """Converte l'altezza d'onda significativa Hs (metri) nel grado ufficiale della Scala Douglas (0-9)."""
    if hs_m < 0.05:
        return {"degree": 0, "label": "Calmo (Grado 0)", "range_m": "0 m"}
    if hs_m < 0.10:
        return {"degree": 1, "label": "Quasi calmo (Grado 1)", "range_m": "0 - 0.10 m"}
    if hs_m < 0.50:
        return {"degree": 2, "label": "Poco mosso (Grado 2)", "range_m": "0.10 - 0.50 m"}
    if hs_m < 1.25:
        return {"degree": 3, "label": "Mosso (Grado 3)", "range_m": "0.50 - 1.25 m"}
    if hs_m < 2.50:
        return {"degree": 4, "label": "Molto mosso (Grado 4)", "range_m": "1.25 - 2.50 m"}
    if hs_m < 4.00:
        return {"degree": 5, "label": "Agitato (Grado 5)", "range_m": "2.50 - 4.00 m"}
    if hs_m < 6.00:
        return {"degree": 6, "label": "Molto agitato (Grado 6)", "range_m": "4.00 - 6.00 m"}
    if hs_m < 9.00:
        return {"degree": 7, "label": "Grosso (Grado 7)", "range_m": "6.00 - 9.00 m"}
    if hs_m < 14.0:
        return {"degree": 8, "label": "Molto grosso (Grado 8)", "range_m": "9.00 - 14.0 m"}
    return {"degree": 9, "label": "Tempestoso (Grado 9)", "range_m": ">14.0 m"}


def extract_tides_from_sea_level(
    times: list[str], sea_levels_m: list[float | None], current_idx: int = 0
) -> dict[str, Any]:
    """Estrae gli estremi di marea (HIGH / LOW) e la fase attuale dalla curva `sea_level_height_msl` (ORO-5)."""
    valid_vals = [float(v) for v in sea_levels_m if v is not None]
    if not valid_vals or len(times) < 3:
        return {
            "is_synthetic": True,
            "current_height_cm": 18,
            "current_phase": "Stazionaria",
            "range_cm": 28,
            "extrema": [
                {"time": "06:30", "type": "HIGH", "label": "Alta Marea", "height_cm": 32},
                {"time": "12:45", "type": "LOW", "label": "Bassa Marea", "height_cm": 4},
                {"time": "19:10", "type": "HIGH", "label": "Alta Marea", "height_cm": 34},
            ],
        }

    base_datum = min(valid_vals)
    max_datum = max(valid_vals)
    extrema: list[dict[str, Any]] = []

    for i in range(1, min(len(times), len(sea_levels_m)) - 1):
        v = sea_levels_m[i]
        prev_v = sea_levels_m[i - 1]
        next_v = sea_levels_m[i + 1]
        if v is None or prev_v is None or next_v is None:
            continue
        fv, fp, fn = float(v), float(prev_v), float(next_v)
        if fv >= fp and fv > fn:
            t_type = "HIGH"
            t_label = "Alta Marea"
        elif fv <= fp and fv < fn:
            t_type = "LOW"
            t_label = "Bassa Marea"
        else:
            continue
        t_str = times[i][11:16] if len(times[i]) >= 16 else times[i]
        d_str = times[i][:10]
        extrema.append(
            {
                "date": d_str,
                "time": t_str,
                "type": t_type,
                "label": t_label,
                "height_cm": int(round((fv - base_datum) * 100)),
                "height_m": round(fv - base_datum, 2),
            }
        )

    idx = max(0, min(current_idx, len(sea_levels_m) - 1))
    cur_v = float(sea_levels_m[idx]) if sea_levels_m[idx] is not None else valid_vals[0]
    next_v = (
        float(sea_levels_m[min(idx + 1, len(sea_levels_m) - 1)])
        if sea_levels_m[min(idx + 1, len(sea_levels_m) - 1)] is not None
        else cur_v
    )
    if next_v > cur_v + 0.005:
        phase = "Crescente (Flusso ↑)"
    elif next_v < cur_v - 0.005:
        phase = "Calante (Riflusso ↓)"
    else:
        phase = "Stanca di Marea (≈ Picco)"

    return {
        "is_synthetic": False,
        "current_height_cm": int(round((cur_v - base_datum) * 100)),
        "current_phase": phase,
        "range_cm": int(round((max_datum - base_datum) * 100)),
        "extrema": extrema[:8],
    }


def compute_bay_surge_physics(
    swell_hs_m: float,
    swell_period_s: float,
    swell_dir_deg: float,
    bay_open_deg: int | None = 200,
    tide_phase: str = "Stazionaria",
) -> dict[str, Any]:
    """Calcola la fisica di rifrazione, shoaling e risacca costiera in una cala/rada (ORO-4).

    Restituisce grandezze fisiche oggettive:
    - `incidence_angle_deg`: differenza angolare tra direzione dello swell e asse di apertura della cala
    - `refraction_coeff`: coefficiente di penetrazione dell'onda nella cala (0.15 se riparata -> 1.0 se esposta frontalmente)
    - `shoaling_factor`: amplificazione per periodo lungo su basso fondale `(Tp / 5.0)^0.5`
    - `breaker_height_m`: altezza fisica stimata del frangente / risacca a riva (in metri)
    """
    open_axis = float(bay_open_deg if bay_open_deg is not None else 200)
    inc_deg = round(angular_difference_deg(swell_dir_deg, open_axis), 0)

    # Coefficiente di penetrazione/rifrazione attorno ai capi
    if inc_deg <= 35:
        kr = 1.00
        exposure_type = "Impatto Frontale Diretto in Rada"
    elif inc_deg <= 70:
        kr = round(0.75 - ((inc_deg - 35) / 35.0) * 0.25, 2)
        exposure_type = "Penetrazione Obliqua / Rifrazione Laterale"
    elif inc_deg <= 115:
        kr = 0.38
        exposure_type = "Diffrazione Attorno al Capo (Ridosso Parziale)"
    else:
        kr = 0.18
        exposure_type = "Rada Ridossata (Swell Sottovento)"

    # Coefficiente di shoaling legato al periodo d'onda (onde con Tp > 7-8s portano molta più energia a riva)
    ks = round(max(0.85, min(1.55, math.sqrt(max(3.0, swell_period_s) / 5.0))), 2)
    tide_mult = 1.12 if ("Crescente" in tide_phase or "Stanca" in tide_phase) else 1.00

    breaker_m = round(swell_hs_m * kr * ks * tide_mult, 2)

    return {
        "bay_open_axis_deg": int(open_axis),
        "swell_incidence_diff_deg": int(inc_deg),
        "exposure_geometry": exposure_type,
        "refraction_kr": kr,
        "shoaling_ks": ks,
        "tide_amplification_factor": tide_mult,
        "shore_breaker_height_m": breaker_m,
    }


def compute_wave_dynamics(
    hs_m: float,
    period_s: float,
    wave_dir_deg: float,
    wind_wave_m: float = 0.0,
    wind_wave_period_s: float = 0.0,
    wind_wave_dir_deg: float = 0.0,
    swell_wave_m: float = 0.0,
    swell_period_s: float = 0.0,
    swell_dir_deg: float = 0.0,
    wind_speed_kmh: float = 0.0,
    wind_gust_kmh: float = 0.0,
    wind_dir_deg: float = 0.0,
    sst_c: float = 17.5,
    current_velocity_kmh: float = 0.4,
    current_dir_deg: float = 285.0,
    visibility_m: float = 10000.0,
    bay_open_deg: int | None = 200,
    tide_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calcola l'intero cruscotto fisico marino (Zero Semafori Soggettivi — ADR-0006)."""
    hs = max(0.05, float(hs_m))
    tp = max(2.5, float(period_s))

    wind_kt = kmh_to_knots(wind_speed_kmh)
    gust_kt = kmh_to_knots(wind_gust_kmh)
    wind_ms = kmh_to_ms(wind_speed_kmh)
    gust_ms = kmh_to_ms(wind_gust_kmh)

    # Correzione fisica per fetch costiero breve in caso di vento forte catabatico sottocosta
    if wind_kt >= 18.0 and hs < 0.7:
        coastal_wind_hs = round(min(2.4, 0.038 * wind_kt), 2)
        hs = max(hs, coastal_wind_hs)
        wind_wave_m = max(wind_wave_m, hs * 0.85)
        tp = min(tp, 4.2)

    # Altezza d'onda massima statistica (Rayleigh distribution: Hmax ≈ 1.65 * Hs, picco estremo 1/1000 ≈ 1.86 * Hs)
    hmax_m = round(hs * 1.65, 2)
    hextreme_m = round(hs * 1.86, 2)

    # Lunghezza d'onda in acqua profonda: L = (g / 2π) * T^2 ≈ 1.56 * T^2
    wavelength_m = round(1.56 * (tp ** 2), 1)
    steepness = hs / max(1.0, wavelength_m)
    steepness_pct = round(steepness * 100.0, 2)

    # Criteri fisici di ripidità d'onda (Stokes wave breaking limit H/L ≈ 1/7 = 14.2%; onda ripida già oltre 3.5-4.2%)
    if hs >= 0.6 and (tp <= 4.5 or steepness >= 0.038):
        steepness_class = f"Onda Corta Ripida (H/L = {steepness_pct:.1f}%, Tp = {tp:.1f}s)"
        steepness_warning = True
    elif hs >= 1.2 and tp >= 7.5:
        steepness_class = f"Onda Lunga di Swell (H/L = {steepness_pct:.1f}%, L = {wavelength_m:.0f}m)"
        steepness_warning = False
    else:
        steepness_class = f"Pendenza Ordinaria (H/L = {steepness_pct:.1f}%, L = {wavelength_m:.0f}m)"
        steepness_warning = False

    beaufort = knots_to_beaufort(wind_kt)
    douglas = hs_to_douglas(hs)
    wind_info = ligurian_wind_name(wind_dir_deg, wind_speed_kmh)
    wave_compass = ligurian_wind_name(wave_dir_deg, 20.0)["cardinal"]
    swell_compass = ligurian_wind_name(swell_dir_deg or wave_dir_deg, 20.0)["cardinal"]
    wind_wave_compass = ligurian_wind_name(wind_wave_dir_deg or wind_dir_deg, 20.0)["cardinal"]

    # Corrente superficiale (da modello marino + componente indotta dal vento sul promontorio `calcPC` ORO-4)
    base_curr_kt = kmh_to_knots(current_velocity_kmh)
    is_westerly_sector = 200 <= (wind_dir_deg % 360) <= 315
    wind_drift_kt = round(wind_kt * 0.028 * (1.2 if is_westerly_sector else 0.6), 2)
    total_current_kt = round(max(0.15, base_curr_kt + wind_drift_kt), 2)
    current_compass = ligurian_wind_name(current_dir_deg, 15.0)["cardinal"]

    # Fisica di risacca nella cala/rada
    eff_swell_h = max(swell_wave_m, hs * 0.75)
    eff_swell_p = max(swell_period_s, tp)
    eff_swell_d = swell_dir_deg if swell_dir_deg else wave_dir_deg
    t_phase = (tide_info or {}).get("current_phase", "Stazionaria")
    bay_surge = compute_bay_surge_physics(
        swell_hs_m=eff_swell_h,
        swell_period_s=eff_swell_p,
        swell_dir_deg=eff_swell_d,
        bay_open_deg=bay_open_deg,
        tide_phase=t_phase,
    )

    return {
        "wind": {
            "speed_knots": wind_kt,
            "gust_knots": gust_kt,
            "speed_kmh": round(wind_speed_kmh, 1),
            "gust_kmh": round(wind_gust_kmh, 1),
            "speed_ms": wind_ms,
            "gust_ms": gust_ms,
            "direction_deg": round(wind_dir_deg, 0),
            "cardinal": wind_info["cardinal"],
            "ligurian_name": wind_info["name"],
            "local_note": wind_info["local_note"],
            "beaufort": beaufort,
        },
        "waves": {
            "significant_height_m": round(hs, 2),
            "max_height_m": hmax_m,
            "extreme_height_1_1000_m": hextreme_m,
            "wind_wave_height_m": round(max(0.0, wind_wave_m), 2),
            "wind_wave_period_s": round(max(2.0, wind_wave_period_s or (tp * 0.85)), 1),
            "wind_wave_dir_deg": round(wind_wave_dir_deg or wind_dir_deg, 0),
            "wind_wave_cardinal": wind_wave_compass,
            "swell_height_m": round(max(0.0, swell_wave_m), 2),
            "swell_period_s": round(max(tp, swell_period_s), 1),
            "swell_dir_deg": round(eff_swell_d, 0),
            "swell_cardinal": swell_compass,
            "peak_period_s": round(tp, 1),
            "wavelength_m": wavelength_m,
            "direction_deg": round(wave_dir_deg, 0),
            "direction_cardinal": wave_compass,
            "douglas": douglas,
            "steepness_ratio": round(steepness, 4),
            "steepness_pct": steepness_pct,
            "steepness_class": steepness_class,
            "steepness_warning": steepness_warning,
            "sea_surface_temp_c": round(sst_c, 1),
        },
        "coastal_physics": {
            "bay_surge": bay_surge,
            "surface_current": {
                "speed_knots": total_current_kt,
                "speed_ms": round(total_current_kt * 0.5144, 2),
                "direction_deg": round(current_dir_deg, 0),
                "direction_cardinal": current_compass,
                "wind_drift_component_knots": wind_drift_kt,
            },
            "tides": tide_info
            or {
                "current_height_cm": 18,
                "current_phase": "Stazionaria",
                "range_cm": 28,
                "extrema": [],
            },
            "visibility_nm": meters_to_nautical_miles(visibility_m),
            "visibility_m": int(round(visibility_m, 0)),
        },
    }
