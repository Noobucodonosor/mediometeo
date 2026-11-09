"""Motore Pubblico di Rotta Costiera, Calcolo ETA, Limiti AMP Portofino e Confronto Andata/Ritorno (ADR-0006 / ORO-6).

Caratteristiche:
- Grafo nautico costiero dell'intero Golfo di Genova (Arenzano -> Voltri -> Genova Porto Antico -> Boccadasse -> Nervi -> Sori -> Camogli -> Punta Chiappa -> San Fruttuoso -> Faro di Portofino -> Portofino -> Paraggi -> Santa Margherita -> Rapallo -> Zoagli -> Chiavari/Lavagna -> Sestri Levante).
- Nessuna rotta "taglia" i promontori via terra (es. per andare da Camogli a Portofino passa obbligatoriamente per Punta Chiappa, San Fruttuoso e il Faro di Portofino).
- Rispetta i limiti di velocità dell'Area Marina Protetta (AMP) di Portofino (Zona B max 5 kt, Zona C max 7 kt).
- Calcola distanza di andata e ritorno in Miglia Nautiche (NM), velocità media richiesta in nodi per rientrare entro `duration_minutes` considerando eventuali soste (`stop_minutes`), l'orario limite di inversione rotta (*Turnaround Time*) e il confronto fisico tra Andata e Ritorno.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import heapq
import math
from typing import Any


COASTAL_WAYPOINTS: dict[str, dict[str, Any]] = {
    "arenzano": {"id": "arenzano", "name": "Porto di Arenzano", "lat": 44.3990, "lon": 8.6850, "amp_zone": None},
    "voltri_pra": {"id": "voltri_pra", "name": "Rada di Voltri / Canale di Pra'", "lat": 44.4180, "lon": 8.7750, "amp_zone": None},
    "genova_porto": {"id": "genova_porto", "name": "Genova Porto Antico / Diga", "lat": 44.3985, "lon": 8.9260, "amp_zone": None},
    "boccadasse": {"id": "boccadasse", "name": "Cala di Boccadasse", "lat": 44.3885, "lon": 8.9735, "amp_zone": None},
    "nervi": {"id": "nervi", "name": "Porticciolo e Scogliera di Nervi", "lat": 44.3805, "lon": 9.0350, "amp_zone": None},
    "recco_sori": {"id": "recco_sori", "name": "Rada di Sori & Recco", "lat": 44.3620, "lon": 9.1200, "amp_zone": None},
    "camogli": {"id": "camogli", "name": "Porto di Camogli", "lat": 44.3490, "lon": 9.1510, "amp_zone": "Zona C (max 7 kt)"},
    "punta_chiappa": {"id": "punta_chiappa", "name": "Punta Chiappa (AMP Zona B)", "lat": 44.3215, "lon": 9.1455, "amp_zone": "Zona B (max 5 kt)"},
    "san_fruttuoso": {"id": "san_fruttuoso", "name": "Baia di San Fruttuoso (AMP Zona B)", "lat": 44.3150, "lon": 9.1750, "amp_zone": "Zona B (max 5 kt)"},
    "faro_portofino": {"id": "faro_portofino", "name": "Punta del Capo / Faro di Portofino", "lat": 44.2985, "lon": 9.2185, "amp_zone": "Zona B (max 5 kt)"},
    "portofino": {"id": "portofino", "name": "Baia e Porto di Portofino", "lat": 44.3030, "lon": 9.2110, "amp_zone": "Zona C (max 7 kt)"},
    "paraggi": {"id": "paraggi", "name": "Baia di Paraggi (AMP Zona C)", "lat": 44.3105, "lon": 9.2125, "amp_zone": "Zona C (max 7 kt)"},
    "santa_margherita": {"id": "santa_margherita", "name": "Porto di Santa Margherita Ligure", "lat": 44.3295, "lon": 9.2165, "amp_zone": "Zona C (max 7 kt)"},
    "rapallo": {"id": "rapallo", "name": "Rada di Rapallo", "lat": 44.3450, "lon": 9.2340, "amp_zone": None},
    "zoagli": {"id": "zoagli", "name": "Scogliera di Zoagli", "lat": 44.3335, "lon": 9.2660, "amp_zone": None},
    "chiavari_lavagna": {"id": "chiavari_lavagna", "name": "Marina di Chiavari & Lavagna", "lat": 44.3100, "lon": 9.3300, "amp_zone": None},
    "sestri_levante": {"id": "sestri_levante", "name": "Sestri Levante (Baia del Silenzio)", "lat": 44.2690, "lon": 9.3910, "amp_zone": None},
}

# Archi del grafo costiero: (nodo_A, nodo_B, max_speed_cap_knots_or_None)
# Impedisce di tagliare via terra il Promontorio di Portofino o i capi costieri
COASTAL_GRAPH_EDGES: list[tuple[str, str, float | None]] = [
    ("arenzano", "voltri_pra", None),
    ("voltri_pra", "genova_porto", None),
    ("genova_porto", "boccadasse", None),
    ("boccadasse", "nervi", None),
    ("nervi", "recco_sori", None),
    ("recco_sori", "camogli", None),
    ("camogli", "punta_chiappa", 7.0),
    ("punta_chiappa", "san_fruttuoso", 5.0),
    ("san_fruttuoso", "faro_portofino", 5.0),
    ("faro_portofino", "portofino", 5.0),
    ("portofino", "paraggi", 7.0),
    ("paraggi", "santa_margherita", 7.0),
    ("santa_margherita", "rapallo", None),
    ("rapallo", "zoagli", None),
    ("zoagli", "chiavari_lavagna", None),
    ("chiavari_lavagna", "sestri_levante", None),
    # Rotta diretta al largo tra Faro Portofino e Chiavari/Sestri senza entrare a Rapallo
    ("faro_portofino", "zoagli", None),
    ("faro_portofino", "chiavari_lavagna", None),
    # Rotta esterna Golfo Paradiso -> Punta Chiappa
    ("nervi", "punta_chiappa", None),
]


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcola la distanza geodetica in Miglia Nautiche (NM, R = 3440.065 NM)."""
    r_nm = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r_nm * math.asin(math.sqrt(a)), 2)


def find_shortest_coastal_path(origin_id: str, dest_id: str) -> dict[str, Any]:
    """Trova il percorso nautico costiero più breve tra `origin_id` e `dest_id` con Dijkstra."""
    if origin_id not in COASTAL_WAYPOINTS or dest_id not in COASTAL_WAYPOINTS:
        raise ValueError(f"Waypoint non valido: {origin_id} -> {dest_id}")

    adj: dict[str, list[tuple[str, float, float | None]]] = {k: [] for k in COASTAL_WAYPOINTS}
    for u, v, speed_cap in COASTAL_GRAPH_EDGES:
        w1, w2 = COASTAL_WAYPOINTS[u], COASTAL_WAYPOINTS[v]
        dist_nm = max(0.25, haversine_nm(w1["lat"], w1["lon"], w2["lat"], w2["lon"]))
        adj[u].append((v, dist_nm, speed_cap))
        adj[v].append((u, dist_nm, speed_cap))

    dist_map: dict[str, float] = {k: float("inf") for k in COASTAL_WAYPOINTS}
    prev_map: dict[str, tuple[str | None, float, float | None]] = {
        k: (None, 0.0, None) for k in COASTAL_WAYPOINTS
    }
    dist_map[origin_id] = 0.0
    pq: list[tuple[float, str]] = [(0.0, origin_id)]

    while pq:
        d_curr, u = heapq.heappop(pq)
        if u == dest_id:
            break
        if d_curr > dist_map[u]:
            continue
        for v, edge_nm, cap in adj[u]:
            nd = d_curr + edge_nm
            if nd < dist_map[v]:
                dist_map[v] = nd
                prev_map[v] = (u, edge_nm, cap)
                heapq.heappush(pq, (nd, v))

    # Ricostruzione segmenti
    nodes: list[str] = []
    curr: str | None = dest_id
    while curr is not None:
        nodes.append(curr)
        curr = prev_map[curr][0]
    nodes.reverse()

    legs: list[dict[str, Any]] = []
    for i in range(len(nodes) - 1):
        u, v = nodes[i], nodes[i + 1]
        _, leg_nm, cap = prev_map[v]
        legs.append(
            {
                "from_id": u,
                "from_name": COASTAL_WAYPOINTS[u]["name"],
                "to_id": v,
                "to_name": COASTAL_WAYPOINTS[v]["name"],
                "distance_nm": round(leg_nm, 2),
                "amp_speed_limit_knots": cap,
            }
        )

    return {
        "waypoints": [COASTAL_WAYPOINTS[n] for n in nodes],
        "legs": legs,
        "one_way_nm": round(dist_map[dest_id], 2),
    }


def compute_coastal_route_eta(
    origin_id: str = "portofino",
    dest_id: str = "san_fruttuoso",
    cruise_speed_knots: float = 6.0,
    duration_minutes: int = 90,
    stop_minutes: int = 20,
    round_trip: bool = True,
    hourly_forecast: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calcola il piano di navigazione completo (ETA, nodi richiesti, Turnaround Time e confronto fisico Andata/Ritorno)."""
    path = find_shortest_coastal_path(origin_id, dest_id)
    one_way_nm = path["one_way_nm"]
    total_nm = round(one_way_nm * (2.0 if round_trip else 1.0), 2)

    eff_cruise = max(1.0, float(cruise_speed_knots))

    # Calcolo tempo reale di navigazione tenendo conto dei cap di velocità AMP su ciascun segmento
    one_way_nav_min = 0.0
    for leg in path["legs"]:
        cap = leg["amp_speed_limit_knots"]
        leg_speed = min(eff_cruise, cap) if cap is not None else eff_cruise
        one_way_nav_min += (leg["distance_nm"] / max(1.0, leg_speed)) * 60.0

    total_nav_min = round(one_way_nav_min * (2.0 if round_trip else 1.0), 1)
    available_nav_min = max(1.0, float(duration_minutes - stop_minutes))
    required_avg_knots = round(total_nm / (available_nav_min / 60.0), 1)

    now_dt = datetime.now()
    eta_dest_dt = now_dt + timedelta(minutes=one_way_nav_min)
    turnaround_dt = now_dt + timedelta(minutes=max(0.0, duration_minutes - one_way_nav_min))
    return_port_dt = now_dt + timedelta(minutes=total_nav_min + stop_minutes)

    # Confronto fisico oggettivo Andata vs Ritorno (ORO-4 da supermeteo)
    outbound_Conditions = None
    inbound_conditions = None
    return_delta_note = "Condizioni stazionarie tra andata e rientro."
    if hourly_forecast and len(hourly_forecast) >= 2:
        h_out = hourly_forecast[0]
        idx_in = min(len(hourly_forecast) - 1, max(1, int(round(duration_minutes / 60.0))))
        h_in = hourly_forecast[idx_in]
        outbound_Conditions = {
            "time": h_out["time"],
            "wind_knots": h_out["wind_knots"],
            "gust_knots": h_out["gust_knots"],
            "wind_cardinal": h_out["wind_cardinal"],
            "wave_hs_m": h_out["wave_hs_m"],
            "wave_period_s": h_out["wave_period_s"],
        }
        inbound_conditions = {
            "time": h_in["time"],
            "wind_knots": h_in["wind_knots"],
            "gust_knots": h_in["gust_knots"],
            "wind_cardinal": h_in["wind_cardinal"],
            "wave_hs_m": h_in["wave_hs_m"],
            "wave_period_s": h_in["wave_period_s"],
        }
        d_wave = round(h_in["wave_hs_m"] - h_out["wave_hs_m"], 2)
        d_wind = round(h_in["wind_knots"] - h_out["wind_knots"], 1)
        return_delta_note = (
            f"Variazione fisica prevista al rientro ({h_in['time'][-5:]}): "
            f"ΔVento {d_wind:+.1f} kt, ΔOnda Hs {d_wave:+.2f} m."
        )

    return {
        "origin": COASTAL_WAYPOINTS[origin_id],
        "destination": COASTAL_WAYPOINTS[dest_id],
        "round_trip": round_trip,
        "waypoints": path["waypoints"],
        "legs": path["legs"],
        "one_way_distance_nm": one_way_nm,
        "total_distance_nm": total_nm,
        "selected_cruise_knots": eff_cruise,
        "planned_duration_minutes": duration_minutes,
        "planned_stop_minutes": stop_minutes,
        "estimated_navigation_minutes": total_nav_min,
        "estimated_total_minutes": round(total_nav_min + stop_minutes, 1),
        "required_average_speed_knots": required_avg_knots,
        "schedule": {
            "departure_time": now_dt.strftime("%H:%M"),
            "eta_destination": eta_dest_dt.strftime("%H:%M"),
            "latest_turnaround_time": turnaround_dt.strftime("%H:%M"),
            "eta_return_origin": return_port_dt.strftime("%H:%M"),
        },
        "physical_comparison_outbound_vs_inbound": {
            "outbound": outbound_Conditions,
            "inbound": inbound_conditions,
            "delta_summary": return_delta_note,
        },
    }
