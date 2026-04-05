"""Tests for the early wave-analysis pipeline and manual checks."""

from __future__ import annotations

import asyncio
from pathlib import Path

from elliott_bot.domain.models import MarketSeries, OHLCVBar
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.manual_check_service import ManualCheckService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.shared.config import AppSettings


def build_settings(storage_path: Path) -> AppSettings:
    """Create deterministic settings for analysis tests."""

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


def build_wave_like_series() -> MarketSeries:
    """Build a synthetic series that contains a clear long wave candidate."""

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
    return MarketSeries(symbol="BTCUSDT", timeframe="5m", bars=bars, source="synthetic")


class FakeMarketDataService:
    """Provide a deterministic market series for manual check tests."""

    def __init__(self, series: MarketSeries) -> None:
        self._series = series

    async def load_market_series(self, symbol: str, timeframe: str, limit: int):
        """Return the preset market series regardless of requested params."""

        return self._series, None


def test_wave_analysis_pipeline_builds_long_candidate() -> None:
    """Prepared series and extremums should produce at least one valid candidate."""

    series = build_wave_like_series()
    preparation_service = SeriesPreparationService()
    extremum_detection_service = ExtremumDetectionService()
    wave_analysis_service = WaveAnalysisService()

    prepared, error = preparation_service.prepare(series)
    assert error is None
    assert prepared is not None

    extremums = extremum_detection_service.detect(prepared, sensitivity="aggressive")
    result = wave_analysis_service.analyze(prepared, extremums)

    assert result.has_candidates is True
    assert result.candidates[0].direction.value == "long"
    assert result.candidates[0].points.p5.price > result.candidates[0].points.p3.price


def test_manual_check_service_returns_probable_result(tmp_path: Path) -> None:
    """Manual check service should return a probable result for a valid synthetic structure."""

    series = build_wave_like_series()
    service = ManualCheckService(
        settings=build_settings(tmp_path),
        market_data_service=FakeMarketDataService(series),
        series_preparation_service=SeriesPreparationService(),
        extremum_detection_service=ExtremumDetectionService(),
        wave_analysis_service=WaveAnalysisService(),
        elliott_validation_service=ElliottValidationService(),
    )

    result = asyncio.run(service.run(symbol="BTCUSDT", timeframe="5m"))

    assert result.status in {"confirmed", "probable"}
    assert result.best_candidate is not None
    assert result.analysis_result is not None
    assert result.validation_result is not None
