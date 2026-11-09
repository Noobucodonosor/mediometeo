"""Motore Meteo-Marino per il Golfo di Genova e l'Alto Mar Ligure (ADR-0003 / TASK-MAR-01).

Calcola:
- Conversione vento in Nodi (kt) e Scala Beaufort (0-12)
- Stato del Mare secondo la Scala Douglas (0-9) per onda significativa (Hs) e onda massima (Hmax)
- Ripidità d'onda (Wave Steepness = Hs / L) per intercettare l'onda corta frangente di Tramontana/Libeccio
- Semaforo Operativo di Sicurezza in Mare (Vela/Diporto, Pesca Costiera, Kayak/SUP/Balneazione, Ormeggi/Portuale)
"""

from __future__ import annotations

import math
from typing import Any
from backend.engine.ligurian_diagnostics import ligurian_wind_name


def kmh_to_knots(speed_kmh: float) -> float:
    """Converte km/h in nodi nautici (kt)."""
    return round(float(speed_kmh) / 1.852, 1)


def knots_to_beaufort(knots: float) -> dict[str, Any]:
    """Restituisce il grado Beaufort (0-12) e la descrizione nautica italiana."""
    thresholds = [
        (1.0, 0, "Calma", "Mare a specchio"),
        (3.5, 1, "Bava di vento", "Increspature senza schiuma"),
        (6.5, 2, "Brezza leggera", "Onde piccole che non rompono"),
        (10.5, 3, "Brezza tesa", "Creste che iniziano a rompere, qualche pecorella"),
        (16.5, 4, "Vento moderato", "Onde piccole più lunghe, numerose pecorelle"),
        (21.5, 5, "Vento teso", "Onde moderate allungate, spruzzi"),
        (27.5, 6, "Vento fresco", "Si formano onde grandi, creste di schiuma bianca estese"),
        (33.5, 7, "Vento forte (Pre-Burrasca)", "Il mare ingrossa, schiuma striata nel vento"),
        (40.5, 8, "Burrasca moderata", "Onde alte con creste che frangono in vortici di spruzzi"),
        (47.5, 9, "Burrasca forte", "Onde grosse, densa schiuma riduce la visibilità"),
        (55.5, 10, "Tempesta", "Onde molto grosse con lunghe creste a pennacchio"),
        (63.5, 11, "Tempesta violenta", "Onde eccezionalmente alte, mare bianco di schiuma"),
    ]
    for limit, degree, label, sea_desc in thresholds:
        if knots < limit:
            return {"force": degree, "label": label, "sea_effect": sea_desc}
    return {"force": 12, "label": "Uragano", "sea_effect": "Aria piena di schiuma e spruzzi, visibilità nulla"}


def hs_to_douglas(hs_m: float) -> dict[str, Any]:
    """Converte l'altezza d'onda significativa Hs (metri) nella Scala Douglas dello stato del mare."""
    if hs_m < 0.05:
        return {"degree": 0, "label": "Calmo (0)", "range_m": "0 m"}
    if hs_m < 0.10:
        return {"degree": 1, "label": "Quasi calmo (1)", "range_m": "0 - 0.1 m"}
    if hs_m < 0.50:
        return {"degree": 2, "label": "Poco mosso (2)", "range_m": "0.1 - 0.5 m"}
    if hs_m < 1.25:
        return {"degree": 3, "label": "Mosso (3)", "range_m": "0.5 - 1.25 m"}
    if hs_m < 2.50:
        return {"degree": 4, "label": "Molto mosso (4)", "range_m": "1.25 - 2.5 m"}
    if hs_m < 4.00:
        return {"degree": 5, "label": "Agitato (5)", "range_m": "2.5 - 4.0 m"}
    if hs_m < 6.00:
        return {"degree": 6, "label": "Molto agitato (6)", "range_m": "4.0 - 6.0 m"}
    if hs_m < 9.00:
        return {"degree": 7, "label": "Grosso (7)", "range_m": "6.0 - 9.0 m"}
    if hs_m < 14.0:
        return {"degree": 8, "label": "Molto grosso (8)", "range_m": "9.0 - 14.0 m"}
    return {"degree": 9, "label": "Tempestoso (9)", "range_m": ">14.0 m"}


def compute_wave_dynamics(
    hs_m: float,
    period_s: float,
    wave_dir_deg: float,
    wind_wave_m: float = 0.0,
    swell_wave_m: float = 0.0,
    swell_period_s: float = 0.0,
    wind_speed_kmh: float = 0.0,
    wind_gust_kmh: float = 0.0,
    wind_dir_deg: float = 0.0,
    sst_c: float = 17.5,
) -> dict[str, Any]:
    """Calcola la cinematica completa dell'onda e la sicurezza per chi va in mare nel Golfo Ligure."""
    hs = max(0.05, float(hs_m))
    tp = max(2.5, float(period_s))

    # Se il modello marino sottostima l'onda corta generata da un forte vento catabatico sottocosta (es. Tramontana a Genova)
    wind_kt = kmh_to_knots(wind_speed_kmh)
    gust_kt = kmh_to_knots(wind_gust_kmh)
    if wind_kt >= 18.0 and hs < 0.7:
        # Stima empirica per fetch costiero breve (2-6 miglia) nel Golfo di Genova
        coastal_wind_hs = round(min(2.4, 0.038 * wind_kt), 2)
        hs = max(hs, coastal_wind_hs)
        wind_wave_m = max(wind_wave_m, hs * 0.85)
        tp = min(tp, 4.2)

    # Altezza d'onda massima statistica (Hmax ≈ 1.65 * Hs, fino a 1.85 nei groppi)
    hmax_m = round(hs * 1.65, 2)

    # Lunghezza d'onda in acqua profonda/intermedia: L = (g / 2π) * T^2 ≈ 1.56 * T^2
    wavelength_m = round(1.56 * (tp ** 2), 1)
    steepness = hs / max(1.0, wavelength_m)

    # Classificazione ripidità (onda corta e ripida vs onda lunga di swell)
    if hs >= 0.8 and (tp <= 4.8 or steepness >= 0.042):
        steepness_class = "ONDA CORTA RIPIDA & FRANGENTE (Pericolosa per diporto)"
        steepness_warning = True
    elif hs >= 1.5 and tp >= 7.5:
        steepness_class = "ONDA LUNGA FORMATA DI SWELL (Attenzione risacca a riva/porti)"
        steepness_warning = False
    else:
        steepness_class = "PROFILO D'ONDA REGOLARE"
        steepness_warning = False

    beaufort = knots_to_beaufort(wind_kt)
    douglas = hs_to_douglas(hs)
    wind_info = ligurian_wind_name(wind_dir_deg, wind_speed_kmh)
    wave_compass = ligurian_wind_name(wave_dir_deg, 20.0)["cardinal"]

    # Matrice di Sicurezza per Profilo Utente in Mare
    # 1. Piccolo Diporto & Vela (< 12m)
    if hs >= 2.0 or wind_kt >= 25 or gust_kt >= 32:
        sailing_status = {"level": "red", "label": "SCONSIGLIATO / RIENTRO IN PORTO", "note": "Condizioni di burrasca o mare molto mosso/agitato; restare all'ormeggio."}
    elif hs >= 1.0 or wind_kt >= 16 or gust_kt >= 22 or steepness_warning:
        sailing_status = {"level": "yellow", "label": "SOLO EQUIPAGGI ESPERTI (Manovre Ridotte)", "note": "Prevedere mano di terzaroli preventiva; attenzione alle raffiche di caduta sottocosta."}
    else:
        sailing_status = {"level": "green", "label": "FAVOREVOLE ALLA NAVIGAZIONE", "note": "Condizioni ottimali per navigazione a vela e motore."}

    # 2. Pesca Sportiva / Costiera
    if hs >= 1.5 or wind_kt >= 20 or gust_kt >= 26 or steepness_warning:
        fishing_status = {"level": "red", "label": "NON IDONEO / PERICOLO SCARROCCIO", "note": "Onda e vento ostacolano la tenuta all'ancora e la sicurezza in murata."}
    elif hs >= 0.8 or wind_kt >= 12:
        fishing_status = {"level": "yellow", "label": "CAUTELA SOTTOCOSTA", "note": "Possibile rollio fastidioso alla fonda; monitorare rotazioni del vento."}
    else:
        fishing_status = {"level": "green", "label": "OTTIMO PER USCITA IN MARE", "note": "Stato del mare favorevole per traina, bolentino e pesca costiera."}

    # 3. Kayak, SUP, Deriva & Balneazione
    if hs >= 0.7 or wind_kt >= 13 or gust_kt >= 18:
        kayak_status = {"level": "red", "label": "VIETATO / RISCHIO DERIVA AL LARGO", "note": "Con Tramontana/Grecale forte rischio di essere spinti al largo; con Libeccio/Scirocco risacca pericolosa a riva."}
    elif hs >= 0.4 or wind_kt >= 8:
        kayak_status = {"level": "yellow", "label": "SOLO SOTTOCOSTA PROTETTA (<200m)", "note": "Increspature e brezza tesa; non allontanarsi dalle calette riparate."}
    else:
        kayak_status = {"level": "green", "label": "CONDIZIONI IDEALI", "note": "Mare calmo o quasi calmo."}

    # 4. Sicurezza Ormeggi & Manovre Portuali (Genova, Rapallo, Santa Margherita, Camogli, Chiavari)
    if hs >= 2.2 or gust_kt >= 34:
        harbor_status = {"level": "red", "label": "RINFORZARE ORMEGGI & PARABORDI", "note": "Forte risacca nei porticcioli esposti a Sud/Sud-Est e raffiche violente di traverso in manovra."}
    elif hs >= 1.2 or gust_kt >= 22:
        harbor_status = {"level": "yellow", "label": "ATTENZIONE IN MANOVRA / RISACCA", "note": "Verificare cime di poppa/prua e molle d'ormeggio."}
    else:
        harbor_status = {"level": "green", "label": "ORMEGGI E RADE TRANQUILLE", "note": "Acque portuali calme."}

    priority_order = {"green": 0, "yellow": 1, "red": 2}
    overall_sea_level = max(
        [sailing_status["level"], fishing_status["level"], harbor_status["level"]],
        key=lambda x: priority_order[x],
    )

    return {
        "overall_level": overall_sea_level,
        "wind": {
            "speed_knots": wind_kt,
            "gust_knots": gust_kt,
            "speed_kmh": round(wind_speed_kmh, 1),
            "gust_kmh": round(wind_gust_kmh, 1),
            "direction_deg": round(wind_dir_deg, 0),
            "cardinal": wind_info["cardinal"],
            "ligurian_name": wind_info["name"],
            "local_note": wind_info["local_note"],
            "beaufort": beaufort,
        },
        "waves": {
            "significant_height_m": round(hs, 2),
            "max_height_m": hmax_m,
            "wind_wave_height_m": round(max(0.0, wind_wave_m), 2),
            "swell_height_m": round(max(0.0, swell_wave_m), 2),
            "peak_period_s": round(tp, 1),
            "swell_period_s": round(max(tp, swell_period_s), 1),
            "wavelength_m": wavelength_m,
            "direction_deg": round(wave_dir_deg, 0),
            "direction_cardinal": wave_compass,
            "douglas": douglas,
            "steepness_ratio": round(steepness, 4),
            "steepness_class": steepness_class,
            "steepness_warning": steepness_warning,
            "sea_surface_temp_c": round(sst_c, 1),
        },
        "activities_safety": {
            "sailing_yachting": sailing_status,
            "coastal_fishing": fishing_status,
            "kayak_sup_swimming": kayak_status,
            "harbor_mooring": harbor_status,
        },
    }
