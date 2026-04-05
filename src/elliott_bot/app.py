"""Application entry point and bootstrap sequence."""

from __future__ import annotations

import asyncio

from elliott_bot.interfaces.telegram.bot_runtime import TelegramBotRuntime
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.application_context import ApplicationContext
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.watchlist_service import WatchlistService
from elliott_bot.shared.config import get_settings
from elliott_bot.shared.logging import configure_logging, get_logger
from elliott_bot.storage.file_storage import FileStorage


def main() -> None:
    """Start the synchronous application bootstrap wrapper."""

    asyncio.run(run())


async def run() -> None:
    """Start the application bootstrap process and polling when configured."""

    base_settings = get_settings()
    configure_logging(base_settings.log_level)
    logger = get_logger("elliott_bot.app")

    logger.info("Starting Elliott Bot bootstrap sequence.")
    storage = FileStorage(base_settings.resolved_storage_path())
    settings_service = SettingsService(storage)
    settings = settings_service.load(base_settings)
    settings_service.save(settings)

    logger.info(
        "Application configuration loaded. exchange=%s default_timeframe=%s storage_path=%s",
        settings.exchange,
        settings.default_timeframe,
        settings.resolved_storage_path(),
    )

    runtime_state_service = RuntimeStateService(storage)
    watchlist_service = WatchlistService(storage)
    signal_history_service = SignalHistoryService(storage)
    coordinator = MonitoringCoordinator(runtime_state_service, storage)

    state = coordinator.bootstrap_state()
    watchlist_state = watchlist_service.load()
    watchlist_service.save(watchlist_state)
    signal_history = signal_history_service.load()
    signal_history_service.save(signal_history)
    app_context = ApplicationContext(
        settings=settings,
        runtime_state=state,
        watchlist_state=watchlist_state,
        signal_history=signal_history,
        settings_service=settings_service,
        runtime_state_service=runtime_state_service,
        watchlist_service=watchlist_service,
        signal_history_service=signal_history_service,
        monitoring_coordinator=coordinator,
    )

    telegram_runtime = TelegramBotRuntime(settings.telegram_bot_token)
    bot = telegram_runtime.create_bot()

    logger.info(
        "Bootstrap completed. monitoring_status=%s telegram_configured=%s watchlist_pairs=%s signal_history=%s",
        state.monitoring_status.value,
        bot is not None,
        len(watchlist_state.pairs),
        len(signal_history),
    )
    logger.info("Persistent state services are ready for the next implementation step.")

    if not telegram_runtime.configured:
        logger.warning("Telegram bot token is not configured. Exiting after bootstrap.")
        return

    dispatcher = telegram_runtime.create_dispatcher(app_context)
    logger.info("Telegram runtime is configured. Starting polling.")
    await dispatcher.start_polling(bot)
