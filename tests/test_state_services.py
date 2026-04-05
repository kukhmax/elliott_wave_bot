"""Tests for persisted state services introduced in the second implementation step."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.domain.models import (
    EventCategory,
    MonitoringStatus,
    PairSourceOrigin,
    RuntimeState,
    ServiceEvent,
    SignalRecord,
    SignalStatus,
    WatchlistState,
)
from elliott_bot.services.runtime_state_service import RuntimeStateService
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
        CMC_API_KEY="cmc-test-key",
        DEFAULT_QUOTE_ASSET="USDT",
        REQUEST_TIMEOUT_SECONDS=10,
        RETRY_COUNT=2,
        RATE_LIMIT_DELAY_MS=250,
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
    assert restored.telegram_bot_token == "test-token"
    assert restored.cmc_api_key == "cmc-test-key"

    payload = storage.read_json(storage.settings_path, {})

    assert "telegram_bot_token" not in payload
    assert "cmc_api_key" not in payload


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


def test_signal_history_service_can_detect_duplicates(tmp_path: Path) -> None:
    """Signal history service should detect duplicate signal signatures."""

    storage = FileStorage(tmp_path)
    service = SignalHistoryService(storage)
    records: list[SignalRecord] = []

    records = service.register_decision(
        records,
        signal_signature="BTCUSDT-5m-signal:confirmed",
        symbol="BTCUSDT",
        timeframe="5m",
        direction="long",
        status=SignalStatus.CONFIRMED,
        sent_to_telegram=True,
    )

    duplicate = service.find_duplicate(records, "BTCUSDT-5m-signal:confirmed")

    assert duplicate is not None
    assert duplicate.symbol == "BTCUSDT"


def test_runtime_state_service_recovers_running_state_after_restart(tmp_path: Path) -> None:
    """Runtime state service should reset running state to stopped after restart."""

    storage = FileStorage(tmp_path)
    service = RuntimeStateService(storage)
    storage.write_json(
        storage.runtime_state_path,
        RuntimeState(monitoring_status=MonitoringStatus.RUNNING).to_dict(),
    )

    restored = service.load()

    assert restored.monitoring_status == MonitoringStatus.STOPPED
    assert restored.last_error is not None


def test_file_storage_truncates_event_log_when_limit_is_exceeded(tmp_path: Path) -> None:
    """Event log retention should keep only the bounded number of records."""

    storage = FileStorage(tmp_path)
    storage.MAX_EVENT_LOG_RECORDS = 3

    for index in range(5):
        storage.append_event(
            ServiceEvent(
                level="INFO",
                module="test",
                event_type=f"event_{index}",
                message="test event",
                category=EventCategory.SYSTEM,
            )
        )

    lines = storage.event_log_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 3
