"""Tests for persisted state services introduced in the second implementation step."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.domain.models import (
    PairSourceOrigin,
    SignalRecord,
    SignalStatus,
    WatchlistState,
)
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.watchlist_service import WatchlistService
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


def build_settings(storage_path: Path) -> AppSettings:
    """Create a deterministic settings object for tests."""

    return AppSettings(
        TELEGRAM_BOT_TOKEN="test-token",
        MARKET_UNIVERSE_PROVIDER="coinmarketcap",
        MARKET_DATA_PROVIDER="binance",
        EXCHANGE="binance_spot",
        DEFAULT_TIMEFRAME="5m",
        SCAN_INTERVAL_SECONDS=300,
        DEFAULT_HISTORY_DEPTH=150,
        MAX_AUTO_PAIRS=20,
        SEARCH_MODE="standard",
        EXTREMUM_SENSITIVITY="standard",
        NOTIFICATIONS_ENABLED=True,
        MANUAL_CHECK_EXPLAIN_REJECTIONS=True,
        STORAGE_PATH=str(storage_path),
        LOG_LEVEL="INFO",
    )


def test_settings_service_roundtrip(tmp_path: Path) -> None:
    """Settings service should persist and restore application settings."""

    storage = FileStorage(tmp_path)
    service = SettingsService(storage)
    settings = build_settings(tmp_path)

    service.save(settings)
    restored = service.load(settings)

    assert restored.default_timeframe == "5m"
    assert restored.exchange == "binance_spot"


def test_watchlist_service_roundtrip(tmp_path: Path) -> None:
    """Watchlist service should persist pairs together with monitoring config."""

    storage = FileStorage(tmp_path)
    service = WatchlistService(storage)
    settings = build_settings(tmp_path)
    state = WatchlistState()

    updated = service.ensure_pair(
        state=state,
        settings=settings,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        source_origin=PairSourceOrigin.MANUAL,
    )
    service.save(updated)
    restored = service.load()

    assert len(restored.pairs) == 1
    assert restored.pairs[0].symbol == "BTCUSDT"
    assert restored.configs[0].timeframe == "5m"


def test_signal_history_service_roundtrip(tmp_path: Path) -> None:
    """Signal history service should persist stored signal records."""

    storage = FileStorage(tmp_path)
    service = SignalHistoryService(storage)
    records = [
        SignalRecord(
            signal_id="signal-1",
            signal_signature="btcusdt-5m-long",
            symbol="BTCUSDT",
            timeframe="5m",
            direction="long",
            status=SignalStatus.CONFIRMED,
            sent_to_telegram=True,
        )
    ]

    service.save(records)
    restored = service.load()

    assert len(restored) == 1
    assert restored[0].signal_signature == "btcusdt-5m-long"
    assert restored[0].status == SignalStatus.CONFIRMED
