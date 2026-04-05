"""Tests for signal-quality evaluation and regression summaries."""

from __future__ import annotations

import asyncio
from pathlib import Path

from elliott_bot.domain.models import MarketSeries, OHLCVBar, SignalStatus
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.manual_check_service import ManualCheckService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.signal_quality_service import SignalQualityService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.shared.config import AppSettings


def build_settings(storage_path: Path) -> AppSettings:
    """Create deterministic settings for quality-regression tests."""

    return AppSettings(
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
        STORAGE_PATH=str(storage_path),
        LOG_LEVEL="INFO",
    )


def build_positive_series() -> MarketSeries:
    """Build a synthetic series with a valid long-wave style structure."""

    closes = [110, 100, 130, 115, 150, 135, 170, 145, 180, 175]
    bars = [
        OHLCVBar(
            open_time=index,
            close_time=index + 1,
            open=float(close_value - 1),
            high=float(close_value),
            low=float(close_value - 2),
            close=float(close_value - 0.5),
            volume=1000.0,
            symbol="BTCUSDT",
            timeframe="5m",
        )
        for index, close_value in enumerate(closes)
    ]
    return MarketSeries(symbol="BTCUSDT", timeframe="5m", bars=bars, source="synthetic_positive")


def build_negative_series() -> MarketSeries:
    """Build a synthetic noisy series that should not pass validation."""

    closes = [100, 102, 101, 103, 102, 101, 102, 101, 100, 101]
    bars = [
        OHLCVBar(
            open_time=index,
            close_time=index + 1,
            open=float(close_value - 0.5),
            high=float(close_value + 0.5),
            low=float(close_value - 1.0),
            close=float(close_value),
            volume=500.0,
            symbol="ETHUSDT",
            timeframe="5m",
        )
        for index, close_value in enumerate(closes)
    ]
    return MarketSeries(symbol="ETHUSDT", timeframe="5m", bars=bars, source="synthetic_negative")


class FakeMarketDataService:
    """Return prebuilt deterministic series for requested symbols."""

    def __init__(self, series_by_symbol: dict[str, MarketSeries]) -> None:
        self._series_by_symbol = series_by_symbol

    async def load_market_series(self, symbol: str, timeframe: str, limit: int):
        """Return the deterministic series for the requested symbol."""

        return self._series_by_symbol[symbol], None


def test_signal_quality_service_summarizes_positive_and_negative_cases(tmp_path: Path) -> None:
    """Signal-quality service should classify regression cases and build metrics."""

    settings = build_settings(tmp_path)
    market_data_service = FakeMarketDataService(
        {
            "BTCUSDT": build_positive_series(),
            "ETHUSDT": build_negative_series(),
        }
    )
    manual_check_service = ManualCheckService(
        settings=settings,
        market_data_service=market_data_service,
        series_preparation_service=SeriesPreparationService(),
        extremum_detection_service=ExtremumDetectionService(),
        wave_analysis_service=WaveAnalysisService(),
        elliott_validation_service=ElliottValidationService(),
    )
    quality_service = SignalQualityService()

    positive_result = asyncio.run(manual_check_service.run(symbol="BTCUSDT", timeframe="5m"))
    negative_result = asyncio.run(manual_check_service.run(symbol="ETHUSDT", timeframe="5m"))

    results = [
        quality_service.evaluate_case(
            case_name="positive_case",
            expected_statuses={SignalStatus.CONFIRMED, SignalStatus.PROBABLE},
            actual_status=SignalStatus(positive_result.status),
        ),
        quality_service.evaluate_case(
            case_name="negative_case",
            expected_statuses={SignalStatus.REJECTED},
            actual_status=SignalStatus(negative_result.status),
        ),
    ]
    summary = quality_service.summarize(results)

    assert summary["total_cases"] == 2
    assert summary["passed_cases"] == 2
    assert summary["false_positive"] == 0
    assert summary["false_negative"] == 0
