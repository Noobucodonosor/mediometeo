"""Diagnostica Meteo-Marina Specifica per Genova e la Liguria (ADR-0003).

Include:
- Conversione e nomenclatura venti della Rosa dei Venti Ligure (Tramontana Scura, Grecale, Scirocco, Ostro, Libeccio, Maestrale)
- Rilevatore di Convergenza Ligure (Tramontana Scura vs Scirocco)
- Indice di Rischio Idrogeologico e Viabilità per la Provincia di Genova (Terra)
"""

from __future__ import annotations

import math
from typing import Any


def vector_mean_deg(angles_deg: list[float], weights: list[float] | None = None) -> float:
    """Calcola la media vettoriale trigonometrica di angoli in gradi [0, 360)."""
    if not angles_deg:
        return 0.0
    if weights is None or len(weights) != len(angles_deg):
        weights = [1.0] * len(angles_deg)
    sin_sum = sum(w * math.sin(math.radians(a)) for a, w in zip(angles_deg, weights))
    cos_sum = sum(w * math.cos(math.radians(a)) for a, w in zip(angles_deg, weights))
    if abs(sin_sum) < 1e-9 and abs(cos_sum) < 1e-9:
        return round(float(angles_deg[0]) % 360.0, 1)
    mean_rad = math.atan2(sin_sum, cos_sum)
    return round((math.degrees(mean_rad) + 360.0) % 360.0, 1)


def angular_difference_deg(a1: float, a2: float) -> float:
    """Restituisce la differenza angolare minima [0, 180] tra due direzioni in gradi."""
    diff = abs((a1 - a2) % 360.0)
    return min(diff, 360.0 - diff)


def ligurian_wind_name(deg: float | None, speed_kmh: float = 0.0) -> dict[str, str]:
    """Restituisce il nome tradizionale ligure del vento, il quadrante bussola e il comportamento locale."""
    if deg is None or speed_kmh < 3.0:
        return {
            "cardinal": "VAR",
            "name": "Brezza / Calma",
            "local_note": "Ventilazione debole a regime di brezza locale",
        }
    d = deg % 360.0
    if d >= 337.5 or d < 22.5:
        name = "Tramontana Scura" if speed_kmh >= 30 else "Tramontana"
        return {
            "cardinal": "N",
            "name": name,
            "local_note": "Trabocco catabatico dai valichi (Giovi/Turchino); raffiche tese allo sbocco delle vallate e in porto.",
        }
    if 22.5 <= d < 67.5:
        return {
            "cardinal": "NE",
            "name": "Grecale",
            "local_note": "Vento freddo e rafficato dai rilievi verso costa; alza onda corta ripida appena fuori diga.",
        }
    if 67.5 <= d < 112.5:
        return {
            "cardinal": "E",
            "name": "Levante",
            "local_note": "Flusso orientale lungo la Riviera di Levante con convergenza sottocosta.",
        }
    if 112.5 <= d < 157.5:
        return {
            "cardinal": "SE",
            "name": "Scirocco",
            "local_note": "Flusso caldo-umido dal Tirreno: alimenta sbarramento orografico su Bisagno, Portofino ed Entella.",
        }
    if 157.5 <= d < 202.5:
        return {
            "cardinal": "S",
            "name": "Ostro / Mezzogiorno",
            "local_note": "Impatto umido frontale contro l'arco ligure; associato a piogge intense e mare molto mosso.",
        }
    if 202.5 <= d < 247.5:
        return {
            "cardinal": "SW",
            "name": "Libeccio",
            "local_note": "Vento dominante delle grandi mareggiate liguri con fetch lungo dal Golfo del Leone.",
        }
    if 247.5 <= d < 292.5:
        return {
            "cardinal": "W",
            "name": "Ponente",
            "local_note": "Flusso occidentale teso al largo con risacca residua sottocosta.",
        }
    return {
        "cardinal": "NW",
        "name": "Maestrale",
        "local_note": "Vento secco di caduta sul Ponente genovese (Arenzano-Voltri) con aria tersa.",
    }


def detect_ligurian_convergence(
    wind_dir_deg: float,
    wind_speed_kmh: float,
    gust_kmh: float,
    precip_mm_h: float,
    humidity_pct: float,
    cape_j_kg: float = 0.0,
    model_dir_spread_deg: float = 0.0,
) -> dict[str, Any]:
    """Rileva la probabilità di attivazione della Convergenza Ligure (Tramontana Scura vs Scirocco).

    Su Genova la convergenza si attiva quando flussi settentrionali di trabocco (320°-045°)
    interagiscono con masse d'aria umide meridionali (110°-195°), oppure quando i modelli LAM
    mostrano forte rotazione di shear sul Golfo con umidità elevata (>78%) e precipitazioni/CAPE.
    """
    score = 0
    reasons: list[str] = []

    is_tramontana_sector = wind_dir_deg >= 325 or wind_dir_deg <= 45
    is_scirocco_sector = 110 <= wind_dir_deg <= 195

    if (is_tramontana_sector or is_scirocco_sector) and humidity_pct >= 78:
        score += 30
        reasons.append(
            "Flusso attivo lungo l'asse critico N/SE con elevato contenuto igrometrico nei bassi strati"
        )

    if model_dir_spread_deg >= 75:
        score += 30
        reasons.append(
            f"Forte shear direzionale tra modelli ad alta risoluzione ({model_dir_spread_deg:.0f}°), indice di linea di convergenza sul Golfo di Genova"
        )

    if precip_mm_h >= 4.0:
        score += 25
        reasons.append(f"Rateo precipitativo attivo ({precip_mm_h:.1f} mm/h) su orografia costiera")
    elif precip_mm_h >= 1.0:
        score += 12

    if cape_j_kg >= 400:
        score += 15
        reasons.append(f"Energia convettiva marittima disponibile (CAPE {cape_j_kg:.0f} J/kg)")

    if gust_kmh - wind_speed_kmh >= 20:
        score += 10
        reasons.append("Elevata turbolenza di raffica nei bassi strati")

    score = min(100, score)
    if score >= 65:
        status = "ATTIVA / ALTO RISCHIO AUTORIGENERANTE"
        level = "high"
    elif score >= 35:
        status = "MODERATA / LINEA DI CONVERGENZA IN FORMAZIONE"
        level = "moderate"
    else:
        status = "ASSENTE / FLUSSO SINOTTICO REGOLARE"
        level = "low"

    return {
        "active": score >= 50,
        "convergence_score": score,
        "level": level,
        "status": status,
        "explanation": (
            " | ".join(reasons)
            if reasons
            else "Assenza di contrasto termico-dinamico critico tra Val Polcevera e Golfo Ligure."
        ),
    }


def compute_thermo_hygrometric_indices(
    temp_c: float,
    humidity_pct: float,
    wind_kmh: float,
    cloud_cover_pct: float = 40.0,
    pressure_hpa: float = 1015.0,
) -> dict[str, Any]:
    """Calcola Punto di Rugiada (Dew Point), Humidex, Windchill e diagnosi della 'Maccaja Ligure'."""
    rh = max(1.0, min(100.0, float(humidity_pct)))
    # Formula di Magnus-Tetens per il Punto di Rugiada (Dew Point)
    a, b = 17.27, 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100.0)
    dew_point_c = round((b * alpha) / (a - alpha), 1)

    # Humidex canadese / indice di disagio estivo
    e_vap = 6.11 * math.exp(5417.7530 * ((1.0 / 273.16) - (1.0 / (273.15 + dew_point_c))))
    humidex = round(temp_c + 0.5555 * (e_vap - 10.0), 1)

    # Windchill invernale (valido per T <= 10°C e vento >= 4.8 km/h)
    if temp_c <= 10.0 and wind_kmh >= 4.8:
        v_pow = wind_kmh ** 0.16
        windchill_c = round(
            13.12 + 0.6215 * temp_c - 11.37 * v_pow + 0.3965 * temp_c * v_pow, 1
        )
    else:
        windchill_c = round(temp_c, 1)

    perceived_c = humidex if temp_c >= 23.0 else (windchill_c if temp_c <= 10.0 else round(temp_c, 1))

    # Rilevamento del regime tipico di "Maccaja Ligure" (copertura stratocumuliforme marittima sotto inversione con alta pressione/umidità)
    is_maccaja = cloud_cover_pct >= 70 and rh >= 75 and pressure_hpa >= 1014.0 and wind_kmh <= 22.0
    maccaja_status = (
        "ATTIVA — Nubi basse marittime da inversione ('Maccaja' sottocosta)"
        if is_maccaja
        else "Assente"
    )

    return {
        "dew_point_c": dew_point_c,
        "perceived_temp_c": perceived_c,
        "humidex_c": humidex,
        "windchill_c": windchill_c,
        "maccaja_active": is_maccaja,
        "maccaja_status": maccaja_status,
    }


def evaluate_land_risk(
    precip_1h_mm: float,
    precip_3h_mm: float,
    precip_24h_mm: float,
    wind_kmh: float,
    gust_kmh: float,
    temp_c: float,
    visibility_m: float,
    convergence_score: int,
    elevation_m: int = 20,
    humidity_pct: float = 70.0,
    cloud_cover_pct: float = 40.0,
    pressure_hpa: float = 1015.0,
    uv_index: float = 2.0,
    shortwave_radiation_wm2: float = 180.0,
) -> dict[str, Any]:
    """Valuta gli indici di rischio per le persone a TERRA nella Provincia di Genova."""
    # 1. Rischio Idrogeologico & Pluviometrico (Torrenti Bisagno, Polcevera, Entella, rii minori)
    if precip_1h_mm >= 35 or precip_3h_mm >= 70 or (precip_1h_mm >= 20 and convergence_score >= 65):
        hydro_level = "red"
        hydro_label = "CRITICO — Rischio Piene Rapide Torrenti & Rii"
        hydro_advice = (
            "Evitare sottopassi, fondi stradali depressi e ponti su Bisagno, Polcevera, Fereggiano ed Entella. "
            "Salire ai piani superiori nelle aree esondabili."
        )
    elif precip_1h_mm >= 12 or precip_3h_mm >= 30 or precip_24h_mm >= 65:
        hydro_level = "orange"
        hydro_label = "MODERATO-ALTO — Ristagni e Rii Minori Reattivi"
        hydro_advice = (
            "Attenzione agli allagamenti localizzati nei sottopassi urbani (Brignole, Sampierdarena, Certosa) "
            "e possibili colate detritiche sui versanti collinari."
        )
    elif precip_1h_mm >= 2.5 or precip_3h_mm >= 8:
        hydro_level = "yellow"
        hydro_label = "ORDINARIO — Pioggia su Bacini Reattivi"
        hydro_advice = "Fondo stradale bagnato/scivoloso; monitorare l'evoluzione radar a 30-60 minuti."
    else:
        hydro_level = "green"
        hydro_label = "REGOLARE — Assenza Criticità Idrologiche"
        hydro_advice = "Condizioni idrogeologiche regolari sui principali bacini genovesi."

    # 2. Rischio Vento Urbano & Viabilità (Sopraelevata Aldo Moro, Viadotti A7/A10/A12/A26)
    if gust_kmh >= 85 or wind_kmh >= 60:
        wind_level = "red"
        wind_label = "BURRASCA FORTE — Rischio Chiusura Sopraelevata / Telonati"
        wind_advice = (
            "Pericolo per motocicli, furgoni telonati, alberature e ponteggi. "
            "Attenzione estrema su Sopraelevata Aldo Moro, Ponte San Giorgio e viadotti A10/A26."
        )
    elif gust_kmh >= 55 or wind_kmh >= 38:
        wind_level = "yellow"
        wind_label = "VENTO FORTE — Raffiche su Viadotti e Sbocchi Vallivi"
        wind_advice = (
            "Prudenza alla guida di mezzi a due ruote su lungomare, Sopraelevata e tratti esposti di Val Polcevera."
        )
    else:
        wind_level = "green"
        wind_label = "REGOLARE — Ventilazione Sostenibile"
        wind_advice = "Nessuna limitazione eolica prevista per la mobilità urbana ed extraurbana."

    # 3. Rischio Valichi Appenninici (Ghiaccio / Neve / Nebbia per Entroterra & A7/A26)
    freezing_level_m = max(0, int(elevation_m + (temp_c / 0.0065))) if temp_c > 0 else 0
    if temp_c <= 1.5 and precip_1h_mm > 0.3:
        mountain_level = "red" if temp_c <= 0.5 else "orange"
        mountain_label = "NEVE / GELICIDIO SUI VALICHI (Giovi, Turchino, A7, A26, Val d'Aveto)"
        mountain_advice = "Obbligo dotazioni invernali montate; attenzione al fenomeno del gelicidio (freezing rain) tra Valle Scrivia, Valle Stura e alta Val Polcevera."
    elif visibility_m < 400:
        mountain_level = "yellow"
        mountain_label = "NEBBIA DENSA SUI CRINALI"
        mountain_advice = f"Visibilità ridotta a {int(visibility_m)} m sui valichi appenninici."
    else:
        mountain_level = "green"
        mountain_label = f"VALICHI PERCORRIBILI (Zero Termico ~{freezing_level_m} m)"
        mountain_advice = "Viabilità appenninica regolare."

    # Calcolo livello sintetico complessivo Terra
    priority_order = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    overall_level = max(
        [hydro_level, wind_level, mountain_level], key=lambda x: priority_order[x]
    )

    thermo = compute_thermo_hygrometric_indices(
        temp_c=temp_c,
        humidity_pct=humidity_pct,
        wind_kmh=wind_kmh,
        cloud_cover_pct=cloud_cover_pct,
        pressure_hpa=pressure_hpa,
    )

    return {
        "overall_level": overall_level,
        "hydrogeological": {
            "level": hydro_level,
            "label": hydro_label,
            "advice": hydro_advice,
            "precip_1h_mm": round(precip_1h_mm, 1),
            "precip_3h_mm": round(precip_3h_mm, 1),
            "precip_24h_mm": round(precip_24h_mm, 1),
        },
        "wind_viability": {
            "level": wind_level,
            "label": wind_label,
            "advice": wind_advice,
            "wind_kmh": round(wind_kmh, 1),
            "gust_kmh": round(gust_kmh, 1),
        },
        "appennino_passes": {
            "level": mountain_level,
            "label": mountain_label,
            "advice": mountain_advice,
            "freezing_level_m": freezing_level_m,
            "visibility_m": int(visibility_m),
        },
        "microclimate_comfort": {
            **thermo,
            "uv_index": round(uv_index, 1),
            "solar_radiation_wm2": round(shortwave_radiation_wm2, 0),
        },
    }
