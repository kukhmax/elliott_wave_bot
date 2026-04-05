"""Fibonacci and proportion validation for early Elliott wave candidates."""

from __future__ import annotations

from math import isclose

from elliott_bot.domain.models import ElliottValidationResult, SignalStatus, WaveCandidate
from elliott_bot.shared.logging import get_logger


class ElliottValidationService:
    """Validate early wave candidates using Fibonacci and proportion heuristics."""

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def validate(self, candidate: WaveCandidate) -> ElliottValidationResult:
        """Validate a wave candidate and assign its current confidence status."""

        ratio2 = self._safe_divide(candidate.length_wave2, candidate.length_wave1)
        ratio3 = self._safe_divide(candidate.length_wave3, candidate.length_wave1)
        ratio4 = self._safe_divide(candidate.length_wave4, candidate.length_wave3)
        ratio5 = self._safe_divide(candidate.length_wave5, candidate.length_wave1)

        strong_matches: list[str] = []
        acceptable_matches: list[str] = []
        weak_matches: list[str] = []
        downgrade_reasons: list[str] = []
        score = 0.0

        score += self._apply_match(
            label="wave2_fibonacci",
            match=self._classify_ratio(ratio2, strong=(0.5, 0.618), acceptable=(0.382, 0.786), weak=(0.236, 0.886)),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="wave2_ratio_out_of_range",
        )
        score += self._apply_match(
            label="wave3_extension",
            match=self._classify_ratio(ratio3, strong=(1.5, 1.75), acceptable=(1.0, 2.618), weak=(0.85, 3.0)),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="wave3_extension_too_weak",
        )
        score += self._apply_match(
            label="wave4_correction",
            match=self._classify_ratio(ratio4, strong=(0.236, 0.382), acceptable=(0.146, 0.5), weak=(0.1, 0.618)),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="wave4_ratio_out_of_range",
        )
        score += self._apply_match(
            label="wave5_projection",
            match=self._classify_wave5(ratio5),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="wave5_ratio_unconvincing",
        )
        score += self._apply_match(
            label="alternation",
            match=self._classify_alternation(ratio2, ratio4),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="alternation_missing",
        )
        score += self._apply_match(
            label="geometry",
            match=self._classify_geometry(candidate),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            downgrade_reason="geometry_inconsistent",
        )

        status = self._pick_status(
            score=score,
            strong_count=len(strong_matches),
            acceptable_count=len(acceptable_matches),
            downgrade_count=len(downgrade_reasons),
        )
        if status == SignalStatus.REJECTED and "too_many_weak_matches" not in downgrade_reasons:
            downgrade_reasons.append("too_many_weak_matches")

        diagnostic_summary = self._build_summary(
            status=status,
            score=score,
            strong_count=len(strong_matches),
            acceptable_count=len(acceptable_matches),
            weak_count=len(weak_matches),
        )
        result = ElliottValidationResult(
            candidate_id=candidate.candidate_id,
            status=status,
            confidence_score=round(score, 3),
            strong_matches=strong_matches,
            acceptable_matches=acceptable_matches,
            weak_matches=weak_matches,
            downgrade_reasons=downgrade_reasons,
            diagnostic_summary=diagnostic_summary,
            ratios={
                "wave2_to_wave1": round(ratio2, 4),
                "wave3_to_wave1": round(ratio3, 4),
                "wave4_to_wave3": round(ratio4, 4),
                "wave5_to_wave1": round(ratio5, 4),
            },
        )
        self._logger.info(
            "Validated candidate %s with status %s and score %.3f.",
            candidate.candidate_id,
            result.status.value,
            result.confidence_score,
        )
        return result

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        """Safely divide wave lengths while avoiding zero-division errors."""

        if denominator == 0:
            return 0.0
        return abs(numerator) / abs(denominator)

    @staticmethod
    def _classify_ratio(value: float, strong: tuple[float, float], acceptable: tuple[float, float], weak: tuple[float, float]) -> str:
        """Classify a ratio according to strong, acceptable and weak zones."""

        if strong[0] <= value <= strong[1]:
            return "strong_match"
        if acceptable[0] <= value <= acceptable[1]:
            return "acceptable_match"
        if weak[0] <= value <= weak[1]:
            return "weak_match"
        return "no_match"

    @staticmethod
    def _classify_wave5(ratio5: float) -> str:
        """Classify wave 5 using wave1 and 0.618 * wave1 projection heuristics."""

        if isclose(ratio5, 1.0, rel_tol=0.12, abs_tol=0.12):
            return "strong_match"
        if isclose(ratio5, 0.618, rel_tol=0.12, abs_tol=0.12):
            return "acceptable_match"
        if 0.382 <= ratio5 <= 1.272:
            return "weak_match"
        return "no_match"

    @staticmethod
    def _classify_alternation(ratio2: float, ratio4: float) -> str:
        """Classify the qualitative alternation between waves 2 and 4."""

        difference = abs(ratio2 - ratio4)
        if difference >= 0.2:
            return "strong_match"
        if difference >= 0.1:
            return "acceptable_match"
        if difference >= 0.05:
            return "weak_match"
        return "no_match"

    @staticmethod
    def _classify_geometry(candidate: WaveCandidate) -> str:
        """Classify the overall geometric consistency of a candidate."""

        if candidate.length_wave3 > candidate.length_wave1 and candidate.length_wave5 > candidate.length_wave2 * 0.7:
            return "strong_match"
        if candidate.length_wave3 >= candidate.length_wave1 and candidate.length_wave5 > 0:
            return "acceptable_match"
        if candidate.length_wave5 > 0 and candidate.length_wave1 > 0:
            return "weak_match"
        return "no_match"

    @staticmethod
    def _apply_match(
        *,
        label: str,
        match: str,
        strong_matches: list[str],
        acceptable_matches: list[str],
        weak_matches: list[str],
        downgrade_reasons: list[str],
        downgrade_reason: str,
    ) -> float:
        """Apply a classified match to the aggregate validation state."""

        if match == "strong_match":
            strong_matches.append(label)
            return 3.0
        if match == "acceptable_match":
            acceptable_matches.append(label)
            return 2.0
        if match == "weak_match":
            weak_matches.append(label)
            return 1.0

        weak_matches.append(label)
        downgrade_reasons.append(downgrade_reason)
        return 0.0

    @staticmethod
    def _pick_status(score: float, strong_count: int, acceptable_count: int, downgrade_count: int) -> SignalStatus:
        """Translate aggregate validation signals into the current status."""

        if downgrade_count == 0 and strong_count >= 2 and score >= 12:
            return SignalStatus.CONFIRMED
        if score >= 7 and downgrade_count <= 2 and (strong_count + acceptable_count) >= 3:
            return SignalStatus.PROBABLE
        return SignalStatus.REJECTED

    @staticmethod
    def _build_summary(status: SignalStatus, score: float, strong_count: int, acceptable_count: int, weak_count: int) -> str:
        """Build a concise validation summary for the user-facing layer."""

        return (
            f"status={status.value}; score={round(score, 3)}; "
            f"strong={strong_count}; acceptable={acceptable_count}; weak={weak_count}"
        )
