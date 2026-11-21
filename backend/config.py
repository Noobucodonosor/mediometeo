"""Configurazione centralizzata e sicura per MedioMeteo Genova (ADR-0001, ADR-0002)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Impostazioni applicative caricate da variabili d'ambiente (.env)."""

    app_name: str = "MedioMeteo Genova — Terra & Mare"
    version: str = "4.0.0"
    db_path: str = os.getenv(
        "MEDIOMETEO_DB_PATH", str(BASE_DIR / "data" / "mediometeo.sqlite")
    )
    nowcast_ttl_seconds: int = int(os.getenv("NOWCAST_TTL_SECONDS", "180"))
    forecast_ttl_seconds: int = int(os.getenv("FORECAST_TTL_SECONDS", "1800"))
    ai_bulletin_ttl_seconds: int = int(os.getenv("AI_BULLETIN_TTL_SECONDS", "900"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "6.0"))

    # API Keys (mai esposte nei payload di risposta)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    tomorrow_api_key: str = os.getenv("TOMORROW_API_KEY", "").strip()
    weatherapi_key: str = os.getenv("WEATHERAPI_KEY", "").strip()
    stormglass_api_key: str = os.getenv("STORMGLASS_API_KEY", "").strip()
    windy_api_key: str = os.getenv("WINDY_API_KEY", "").strip()
    cors_allow_origins: str = os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).strip()
    trust_proxy_headers: bool = (
        os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() in {"1", "true", "yes"}
    )

    def cors_origins_list(self) -> list[str]:
        """Restituisce la lista delle origini CORS consentite."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    # Dominio Geografico Liguria / Golfo di Genova (ADR-0002 Geofencing)
    min_lat: float = 43.50
    max_lat: float = 45.00
    min_lon: float = 7.50
    max_lon: float = 10.20

    def configured_commercial_providers(self) -> list[str]:
        """Restituisce i nomi dei provider commerciali configurati (senza mai esporre le chiavi)."""
        providers: list[str] = []
        if self.tomorrow_api_key:
            providers.append("tomorrow_io")
        if self.weatherapi_key:
            providers.append("weatherapi")
        if self.stormglass_api_key:
            providers.append("stormglass_marine")
        if self.windy_api_key:
            providers.append("windy")
        return providers


def get_settings() -> Settings:
    """Restituisce un'istanza aggiornata di Settings."""
    return Settings(
        db_path=os.getenv(
            "MEDIOMETEO_DB_PATH", str(BASE_DIR / "data" / "mediometeo.sqlite")
        ),
        nowcast_ttl_seconds=int(os.getenv("NOWCAST_TTL_SECONDS", "180")),
        forecast_ttl_seconds=int(os.getenv("FORECAST_TTL_SECONDS", "1800")),
        ai_bulletin_ttl_seconds=int(os.getenv("AI_BULLETIN_TTL_SECONDS", "900")),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "6.0")),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        tomorrow_api_key=os.getenv("TOMORROW_API_KEY", "").strip(),
        weatherapi_key=os.getenv("WEATHERAPI_KEY", "").strip(),
        stormglass_api_key=os.getenv("STORMGLASS_API_KEY", "").strip(),
        windy_api_key=os.getenv("WINDY_API_KEY", "").strip(),
        cors_allow_origins=os.getenv(
            "CORS_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        ).strip(),
    )
