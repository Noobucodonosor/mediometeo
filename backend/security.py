"""Sicurezza, Geofencing Dominio Ligure, Resilienza & Disclaimer Incolumità (ADR-0002)."""

from __future__ import annotations

from collections import defaultdict, deque
import time
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


class SlidingWindowRateLimiter:
    """Rate limiter in-memory a finestra scorrevole per protezione quote API e anti-abuso (ADR-0011)."""

    def __init__(self, max_requests: int = 15, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Troppe richieste ravvicinate. Riprova tra qualche secondo.",
            )
        bucket.append(now)

    def reset(self) -> None:
        self._hits.clear()


class CircuitBreaker:
    """Circuit Breaker per connettori meteo esterni (N=3 fallimenti -> cooldown T=5 min, ADR-0002)."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 300.0) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: dict[str, int] = defaultdict(int)
        self._open_until: dict[str, float] = {}

    def is_open(self, source: str) -> bool:
        until = self._open_until.get(source, 0.0)
        if until <= 0.0:
            return False
        if time.monotonic() >= until:
            # Half-open: consente un nuovo tentativo dopo il cooldown
            self._open_until.pop(source, None)
            self._failures[source] = 0
            return False
        return True

    def record_success(self, source: str) -> None:
        self._failures[source] = 0
        self._open_until.pop(source, None)

    def record_failure(self, source: str) -> None:
        self._failures[source] += 1
        if self._failures[source] >= self.failure_threshold:
            self._open_until[source] = time.monotonic() + self.cooldown_seconds

    def reset(self) -> None:
        self._failures.clear()
        self._open_until.clear()
