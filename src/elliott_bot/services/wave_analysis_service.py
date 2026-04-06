"""Early Elliott-wave candidate construction and structural filtering."""

from __future__ import annotations

from elliott_bot.domain.models import (
    ExtremumKind,
    ExtremumPoint,
    MarketSeries,
    WaveAnalysisResult,
    WaveCandidate,
    WaveDirection,
    WavePointSet,
)
from elliott_bot.shared.logging import get_logger


class WaveAnalysisService:
    """Build candidate Elliott structures from cleaned market extremums."""

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def analyze(self, series: MarketSeries, extremums: list[ExtremumPoint]) -> WaveAnalysisResult:
        """Build early wave candidates and collect rejected windows diagnostics."""

        candidates: list[WaveCandidate] = []
        rejected_windows: list[dict] = []

        if len(extremums) < 6:
            return WaveAnalysisResult(
                symbol=series.symbol,
                timeframe=series.timeframe,
                candidates=[],
                rejected_windows=[{"reason": "not_enough_extremums", "extremums_count": len(extremums)}],
                extremums=extremums,
                analyzed_bars=len(series.bars),
            )

        for offset in range(len(extremums) - 5):
            window = extremums[offset : offset + 6]
            candidate, reason = self._build_candidate(series, window)
            if candidate is not None:
                candidates.append(candidate)
            else:
                rejected_windows.append(
                    {
                        "offset": offset,
                        "reason": reason,
                        "extremum_indexes": [point.index for point in window],
                    }
                )

        unique_candidates = self._deduplicate_candidates(candidates)
        self._logger.info(
            "Built %s valid candidates and rejected %s windows for %s %s.",
            len(unique_candidates),
            len(rejected_windows),
            series.symbol,
            series.timeframe,
        )
        return WaveAnalysisResult(
            symbol=series.symbol,
            timeframe=series.timeframe,
            candidates=unique_candidates[:3],
            rejected_windows=rejected_windows,
            extremums=extremums,
            analyzed_bars=len(series.bars),
        )

    def _build_candidate(
        self,
        series: MarketSeries,
        window: list[ExtremumPoint],
    ) -> tuple[WaveCandidate | None, str]:
        """Create a candidate from a six-extremum window or return a rejection reason."""

        kinds = [point.kind for point in window]
        direction: WaveDirection | None = None

        if kinds == [
            ExtremumKind.LOW,
            ExtremumKind.HIGH,
            ExtremumKind.LOW,
            ExtremumKind.HIGH,
            ExtremumKind.LOW,
            ExtremumKind.HIGH,
        ]:
            direction = WaveDirection.LONG
        elif kinds == [
            ExtremumKind.HIGH,
            ExtremumKind.LOW,
            ExtremumKind.HIGH,
            ExtremumKind.LOW,
            ExtremumKind.HIGH,
            ExtremumKind.LOW,
        ]:
            direction = WaveDirection.SHORT

        if direction is None:
            return None, "invalid_wave_direction"

        if any(window[index + 1].index - window[index].index < 1 for index in range(5)):
            return None, "too_small_structure"

        p0, p1, p2, p3, p4, p5 = window
        
        if len(series.bars) - p5.index > 20:
            return None, "structure_too_old"

        if direction == WaveDirection.LONG:
            if not (p1.price > p0.price and p2.price < p1.price and p2.price > p0.price):
                return None, "wave2_breaks_wave1_origin"
            if not (p3.price > p1.price):
                return None, "wave3_no_breakout"
            if not (p4.price < p3.price):
                return None, "invalid_wave_direction"
            if not (p5.price > p3.price):
                return None, "wave5_no_breakout"
            if not (p4.price > p1.price):
                return None, "wave4_overlap_wave1"
        else:
            if not (p1.price < p0.price and p2.price > p1.price and p2.price < p0.price):
                return None, "wave2_breaks_wave1_origin"
            if not (p3.price < p1.price):
                return None, "wave3_no_breakout"
            if not (p4.price > p3.price):
                return None, "invalid_wave_direction"
            if not (p5.price < p3.price):
                return None, "wave5_no_breakout"
            if not (p4.price < p1.price):
                return None, "wave4_overlap_wave1"

        length_wave1 = abs(p1.price - p0.price)
        length_wave2 = abs(p2.price - p1.price)
        length_wave3 = abs(p3.price - p2.price)
        length_wave4 = abs(p4.price - p3.price)
        length_wave5 = abs(p5.price - p4.price)
        if length_wave3 <= min(length_wave1, length_wave5):
            return None, "wave3_shortest"

        points = WavePointSet(p0=p0, p1=p1, p2=p2, p3=p3, p4=p4, p5=p5, direction=direction)
        candidate = WaveCandidate(
            candidate_id=self._build_candidate_id(series.symbol, series.timeframe, window),
            symbol=series.symbol,
            timeframe=series.timeframe,
            direction=direction,
            points=points,
            length_wave1=length_wave1,
            length_wave2=length_wave2,
            length_wave3=length_wave3,
            length_wave4=length_wave4,
            length_wave5=length_wave5,
            source_extremums=window,
            structural_notes=self._build_notes(direction),
        )
        return candidate, ""

    @staticmethod
    def _build_candidate_id(symbol: str, timeframe: str, window: list[ExtremumPoint]) -> str:
        """Build a deterministic candidate identifier from pivot indexes."""

        indexes = "-".join(str(point.index) for point in window)
        return f"{symbol}-{timeframe}-{indexes}"

    @staticmethod
    def _build_notes(direction: WaveDirection) -> list[str]:
        """Return a baseline set of notes for early structural candidates."""

        return [
            f"direction={direction.value}",
            "early_structure_passed",
            "ready_for_fibonacci_validation",
        ]

    @staticmethod
    def _deduplicate_candidates(candidates: list[WaveCandidate]) -> list[WaveCandidate]:
        """Drop duplicate candidates based on the deterministic candidate id."""

        unique: dict[str, WaveCandidate] = {}
        for candidate in candidates:
            unique[candidate.candidate_id] = candidate
        return list(unique.values())
