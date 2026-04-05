"""Tests for Fibonacci and proportion validation of wave candidates."""

from __future__ import annotations

from elliott_bot.domain.models import ExtremumKind, ExtremumPoint, WaveCandidate, WaveDirection, WavePointSet
from elliott_bot.services.elliott_validation_service import ElliottValidationService


def build_candidate() -> WaveCandidate:
    """Create a deterministic wave candidate with solid Fibonacci-like proportions."""

    points = [
        ExtremumPoint(index=0, timestamp=1, price=100.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=0),
        ExtremumPoint(index=1, timestamp=2, price=120.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=2, timestamp=3, price=108.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=3, timestamp=4, price=140.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=4, timestamp=5, price=130.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=5, timestamp=6, price=152.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
    ]
    return WaveCandidate(
        candidate_id="BTCUSDT-5m-0-1-2-3-4-5",
        symbol="BTCUSDT",
        timeframe="5m",
        direction=WaveDirection.LONG,
        points=WavePointSet(
            p0=points[0],
            p1=points[1],
            p2=points[2],
            p3=points[3],
            p4=points[4],
            p5=points[5],
            direction=WaveDirection.LONG,
        ),
        length_wave1=20.0,
        length_wave2=12.0,
        length_wave3=32.0,
        length_wave4=10.0,
        length_wave5=22.0,
        source_extremums=points,
        structural_notes=["direction=long", "early_structure_passed"],
    )


def test_elliott_validation_service_returns_confirmed_or_probable() -> None:
    """Validation service should produce a confident result for a well-proportioned candidate."""

    service = ElliottValidationService()
    result = service.validate(build_candidate())

    assert result.status.value in {"confirmed", "probable"}
    assert result.confidence_score >= 7
    assert "wave3_extension" in result.strong_matches or "wave3_extension" in result.acceptable_matches
