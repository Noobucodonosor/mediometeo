"""Motore di Fusione Pesata Multi-Modello ("Ligurian Weighted Ensemble") e Nowcasting (ADR-0003).

Fonde i modelli:
- Météo-France AROME HD (1.3 km) — Peso primario per le prime 36h e la convergenza ligure
- DWD ICON-D2 (2.2 km) — Peso convettivo e orografico per le prime 48h
- ECMWF IFS (9 km) — Riferimento sinottico europeo
- NCEP GFS — Quarto membro d'ensemble per calcolo spread e incertezza
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from backend.districts import District
from backend.engine.ligurian_diagnostics import (
    angular_difference_deg,
    detect_ligurian_convergence,
    evaluate_land_risk,
    ligurian_wind_name,
    vector_mean_deg,
)
from backend.engine.marine import compute_wave_dynamics
from backend.security import SAFETY_DISCLAIMER_LAND, SAFETY_DISCLAIMER_SEA


MODEL_SPECS = [
    ("meteofrance_arome_france_hd", "AROME 1.3km", 0.42),
    ("icon_d2", "ICON-D2 2km", 0.33),
    ("ecmwf_ifs025", "ECMWF IFS 9km", 0.18),
    ("gfs_seamless", "GFS Global", 0.07),
]

WMO_CODE_ITALIAN: dict[int, str] = {
    0: "Sereno",
    1: "Prevalentemente sereno",
    2: "Parzialmente nuvoloso",
    3: "Nuvoloso / Coperto (Maccaja Ligure)",
    45: "Nebbia sui valichi / Foschia densa",
    48: "Nebbia con brina",
    51: "Pioviggine debole",
    53: "Pioviggine moderata",
    55: "Pioviggine intensa da sbarramento",
    61: "Pioggia debole",
    63: "Pioggia moderata",
    65: "Pioggia forte",
    71: "Nevicata debole in Appennino",
    73: "Nevicata moderata",
    75: "Nevicata forte",
    80: "Rovescio di pioggia debole",
    81: "Rovescio moderato",
    82: "Nubifragio / Rovescio violento",
    95: "Temporale attivo",
    96: "Temporale con grandine piccola",
    99: "Temporale violento autorigenerante / Grandine",
}


def describe_wmo(code: int | float | None) -> str:
    if code is None:
        return "Variabile"
    c = int(code)
    return WMO_CODE_ITALIAN.get(c, "Variabile")


def _extract_series_value(
    container: dict[str, Any], var_name: str, model_suffix: str, idx: int, default: float = 0.0
) -> float | None:
    """Estrae un valore da `container[f'{var_name}_{model_suffix}'][idx]` o `container[var_name][idx]`."""
    key_with_model = f"{var_name}_{model_suffix}" if model_suffix else var_name
    arr = container.get(key_with_model)
    if arr is None and model_suffix:
        arr = container.get(var_name)
    if isinstance(arr, list) and 0 <= idx < len(arr) and arr[idx] is not None:
        try:
            return float(arr[idx])
        except (TypeError, ValueError):
            return default
    return None


def _extract_current_value(
    container: dict[str, Any], var_name: str, default: float = 0.0
) -> float:
    """Estrae il valore corrente medio o dal primo modello disponibile nel blocco `current`."""
    if var_name in container and container[var_name] is not None:
        try:
            return float(container[var_name])
        except (TypeError, ValueError):
            pass
    vals: list[float] = []
    for suffix, _, _ in MODEL_SPECS:
        k = f"{var_name}_{suffix}"
        if k in container and container[k] is not None:
            try:
                vals.append(float(container[k]))
            except (TypeError, ValueError):
                pass
    return round(sum(vals) / len(vals), 2) if vals else default


def fuse_hourly_step(hourly: dict[str, Any], idx: int, lead_hours: int) -> dict[str, Any]:
    """Esegue la fusione pesata tra AROME, ICON-D2, ECMWF e GFS per una singola ora `idx`."""
    temps: list[tuple[float, float, str]] = []
    precips: list[tuple[float, float, str]] = []
    winds: list[tuple[float, float, str]] = []
    gusts: list[tuple[float, float, str]] = []
    wind_dirs: list[tuple[float, float]] = []
    humidities: list[float] = []
    pressures: list[float] = []
    clouds: list[float] = []
    capes: list[float] = []
    visibilities: list[float] = []
    wmo_codes: list[int] = []

    model_breakdown: dict[str, dict[str, float | None]] = {}

    for suffix, label, base_w in MODEL_SPECS:
        # Oltre le 42 ore AROME e ICON-D2 terminano il dominio: aumentiamo il peso di ECMWF
        w = base_w
        if lead_hours > 42 and suffix in ("ecmwf_ifs025", "gfs_seamless"):
            w = 0.75 if suffix == "ecmwf_ifs025" else 0.25

        t = _extract_series_value(hourly, "temperature_2m", suffix, idx)
        p = _extract_series_value(hourly, "precipitation", suffix, idx)
        ws = _extract_series_value(hourly, "wind_speed_10m", suffix, idx)
        wg = _extract_series_value(hourly, "wind_gusts_10m", suffix, idx)
        wd = _extract_series_value(hourly, "wind_direction_10m", suffix, idx)
        rh = _extract_series_value(hourly, "relative_humidity_2m", suffix, idx)
        pr = _extract_series_value(hourly, "pressure_msl", suffix, idx)
        cl = _extract_series_value(hourly, "cloud_cover", suffix, idx)
        cp = _extract_series_value(hourly, "cape", suffix, idx)
        vis = _extract_series_value(hourly, "visibility", suffix, idx)
        wc = _extract_series_value(hourly, "weather_code", suffix, idx)

        model_breakdown[suffix] = {
            "label": label,
            "temp_c": round(t, 1) if t is not None else None,
            "precip_mm": round(p, 1) if p is not None else None,
            "wind_kmh": round(ws, 1) if ws is not None else None,
            "gust_kmh": round(wg, 1) if wg is not None else None,
            "wind_dir_deg": round(wd, 0) if wd is not None else None,
        }

        if t is not None:
            temps.append((t, w, label))
        if p is not None:
            precips.append((max(0.0, p), w, label))
        if ws is not None:
            winds.append((max(0.0, ws), w, label))
        if wg is not None:
            gusts.append((max(0.0, wg), w, label))
        if wd is not None:
            wind_dirs.append((wd, w))
        if rh is not None:
            humidities.append(rh)
        if pr is not None:
            pressures.append(pr)
        if cl is not None:
            clouds.append(cl)
        if cp is not None:
            capes.append(max(0.0, cp))
        if vis is not None:
            visibilities.append(max(50.0, vis))
        if wc is not None:
            wmo_codes.append(int(wc))

    def weighted_avg(items: list[tuple[float, float, str]], default: float = 0.0) -> float:
        if not items:
            return default
        total_w = sum(w for _, w, _ in items)
        if total_w <= 0:
            return items[0][0]
        return sum(val * w for val, w, _ in items) / total_w

    temp_c = round(weighted_avg(temps, 16.0), 1)
    precip_mean = round(weighted_avg(precips, 0.0), 2)
    precip_max_lam = round(max((v for v, _, _ in precips), default=0.0), 1)
    # Peak Preservation (ADR-0003): se un modello LAM vede un picco convettivo intenso,
    # fondiamo 65% media pesata + 35% picco LAM per non sottostimare mai nubifragi locali.
    precip_fused = round(0.65 * precip_mean + 0.35 * precip_max_lam, 1) if precip_max_lam >= 3.0 else round(precip_mean, 1)

    wind_kmh = round(weighted_avg(winds, 8.0), 1)
    gust_mean = weighted_avg(gusts, wind_kmh * 1.35)
    gust_max_lam = max((v for v, _, _ in gusts), default=gust_mean)
    gust_kmh = round(max(wind_kmh, 0.6 * gust_mean + 0.4 * gust_max_lam), 1)

    wind_dir_deg = vector_mean_deg(
        [d for d, _ in wind_dirs], [w for _, w in wind_dirs]
    ) if wind_dirs else 0.0

    # Spread direzionale massimo tra i modelli (indicatore di convergenza sul Golfo di Genova)
    dir_spread = 0.0
    if len(wind_dirs) >= 2:
        angles = [d for d, _ in wind_dirs]
        dir_spread = max(
            angular_difference_deg(angles[i], angles[j])
            for i in range(len(angles))
            for j in range(i + 1, len(angles))
        )

    # Calcolo Confidence Score (0-100%) basato sullo spread tra modelli su temperatura, pioggia e vento
    temp_spread = (max(v for v, _, _ in temps) - min(v for v, _, _ in temps)) if len(temps) >= 2 else 0.5
    precip_spread = (max(v for v, _, _ in precips) - min(v for v, _, _ in precips)) if len(precips) >= 2 else 0.0
    wind_spread = (max(v for v, _, _ in winds) - min(v for v, _, _ in winds)) if len(winds) >= 2 else 2.0

    penalty = (temp_spread * 3.0) + (precip_spread * 2.5) + (wind_spread * 0.6) + (lead_hours * 0.15)
    confidence_pct = int(max(45, min(98, round(96 - penalty))))

    wmo_code = max(wmo_codes) if wmo_codes else 1
    humidity_pct = round(sum(humidities) / len(humidities), 0) if humidities else 70.0
    pressure_hpa = round(sum(pressures) / len(pressures), 1) if pressures else 1015.0
    cloud_pct = round(sum(clouds) / len(clouds), 0) if clouds else 35.0
    cape_val = round(max(capes), 0) if capes else 0.0
    vis_m = round(min(visibilities), 0) if visibilities else 10000.0

    return {
        "temp_c": temp_c,
        "precip_mm": precip_fused,
        "precip_max_lam_mm": precip_max_lam,
        "wind_kmh": wind_kmh,
        "gust_kmh": gust_kmh,
        "wind_dir_deg": wind_dir_deg,
        "wind_dir_spread_deg": round(dir_spread, 1),
        "humidity_pct": humidity_pct,
        "pressure_hpa": pressure_hpa,
        "cloud_cover_pct": cloud_pct,
        "cape_j_kg": cape_val,
        "visibility_m": vis_m,
        "weather_code": wmo_code,
        "weather_description": describe_wmo(wmo_code),
        "confidence_pct": confidence_pct,
        "models": model_breakdown,
    }


def build_synthetic_fallback_dataset(district: District) -> dict[str, Any]:
    """Genera un dataset fisico coerente di emergenza se tutte le reti esterne sono offline (ADR-0002)."""
    now = datetime.now(timezone.utc)
    base_temp = 16.5 if district.elevation_m < 100 else max(7.0, 16.5 - district.elevation_m * 0.0065)
    hourly_times = [now.strftime("%Y-%m-%dT%H:00") for _ in range(48)]
    return {
        "multimodel": {
            "current": {
                "temperature_2m": base_temp,
                "relative_humidity_2m": 72.0,
                "precipitation": 0.0,
                "pressure_msl": 1016.0,
                "wind_speed_10m": 14.0,
                "wind_direction_10m": 15.0,
                "wind_gusts_10m": 22.0,
                "weather_code": 1,
            },
            "hourly": {
                "time": hourly_times,
                "temperature_2m_meteofrance_arome_france_hd": [base_temp] * 48,
                "precipitation_meteofrance_arome_france_hd": [0.0] * 48,
                "wind_speed_10m_meteofrance_arome_france_hd": [14.0] * 48,
                "wind_gusts_10m_meteofrance_arome_france_hd": [22.0] * 48,
                "wind_direction_10m_meteofrance_arome_france_hd": [15.0] * 48,
            },
        },
        "marine": {
            "current": {
                "wave_height": 0.45,
                "wave_period": 4.8,
                "wave_direction": 195.0,
                "wind_wave_height": 0.25,
                "swell_wave_height": 0.35,
                "swell_wave_period": 5.2,
                "sea_surface_temperature": 18.0,
            },
            "hourly": {
                "time": hourly_times,
                "wave_height": [0.45] * 48,
                "wave_period": [4.8] * 48,
                "wave_direction": [195.0] * 48,
            },
        },
        "radar": {"frames": [], "latest_tile_url": None},
        "sources_active": ["fallback_physical_baseline"],
        "sources_degraded": ["external_network_offline"],
    }


def build_complete_weather_package(
    district: District,
    raw_data: dict[str, Any],
    custom_coords: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Costruisce il pacchetto unificato Nowcast (0-3h) + Forecast (48h & 7d) per Terra e Mare."""
    if not raw_data.get("multimodel"):
        raw_data = build_synthetic_fallback_dataset(district)

    mm = raw_data["multimodel"]
    marine_raw = raw_data.get("marine") or {}
    radar_raw = raw_data.get("radar") or {}

    hourly = mm.get("hourly") or {}
    hourly_times: list[str] = hourly.get("time") or []
    total_hours = len(hourly_times)

    # Identifica l'indice orario corrente più vicino all'ora locale
    now_str = datetime.now().strftime("%Y-%m-%dT%H:00")
    start_idx = 0
    for idx, t_str in enumerate(hourly_times):
        if t_str >= now_str:
            start_idx = idx
            break

    # 1. Fusione oraria delle prossime 48 ore
    fused_hourly: list[dict[str, Any]] = []
    marine_hourly = marine_raw.get("hourly") or {}

    for offset in range(min(48, max(1, total_hours - start_idx))):
        h_idx = start_idx + offset
        step = fuse_hourly_step(hourly, h_idx, lead_hours=offset)
        time_iso = hourly_times[h_idx] if h_idx < len(hourly_times) else now_str

        # Integrazione stato del mare per quell'ora
        wh = _extract_series_value(marine_hourly, "wave_height", "", h_idx, 0.35) or 0.35
        wp = _extract_series_value(marine_hourly, "wave_period", "", h_idx, 4.5) or 4.5
        wd = _extract_series_value(marine_hourly, "wave_direction", "", h_idx, 200.0) or 200.0
        wwh = _extract_series_value(marine_hourly, "wind_wave_height", "", h_idx, 0.2) or 0.2
        swh = _extract_series_value(marine_hourly, "swell_wave_height", "", h_idx, 0.25) or 0.25
        swp = _extract_series_value(marine_hourly, "swell_wave_period", "", h_idx, wp) or wp
        sst = _extract_series_value(marine_hourly, "sea_surface_temperature", "", h_idx, 18.0) or 18.0

        marine_step = compute_wave_dynamics(
            hs_m=wh,
            period_s=wp,
            wave_dir_deg=wd,
            wind_wave_m=wwh,
            swell_wave_m=swh,
            swell_period_s=swp,
            wind_speed_kmh=step["wind_kmh"],
            wind_gust_kmh=step["gust_kmh"],
            wind_dir_deg=step["wind_dir_deg"],
            sst_c=sst,
        )

        wind_meta = ligurian_wind_name(step["wind_dir_deg"], step["wind_kmh"])
        step["time"] = time_iso
        step["wind_cardinal"] = wind_meta["cardinal"]
        step["wind_ligurian_name"] = wind_meta["name"]
        step["wind_knots"] = marine_step["wind"]["speed_knots"]
        step["gust_knots"] = marine_step["wind"]["gust_knots"]
        step["beaufort_force"] = marine_step["wind"]["beaufort"]["force"]
        step["wave_hs_m"] = marine_step["waves"]["significant_height_m"]
        step["wave_hmax_m"] = marine_step["waves"]["max_height_m"]
        step["wave_period_s"] = marine_step["waves"]["peak_period_s"]
        step["wave_dir_deg"] = marine_step["waves"]["direction_deg"]
        step["wave_dir_cardinal"] = marine_step["waves"]["direction_cardinal"]
        step["douglas_degree"] = marine_step["waves"]["douglas"]["degree"]
        step["douglas_label"] = marine_step["waves"]["douglas"]["label"]
        step["steepness_warning"] = marine_step["waves"]["steepness_warning"]
        fused_hourly.append(step)

    current_step = fused_hourly[0] if fused_hourly else fuse_hourly_step(hourly, 0, 0)

    # Tendenza barometrica a 3 ore (ΔP / 3h — cruciale per i naviganti nel Mar Ligure)
    pressure_now = current_step["pressure_hpa"]
    pressure_plus_3h = fused_hourly[min(3, len(fused_hourly) - 1)]["pressure_hpa"] if fused_hourly else pressure_now
    pressure_delta_3h = round(pressure_plus_3h - pressure_now, 1)
    if pressure_delta_3h <= -2.5:
        pressure_trend_label = f"In rapido calo ({pressure_delta_3h:+.1f} hPa/3h) — Avviso peggioramento / burrasca"
    elif pressure_delta_3h <= -1.0:
        pressure_trend_label = f"In calo ({pressure_delta_3h:+.1f} hPa/3h)"
    elif pressure_delta_3h >= 1.5:
        pressure_trend_label = f"In deciso aumento ({pressure_delta_3h:+.1f} hPa/3h) — Ingresso Tramontana/alta pressione"
    else:
        pressure_trend_label = f"Stazionaria ({pressure_delta_3h:+.1f} hPa/3h)"

    # 2. Timeline Nowcasting a 15 minuti (prossime 3 ore = 12 step da 15 min)
    minutely = mm.get("minutely_15") or {}
    m_times: list[str] = minutely.get("time") or []
    nowcast_15m: list[dict[str, Any]] = []
    for idx in range(min(12, len(m_times))):
        p_15 = _extract_series_value(minutely, "precipitation", "", idx, 0.0) or 0.0
        # p_15 è precipitazione in 15 min: intensità equivalente mm/h = p_15 * 4
        rain_rate_mm_h = round(max(0.0, p_15 * 4.0), 1)
        t_15 = _extract_series_value(minutely, "temperature_2m", "", idx, current_step["temp_c"]) or current_step["temp_c"]
        ws_15 = _extract_series_value(minutely, "wind_speed_10m", "", idx, current_step["wind_kmh"]) or current_step["wind_kmh"]
        wg_15 = _extract_series_value(minutely, "wind_gusts_10m", "", idx, current_step["gust_kmh"]) or current_step["gust_kmh"]
        wd_15 = _extract_series_value(minutely, "wind_direction_10m", "", idx, current_step["wind_dir_deg"]) or current_step["wind_dir_deg"]
        wc_15 = _extract_series_value(minutely, "weather_code", "", idx, current_step["weather_code"]) or current_step["weather_code"]
        w_info = ligurian_wind_name(wd_15, ws_15)
        nowcast_15m.append(
            {
                "time": m_times[idx],
                "temp_c": round(t_15, 1),
                "precip_15m_mm": round(p_15, 2),
                "rain_rate_mm_h": rain_rate_mm_h,
                "wind_kmh": round(ws_15, 1),
                "gust_kmh": round(wg_15, 1),
                "wind_knots": round(ws_15 / 1.852, 1),
                "gust_knots": round(wg_15 / 1.852, 1),
                "wind_dir_deg": round(wd_15, 0),
                "wind_cardinal": w_info["cardinal"],
                "wind_name": w_info["name"],
                "weather_code": int(wc_15),
                "weather_description": describe_wmo(wc_15),
            }
        )

    # Fallback se l'endpoint minutely_15 non ha restituito step sufficienti: interpola dalle prime 3 ore
    if not nowcast_15m and fused_hourly:
        for h in fused_hourly[:4]:
            nowcast_15m.append(
                {
                    "time": h["time"],
                    "temp_c": h["temp_c"],
                    "precip_15m_mm": round(h["precip_mm"] / 4.0, 2),
                    "rain_rate_mm_h": h["precip_mm"],
                    "wind_kmh": h["wind_kmh"],
                    "gust_kmh": h["gust_kmh"],
                    "wind_knots": h["wind_knots"],
                    "gust_knots": h["gust_knots"],
                    "wind_dir_deg": h["wind_dir_deg"],
                    "wind_cardinal": h["wind_cardinal"],
                    "wind_name": h["wind_ligurian_name"],
                    "weather_code": h["weather_code"],
                    "weather_description": h["weather_description"],
                }
            )

    # 3. Cumulate Pluviometriche e Diagnostica Convergenza Ligure + Rischi Terra/Mare
    precip_1h = max(
        current_step["precip_mm"],
        max((s["rain_rate_mm_h"] for s in nowcast_15m[:4]), default=0.0),
    )
    precip_3h = sum(h["precip_mm"] for h in fused_hourly[:3])
    precip_24h = sum(h["precip_mm"] for h in fused_hourly[:24])

    convergence = detect_ligurian_convergence(
        wind_dir_deg=current_step["wind_dir_deg"],
        wind_speed_kmh=current_step["wind_kmh"],
        gust_kmh=current_step["gust_kmh"],
        precip_mm_h=precip_1h,
        humidity_pct=current_step["humidity_pct"],
        cape_j_kg=current_step["cape_j_kg"],
        model_dir_spread_deg=current_step["wind_dir_spread_deg"],
    )

    land_risk = evaluate_land_risk(
        precip_1h_mm=precip_1h,
        precip_3h_mm=precip_3h,
        precip_24h_mm=precip_24h,
        wind_kmh=current_step["wind_kmh"],
        gust_kmh=current_step["gust_kmh"],
        temp_c=current_step["temp_c"],
        visibility_m=current_step["visibility_m"],
        convergence_score=convergence["convergence_score"],
        elevation_m=max(0, district.elevation_m),
    )

    marine_current_raw = marine_raw.get("current") or {}
    sea_state = compute_wave_dynamics(
        hs_m=float(marine_current_raw.get("wave_height") or current_step.get("wave_hs_m") or 0.4),
        period_s=float(marine_current_raw.get("wave_period") or current_step.get("wave_period_s") or 4.5),
        wave_dir_deg=float(marine_current_raw.get("wave_direction") or current_step.get("wave_dir_deg") or 200.0),
        wind_wave_m=float(marine_current_raw.get("wind_wave_height") or 0.2),
        swell_wave_m=float(marine_current_raw.get("swell_wave_height") or 0.3),
        swell_period_s=float(marine_current_raw.get("swell_wave_period") or 5.0),
        wind_speed_kmh=current_step["wind_kmh"],
        wind_gust_kmh=current_step["gust_kmh"],
        wind_dir_deg=current_step["wind_dir_deg"],
        sst_c=float(marine_current_raw.get("sea_surface_temperature") or 18.0),
    )

    # 4. Previsione Giornaliera a 7 Giorni (Sintesi Multi-Modello Terra + Mare)
    daily_raw = mm.get("daily") or {}
    marine_daily_raw = marine_raw.get("daily") or {}
    d_times: list[str] = daily_raw.get("time") or []
    daily_forecast: list[dict[str, Any]] = []

    for d_idx, day_str in enumerate(d_times[:7]):
        tmax_vals = [
            _extract_series_value(daily_raw, "temperature_2m_max", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        tmin_vals = [
            _extract_series_value(daily_raw, "temperature_2m_min", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        psum_vals = [
            _extract_series_value(daily_raw, "precipitation_sum", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        wmax_vals = [
            _extract_series_value(daily_raw, "wind_speed_10m_max", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        gmax_vals = [
            _extract_series_value(daily_raw, "wind_gusts_10m_max", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        wdir_vals = [
            _extract_series_value(daily_raw, "wind_direction_10m_dominant", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]
        wcode_vals = [
            _extract_series_value(daily_raw, "weather_code", s, d_idx)
            for s, _, _ in MODEL_SPECS
        ]

        clean_tmax = [v for v in tmax_vals if v is not None]
        clean_tmin = [v for v in tmin_vals if v is not None]
        clean_psum = [max(0.0, v) for v in psum_vals if v is not None]
        clean_wmax = [max(0.0, v) for v in wmax_vals if v is not None]
        clean_gmax = [max(0.0, v) for v in gmax_vals if v is not None]
        clean_wdir = [v for v in wdir_vals if v is not None]
        clean_wcode = [int(v) for v in wcode_vals if v is not None]

        wave_max_m = _extract_series_value(marine_daily_raw, "wave_height_max", "", d_idx, 0.5) or 0.5
        wave_per_max = _extract_series_value(marine_daily_raw, "wave_period_max", "", d_idx, 5.0) or 5.0
        wave_dom_dir = _extract_series_value(marine_daily_raw, "wave_direction_dominant", "", d_idx, 200.0) or 200.0

        dom_wind_deg = vector_mean_deg(clean_wdir) if clean_wdir else 0.0
        max_wind_kmh = round(sum(clean_wmax) / len(clean_wmax), 1) if clean_wmax else 15.0
        max_gust_kmh = round(max(clean_gmax), 1) if clean_gmax else round(max_wind_kmh * 1.35, 1)
        wind_meta_day = ligurian_wind_name(dom_wind_deg, max_wind_kmh)
        douglas_day = compute_wave_dynamics(
            hs_m=wave_max_m,
            period_s=wave_per_max,
            wave_dir_deg=wave_dom_dir,
            wind_speed_kmh=max_wind_kmh,
            wind_gust_kmh=max_gust_kmh,
            wind_dir_deg=dom_wind_deg,
        )

        daily_forecast.append(
            {
                "date": day_str,
                "temp_max_c": round(sum(clean_tmax) / len(clean_tmax), 1) if clean_tmax else 18.0,
                "temp_min_c": round(sum(clean_tmin) / len(clean_tmin), 1) if clean_tmin else 12.0,
                "precip_sum_mm": round(sum(clean_psum) / len(clean_psum), 1) if clean_psum else 0.0,
                "precip_max_model_mm": round(max(clean_psum), 1) if clean_psum else 0.0,
                "wind_max_kmh": max_wind_kmh,
                "gust_max_kmh": max_gust_kmh,
                "wind_max_knots": douglas_day["wind"]["speed_knots"],
                "gust_max_knots": douglas_day["wind"]["gust_knots"],
                "beaufort_max": douglas_day["wind"]["beaufort"]["force"],
                "wind_dominant_cardinal": wind_meta_day["cardinal"],
                "wind_dominant_name": wind_meta_day["name"],
                "wave_max_hs_m": douglas_day["waves"]["significant_height_m"],
                "wave_max_hmax_m": douglas_day["waves"]["max_height_m"],
                "wave_period_max_s": round(wave_per_max, 1),
                "douglas_max_label": douglas_day["waves"]["douglas"]["label"],
                "weather_code": max(clean_wcode) if clean_wcode else 1,
                "weather_description": describe_wmo(max(clean_wcode) if clean_wcode else 1),
            }
        )

    target_lat, target_lon = custom_coords if custom_coords else (district.lat, district.lon)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_stale": False,
        "stale_warning": None,
        "district": district.to_dict(),
        "coordinates": {
            "lat": target_lat,
            "lon": target_lon,
            "sea_lat": district.sea_lat,
            "sea_lon": district.sea_lon,
            "is_custom_pin": custom_coords is not None,
        },
        "sources": {
            "active": raw_data.get("sources_active", []),
            "degraded": raw_data.get("sources_degraded", []),
            "ensemble_weights": {
                "AROME_1.3km": "42% (Short-Range & Convergenza Ligure)",
                "ICON_D2_2.2km": "33% (Convezione & Vento Orografico)",
                "ECMWF_IFS_9km": "18% (Sinottica Mediterranea / 75% >42h)",
                "GFS_Seamless": "7% (Spread Ensemble)",
            },
        },
        "nowcast": {
            "current": {
                **current_step,
                "pressure_delta_3h_hpa": pressure_delta_3h,
                "pressure_trend_label": pressure_trend_label,
            },
            "timeline_15m": nowcast_15m,
            "radar": radar_raw,
            "ligurian_convergence": convergence,
        },
        "land": {
            "risk_assessment": land_risk,
            "safety_disclaimer": SAFETY_DISCLAIMER_LAND,
        },
        "sea": {
            "marine_conditions": sea_state,
            "meteomar_sector": district.arpal_zone,
            "safety_disclaimer": SAFETY_DISCLAIMER_SEA,
        },
        "forecast": {
            "hourly_48h": fused_hourly,
            "daily_7d": daily_forecast,
        },
    }
