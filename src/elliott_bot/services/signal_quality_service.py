"""Signal-quality evaluation helpers for historical regression cases."""

from __future__ import annotations

from dataclasses import dataclass

from elliott_bot.domain.models import SignalStatus


@dataclass(slots=True)
class SignalQualityCaseResult:
    """Represents the quality outcome for a single historical case."""

    case_name: str
    expected_statuses: set[SignalStatus]
    actual_status: SignalStatus
    passed: bool
    issue_type: str


class SignalQualityService:
    """Classify analytical outcomes and summarize regression-quality metrics."""

    def evaluate_case(
        self,
        *,
        case_name: str,
        expected_statuses: set[SignalStatus],
        actual_status: SignalStatus,
    ) -> SignalQualityCaseResult:
        """Evaluate a single historical case against expected statuses."""

        if actual_status in expected_statuses:
            return SignalQualityCaseResult(
                case_name=case_name,
                expected_statuses=expected_statuses,
                actual_status=actual_status,
                passed=True,
                issue_type="matched",
            )

        if actual_status == SignalStatus.REJECTED and expected_statuses & {SignalStatus.CONFIRMED, SignalStatus.PROBABLE}:
            issue_type = "false_negative"
        elif actual_status in {SignalStatus.CONFIRMED, SignalStatus.PROBABLE} and expected_statuses == {SignalStatus.REJECTED}:
            issue_type = "false_positive"
        elif actual_status == SignalStatus.CONFIRMED and expected_statuses == {SignalStatus.PROBABLE}:
            issue_type = "weak_confirmation"
        else:
            issue_type = "status_mismatch"

        return SignalQualityCaseResult(
            case_name=case_name,
            expected_statuses=expected_statuses,
            actual_status=actual_status,
            passed=False,
            issue_type=issue_type,
        )

    def summarize(self, results: list[SignalQualityCaseResult]) -> dict[str, int]:
        """Build a compact regression summary for a batch of historical cases."""

        summary = {
            "total_cases": len(results),
            "passed_cases": sum(1 for result in results if result.passed),
            "false_positive": 0,
            "false_negative": 0,
            "weak_confirmation": 0,
            "status_mismatch": 0,
        }
        for result in results:
            if result.issue_type in summary:
                summary[result.issue_type] += 1
        return summary
