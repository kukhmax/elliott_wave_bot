"""Application entry point and bootstrap sequence."""

from __future__ import annotations

import sys

from elliott_bot.interfaces.telegram.bot_runtime import TelegramBotRuntime
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.shared.config import get_settings
from elliott_bot.shared.logging import configure_logging, get_logger
from elliott_bot.storage.file_storage import FileStorage


def main() -> None:
    """Start the application bootstrap process."""

    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("elliott_bot.app")

    logger.info("Starting Elliott Bot bootstrap sequence.")
    logger.info(
        "Application configuration loaded. exchange=%s default_timeframe=%s storage_path=%s",
        settings.exchange,
        settings.default_timeframe,
        settings.resolved_storage_path(),
    )

    storage = FileStorage(settings.resolved_storage_path())
    runtime_state_service = RuntimeStateService(storage)
    coordinator = MonitoringCoordinator(runtime_state_service, storage)
    state = coordinator.bootstrap_state()

    telegram_runtime = TelegramBotRuntime(settings.telegram_bot_token)
    bot = telegram_runtime.create_bot()

    logger.info(
        "Bootstrap completed. monitoring_status=%s telegram_configured=%s",
        state.monitoring_status.value,
        bot is not None,
    )
    logger.info("Initial application scaffold is ready for the next implementation step.")

    if not telegram_runtime.configured:
        logger.warning("Telegram bot token is not configured. Exiting after bootstrap.")
        return

    logger.info("Telegram runtime is configured. Polling is not implemented in the current step yet.")
    sys.exit(0)
