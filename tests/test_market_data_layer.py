"""Tests for the market data layer services and provider normalization."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.integrations.binance_provider import BinanceMarketDataProvider
from elliott_bot.integrations.coinmarketcap_provider import CoinMarketCapProvider
from elliott_bot.services.market_universe_service import MarketUniverseService
from elliott_bot.services.symbol_mapping_service import SymbolMappingService
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


def build_settings(storage_path: Path) -> AppSettings:
    """Create deterministic settings for market-data tests."""

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


def test_symbol_mapping_service_filters_stablecoins_and_maps_symbols(tmp_path: Path) -> None:
    """Mapping service should remove stablecoins and build USDT pairs."""

    settings = build_settings(tmp_path)
    storage = FileStorage(tmp_path)
    service = SymbolMappingService(settings, storage)

    matched, unmatched = service.map_assets_to_symbols(
        assets=["BTC", "USDT", "ETH", "BTC", "TON"],
        available_symbols={"BTCUSDT", "ETHUSDT"},
    )

    assert matched == ["BTCUSDT", "ETHUSDT"]
    assert unmatched == ["TON"]


def test_coinmarketcap_provider_parses_top_assets(tmp_path: Path) -> None:
    """CoinMarketCap provider should extract canonical symbols from payloads."""

    provider = CoinMarketCapProvider(build_settings(tmp_path))
    payload = {
        "data": [
            {"symbol": "btc"},
            {"symbol": "eth"},
            {"symbol": "sol"},
        ]
    }

    assert provider.parse_top_assets(payload, 2) == ["BTC", "ETH"]


def test_binance_provider_normalizes_exchange_info_and_klines(tmp_path: Path) -> None:
    """Binance provider should normalize exchange info and candles."""

    provider = BinanceMarketDataProvider(build_settings(tmp_path))
    exchange_info = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "status": "TRADING"},
            {"symbol": "TESTUSDT", "status": "BREAK"},
        ]
    }
    klines = [
        [1, "100.0", "110.0", "90.0", "105.0", "1000.0", 2],
        [3, "105.0", "115.0", "95.0", "112.0", "900.0", 4],
    ]

    assert provider.parse_available_symbols(exchange_info) == {"BTCUSDT", "ETHUSDT"}

    series = provider.normalize_klines(symbol="BTCUSDT", timeframe="5m", payload=klines)
    assert series.symbol == "BTCUSDT"
    assert series.timeframe == "5m"
    assert len(series.bars) == 2
    assert series.bars[0].open == 100.0
    assert series.bars[1].close == 112.0


def test_market_universe_service_maps_assets_with_available_symbols(tmp_path: Path) -> None:
    """Market-universe service should combine provider parsing and symbol mapping."""

    settings = build_settings(tmp_path)
    storage = FileStorage(tmp_path)
    mapping_service = SymbolMappingService(settings, storage)
    service = MarketUniverseService(CoinMarketCapProvider(settings), mapping_service, storage)

    matched, unmatched = mapping_service.map_assets_to_symbols(
        assets=["BTC", "ETH", "USDC", "TON"],
        available_symbols={"BTCUSDT", "TONUSDT"},
    )

    assert matched == ["BTCUSDT", "TONUSDT"]
    assert unmatched == ["ETH"]
    assert service is not None
