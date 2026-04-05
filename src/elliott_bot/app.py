"""Application entry point and bootstrap sequence."""

from __future__ import annotations

import asyncio

from elliott_bot.domain.models import EventCategory, ServiceEvent
from elliott_bot.integrations.binance_provider import BinanceMarketDataProvider
from elliott_bot.integrations.coinmarketcap_provider import CoinMarketCapProvider
from elliott_bot.interfaces.telegram.bot_runtime import TelegramBotRuntime
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.application_context import ApplicationContext
from elliott_bot.services.chart_rendering_service import ChartRenderingService
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.manual_check_service import ManualCheckService
from elliott_bot.services.market_data_service import MarketDataService
from elliott_bot.services.market_universe_service import MarketUniverseService
from elliott_bot.services.notification_message_service import NotificationMessageService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.symbol_mapping_service import SymbolMappingService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
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
    symbol_mapping_service = SymbolMappingService(settings, storage)
    market_universe_provider = CoinMarketCapProvider(settings)
    market_data_provider = BinanceMarketDataProvider(settings)
    market_universe_service = MarketUniverseService(market_universe_provider, symbol_mapping_service, storage)
    market_data_service = MarketDataService(market_data_provider, storage)
    series_preparation_service = SeriesPreparationService()
    extremum_detection_service = ExtremumDetectionService()
    wave_analysis_service = WaveAnalysisService()
    elliott_validation_service = ElliottValidationService()
    chart_rendering_service = ChartRenderingService(settings)
    notification_message_service = NotificationMessageService()
    manual_check_service = ManualCheckService(
        settings=settings,
        market_data_service=market_data_service,
        series_preparation_service=series_preparation_service,
        extremum_detection_service=extremum_detection_service,
        wave_analysis_service=wave_analysis_service,
        elliott_validation_service=elliott_validation_service,
    )
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
        storage=storage,
        settings_service=settings_service,
        runtime_state_service=runtime_state_service,
        watchlist_service=watchlist_service,
        signal_history_service=signal_history_service,
        monitoring_coordinator=coordinator,
        symbol_mapping_service=symbol_mapping_service,
        market_universe_service=market_universe_service,
        market_data_service=market_data_service,
        series_preparation_service=series_preparation_service,
        extremum_detection_service=extremum_detection_service,
        wave_analysis_service=wave_analysis_service,
        elliott_validation_service=elliott_validation_service,
        manual_check_service=manual_check_service,
        chart_rendering_service=chart_rendering_service,
        notification_message_service=notification_message_service,
    )

    telegram_runtime = TelegramBotRuntime(settings.telegram_bot_token)
    bot = telegram_runtime.create_bot()
    app_context.attach_bot(bot)

    logger.info(
        "Bootstrap completed. monitoring_status=%s telegram_configured=%s watchlist_pairs=%s signal_history=%s market_universe_provider=%s market_data_provider=%s",
        state.monitoring_status.value,
        bot is not None,
        len(watchlist_state.pairs),
        len(signal_history),
        settings.market_universe_provider,
        settings.market_data_provider,
    )
    logger.info("Persistent state services, validation pipeline and visualization layer are ready.")
    storage.append_event(
        ServiceEvent(
            level="INFO",
            module="elliott_bot.app",
            event_type="application_started",
            message="Application startup sequence completed.",
            category=EventCategory.SYSTEM,
            context={"telegram_configured": bot is not None},
        )
    )

    if not telegram_runtime.configured:
        logger.warning("Telegram bot token is not configured. Exiting after bootstrap.")
        storage.append_event(
            ServiceEvent(
                level="INFO",
                module="elliott_bot.app",
                event_type="application_stopped",
                message="Application stopped after bootstrap because Telegram token is not configured.",
                category=EventCategory.SYSTEM,
                reason_code="telegram_not_configured",
            )
        )
        return

    dispatcher = telegram_runtime.create_dispatcher(app_context)
    logger.info("Telegram runtime is configured. Starting polling.")
    try:
        await dispatcher.start_polling(bot)
    except Exception as error:
        app_context.runtime_state.last_error = str(error)
        app_context.runtime_state = app_context.runtime_state_service.mark_stopped(app_context.runtime_state)
        app_context.runtime_state_service.save(app_context.runtime_state)
        storage.append_event(
            ServiceEvent(
                level="CRITICAL",
                module="elliott_bot.app",
                event_type="application_crashed",
                message="Application polling loop crashed.",
                category=EventCategory.SYSTEM,
                reason_code="polling_crash",
                context={"details": str(error)},
            )
        )
        raise
    finally:
        await app_context.shutdown()
        app_context.runtime_state = app_context.runtime_state_service.mark_stopped(app_context.runtime_state)
        app_context.runtime_state_service.save(app_context.runtime_state)
        storage.append_event(
            ServiceEvent(
                level="INFO",
                module="elliott_bot.app",
                event_type="application_stopped",
                message="Application stopped and runtime state persisted.",
                category=EventCategory.SYSTEM,
            )
        )
