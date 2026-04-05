"""Notification text builders for manual checks and future signal alerts."""

from __future__ import annotations

from elliott_bot.domain.models import ElliottValidationResult, WaveCandidate
from elliott_bot.services.manual_check_service import ManualCheckResult
from elliott_bot.shared.logging import get_logger


class NotificationMessageService:
    """Build concise notification messages for Telegram delivery."""

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def build_manual_check_caption(self, result: ManualCheckResult) -> str:
        """Build a unified caption for manual-check results."""

        if result.best_candidate is None or result.status == "rejected":
            validation_summary = result.validation_result.diagnostic_summary if result.validation_result else result.summary
            caption = (
                f"🔎 {result.symbol} | {result.timeframe}\n"
                f"📉 Статус: {result.status}\n"
                f"⚠️ Структура не подтверждена\n"
                f"🧾 Причина: {result.summary}\n"
                f"🧮 Диагностика: {validation_summary}"
            )
            self._logger.info("Built rejected manual-check caption for %s %s.", result.symbol, result.timeframe)
            return caption

        strong_matches = ", ".join(result.validation_result.strong_matches) if result.validation_result else "нет"
        validation_summary = result.validation_result.diagnostic_summary if result.validation_result else result.summary
        caption = (
            f"🔎 {result.symbol} | {result.timeframe} | {result.best_candidate.direction.value} | {result.status}\n"
            "🌊 Найдена 5-волновая структура после раннего анализа и валидации\n"
            f"✨ Подтверждения: {strong_matches}\n"
            f"🧮 Диагностика: {validation_summary}"
        )
        self._logger.info("Built successful manual-check caption for %s %s.", result.symbol, result.timeframe)
        return caption

    def build_signal_alert_caption(self, candidate: WaveCandidate, validation_result: ElliottValidationResult) -> str:
        """Build a compact automatic-signal caption for future monitoring flows."""

        strong_matches = ", ".join(validation_result.strong_matches) if validation_result.strong_matches else "нет"
        return (
            f"🚨 {candidate.symbol} | {candidate.timeframe} | {candidate.direction.value} | {validation_result.status.value}\n"
            "🌊 Найдена 5-волновая структура\n"
            f"✨ Подтверждения: {strong_matches}\n"
            f"🧮 Диагностика: {validation_result.diagnostic_summary}"
        )

    @staticmethod
    def build_signal_signature(candidate: WaveCandidate, validation_result: ElliottValidationResult) -> str:
        """Build a deterministic signal signature for anti-duplicate checks."""

        return f"{candidate.candidate_id}:{validation_result.status.value}"
