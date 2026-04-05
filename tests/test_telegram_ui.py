"""Tests for Telegram UI helpers and application context behavior."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.domain.models import MonitoringStatus, PairSourceOrigin, RuntimeState, WatchlistState
from elliott_bot.integrations.binance_provider import BinanceMarketDataProvider
from elliott_bot.integrations.coinmarketcap_provider import CoinMarketCapProvider
from elliott_bot.interfaces.telegram.keyboards import build_main_menu_keyboard, build_timeframe_keyboard
from elliott_bot.interfaces.telegram.presenters import (
    format_status_text,
    format_watchlist_text,
    is_supported_timeframe,
    normalize_symbol,
    normalize_timeframe,
)
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
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.symbol_mapping_service import SymbolMappingService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.services.watchlist_service import WatchlistService
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


def build_context(tmp_path: Path) -> ApplicationContext:
    """Create a deterministic application context for UI-related tests."""

    settings = AppSettings(
        TELEGRAM_BOT_TOKEN="",
        MARKET_UNIVERSE_PROVIDER="coinmarketcap",
        MARKET_DATA_PROVIDER="binance",
        EXCHANGE="binance_spot",
        DEFAULT_TIMEFRAME="5m",
        SCAN_INTERVAL_SECONDS=300,
        DEFAULT_HISTORY_DEPTH=150,
        MAX_AUTO_PAIRS=20,
        SEARCH_MODE="standard",
        EXTREMUM_SENSITIVITY="standard",
        CMC_API_KEY="test-key",
        DEFAULT_QUOTE_ASSET="USDT",
        REQUEST_TIMEOUT_SECONDS=10,
        RETRY_COUNT=2,
        RATE_LIMIT_DELAY_MS=250,
        NOTIFICATIONS_ENABLED=True,
        MANUAL_CHECK_EXPLAIN_REJECTIONS=True,
        STORAGE_PATH=str(tmp_path),
        LOG_LEVEL="INFO",
    )
    storage = FileStorage(tmp_path)
    runtime_state_service = RuntimeStateService(storage)
    watchlist_service = WatchlistService(storage)
    signal_history_service = SignalHistoryService(storage)
    settings_service = SettingsService(storage)
    symbol_mapping_service = SymbolMappingService(settings, storage)
    market_universe_service = MarketUniverseService(
        CoinMarketCapProvider(settings),
        symbol_mapping_service,
        storage,
    )
    market_data_service = MarketDataService(BinanceMarketDataProvider(settings), storage)
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

    return ApplicationContext(
        settings=settings,
        runtime_state=RuntimeState.default(),
        watchlist_state=WatchlistState(),
        signal_history=[],
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


def test_main_menu_keyboard_switches_between_start_and_stop() -> None:
    """Main menu keyboard should reflect the monitoring status."""

    stopped_keyboard = build_main_menu_keyboard(monitoring_running=False)
    running_keyboard = build_main_menu_keyboard(monitoring_running=True)

    assert stopped_keyboard.keyboard[0][0].text == "Старт"
    assert running_keyboard.keyboard[0][0].text == "Стоп"


def test_timeframe_keyboard_contains_default_shortcut() -> None:
    """Timeframe keyboard should expose the default-timeframe shortcut."""

    keyboard = build_timeframe_keyboard()
    assert keyboard.keyboard[0][0].text == "1m"
    assert keyboard.keyboard[2][0].text == "Использовать 5m"


def test_presenters_and_normalizers_work_for_basic_inputs(tmp_path: Path) -> None:
    """Telegram presenters should produce user-friendly outputs."""

    context = build_context(tmp_path)
    context.watchlist_state = context.watchlist_service.ensure_pair(
        state=context.watchlist_state,
        settings=context.settings,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        source_origin=PairSourceOrigin.MANUAL,
    )

    assert normalize_symbol("btc/usdt") == "BTCUSDT"
    assert normalize_timeframe("Использовать 5m", "5m") == "5m"
    assert is_supported_timeframe("15m") is True
    assert is_supported_timeframe("30m") is False
    assert "BTCUSDT" in format_watchlist_text(context)
    assert "⏱ Дефолтный таймфрейм: 5m" in format_status_text(context)


def test_application_context_can_switch_monitoring_state(tmp_path: Path) -> None:
    """Application context should start and stop monitoring through the coordinator."""

    context = build_context(tmp_path)

    context.start_monitoring()
    assert context.runtime_state.monitoring_status == MonitoringStatus.RUNNING

    context.stop_monitoring()
    assert context.runtime_state.monitoring_status == MonitoringStatus.STOPPED
