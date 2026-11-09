"""Test suite per TASK-AI-01 (ADR-0004): AI Meteo & Marine Advisor e Fallback Sinottico Ligure."""

from __future__ import annotations

import pytest
from backend.districts import get_district
from backend.engine.ai_advisor import (
    build_deterministic_synoptic_bulletin,
    generate_ai_bulletin,
)
from backend.engine.ensemble import (
    build_complete_weather_package,
    build_synthetic_fallback_dataset,
)


@pytest.mark.asyncio
async def test_ai_advisor_deterministic_fallback_completeness() -> None:
    """Verifica che il bollettino sia generato in modo ricco e completo anche senza GEMINI_API_KEY."""
    district = get_district("GE-CENTRO-PONENTE")
    assert district is not None
    raw = build_synthetic_fallback_dataset(district)
    pkg = build_complete_weather_package(district, raw)

    bulletin = await generate_ai_bulletin(pkg, mode="both")
    assert bulletin["district_id"] == "GE-CENTRO-PONENTE"
    assert len(bulletin["headline"]) > 20
    assert len(bulletin["synoptic_nowcast_analysis"]) > 30
    assert "Stato Bacini" in bulletin["land_operational_briefing"]
    assert "Moto Ondoso" in bulletin["sea_operational_briefing"]
    assert len(bulletin["key_takeaways"]) == 3
