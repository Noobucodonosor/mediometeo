"""Sicurezza, Geofencing Dominio Ligure, Resilienza & Disclaimer Incolumità (ADR-0002)."""

from __future__ import annotations

from typing import Any
from fastapi import HTTPException
from backend.config import get_settings


SAFETY_DISCLAIMER_LAND = (
    "AVVISO DI SICUREZZA (TERRA): MedioMeteo Genova elabora modelli LAM ad alta risoluzione "
    "(AROME 1.3km, ICON-D2 2km, ECMWF) e dati radar a scopo informativo e di supporto decisionale. "
    "Per le allerte ufficiali di Protezione Civile nella Provincia di Genova fare SEMPRE riferimento "
    "al portale ufficiale ARPAL / Regione Liguria (allertaliguria.regione.liguria.it) e al Numero Unico di Emergenza 112."
)

SAFETY_DISCLAIMER_SEA = (
    "AVVISO DI SICUREZZA NAUTICA (MARE): I dati di vento, raffica e moto ondoso non sostituiscono "
    "i Bollettini Ufficiali METEOMAR, gli Avvisi ai Naviganti della Capitaneria di Porto di Genova "
    "e le valutazioni strumentali del Comandante di bordo. Emergenza in Mare Guardia Costiera: 1530 "
    "(VHF Canale 16)."
)


def validate_ligurian_coordinates(lat: float, lon: float) -> tuple[float, float]:
    """Verifica che le coordinate cadano nel dominio geografico Ligure / Alto Tirreno (ADR-0002)."""
    settings = get_settings()
    if not (settings.min_lat <= lat <= settings.max_lat) or not (
        settings.min_lon <= lon <= settings.max_lon
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Coordinate ({lat:.4f}, {lon:.4f}) fuori dal dominio operativo di MedioMeteo Genova/Liguria "
                f"(Lat: {settings.min_lat}..{settings.max_lat}, Lon: {settings.min_lon}..{settings.max_lon})."
            ),
        )
    return round(float(lat), 4), round(float(lon), 4)


def sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Rimuove qualsiasi potenziale riferimento a chiavi o token dai dizionari di metadati."""
    forbidden_substrings = ("key", "token", "secret", "password", "authorization")
    cleaned: dict[str, Any] = {}
    for k, v in meta.items():
        if any(sub in k.lower() for sub in forbidden_substrings):
            continue
        cleaned[k] = v
    return cleaned
