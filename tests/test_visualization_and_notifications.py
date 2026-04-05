"""Tests for chart rendering and notification message formatting."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.domain.models import ExtremumKind, ExtremumPoint, MarketSeries, OHLCVBar, SignalStatus, WaveCandidate, WaveDirection, WavePointSet
from elliott_bot.services.chart_rendering_service import ChartRenderingService
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.manual_check_service import ManualCheckResult
from elliott_bot.services.notification_message_service import NotificationMessageService
from elliott_bot.shared.config import AppSettings


def build_settings(storage_path: Path) -> AppSettings:
    """Create deterministic settings for visualization tests."""

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


def build_series_and_candidate() -> tuple[MarketSeries, WaveCandidate]:
    """Create a deterministic market series and matching wave candidate."""

    closes = [110, 100, 130, 115, 150, 135, 170, 145, 180]
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
    points = [
        ExtremumPoint(index=1, timestamp=2, price=98.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=0),
        ExtremumPoint(index=2, timestamp=3, price=130.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=3, timestamp=4, price=113.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=4, timestamp=5, price=150.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=5, timestamp=6, price=133.0, kind=ExtremumKind.LOW, strength=0.1, bar_distance_from_previous=1),
        ExtremumPoint(index=6, timestamp=7, price=170.0, kind=ExtremumKind.HIGH, strength=0.1, bar_distance_from_previous=1),
    ]
    candidate = WaveCandidate(
        candidate_id="BTCUSDT-5m-1-2-3-4-5-6",
        symbol="BTCUSDT",
        timeframe="5m",
        direction=WaveDirection.LONG,
        points=WavePointSet(
            p0=points[0],
            p1=points[1],
            p2=points[2],
            p3=points[3],
            p4=points[4],
            p5=points[5],
            direction=WaveDirection.LONG,
        ),
        length_wave1=32.0,
        length_wave2=17.0,
        length_wave3=37.0,
        length_wave4=17.0,
        length_wave5=37.0,
        source_extremums=points,
        structural_notes=["direction=long", "early_structure_passed"],
    )
    return MarketSeries(symbol="BTCUSDT", timeframe="5m", bars=bars, source="synthetic"), candidate


def test_chart_rendering_service_creates_png(tmp_path: Path) -> None:
    """Chart renderer should create a PNG file for a valid manual-check result."""

    settings = build_settings(tmp_path)
    series, candidate = build_series_and_candidate()
    validation_result = ElliottValidationService().validate(candidate)
    result = ManualCheckResult(
        symbol="BTCUSDT",
        timeframe="5m",
        status=validation_result.status.value,
        summary="Найдена структура после базовой фильтрации и валидации пропорций.",
        best_candidate=candidate,
        validation_result=validation_result,
        market_series=series,
    )

    file_path = ChartRenderingService(settings).render_manual_check_chart(result)

    assert file_path is not None
    assert file_path.exists()
    assert file_path.suffix == ".png"


def test_chart_rendering_service_creates_png_for_rejected_manual_check(tmp_path: Path) -> None:
    """Chart renderer should still create a PNG for rejected manual checks when series exists."""

    settings = build_settings(tmp_path)
    series, _ = build_series_and_candidate()
    result = ManualCheckResult(
        symbol="BTCUSDT",
        timeframe="1m",
        status=SignalStatus.REJECTED.value,
        summary="Не найдено валидных структур.",
        market_series=series,
    )

    file_path = ChartRenderingService(settings).render_manual_check_chart(result)

    assert file_path is not None
    assert file_path.exists()
    assert "1m" in file_path.name


def test_notification_message_service_builds_manual_check_caption() -> None:
    """Notification message service should create a compact manual-check caption."""

    _, candidate = build_series_and_candidate()
    validation_result = ElliottValidationService().validate(candidate)
    service = NotificationMessageService()
    result = ManualCheckResult(
        symbol="BTCUSDT",
        timeframe="5m",
        status=SignalStatus.CONFIRMED.value,
        summary="Найдена структура после базовой фильтрации и валидации пропорций.",
        best_candidate=candidate,
        validation_result=validation_result,
    )

    caption = service.build_manual_check_caption(result)
    signature = service.build_signal_signature(candidate, validation_result)

    assert "BTCUSDT | 5m" in caption
    assert "🌊 Найдена 5-волновая структура" in caption
    assert "🧮 Диагностика:" in caption
    assert signature.endswith(validation_result.status.value)
