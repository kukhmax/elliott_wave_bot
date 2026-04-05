"""Service responsible for exchange symbol discovery and OHLCV retrieval."""

from __future__ import annotations

from elliott_bot.domain.models import MarketDataError, MarketSeries, ServiceEvent
from elliott_bot.integrations.binance_provider import BinanceMarketDataProvider
from elliott_bot.storage.file_storage import FileStorage


class MarketDataService:
    """Coordinate market-data retrieval for the first exchange provider."""

    def __init__(self, provider: BinanceMarketDataProvider, storage: FileStorage) -> None:
        self._provider = provider
        self._storage = storage

    async def load_available_symbols(self) -> tuple[set[str], MarketDataError | None]:
        """Load tradable exchange symbols from the market-data provider."""

        symbols, error = await self._provider.fetch_available_symbols()
        if error is None:
            self._storage.append_event(
                ServiceEvent(
                    level="INFO",
                    module=self.__class__.__name__,
                    event_type="available_symbols_loaded",
                    message="Exchange symbols loaded from the market-data provider.",
                    context={"symbols_count": len(symbols)},
                )
            )
        return symbols, error

    async def load_market_series(self, symbol: str, timeframe: str, limit: int) -> tuple[MarketSeries | None, MarketDataError | None]:
        """Load normalized OHLCV candles for a symbol and timeframe."""

        series, error = await self._provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        if error is None and series is not None:
            self._storage.append_event(
                ServiceEvent(
                    level="INFO",
                    module=self.__class__.__name__,
                    event_type="market_series_loaded",
                    message="Normalized OHLCV series loaded for analysis.",
                    context={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bars_count": len(series.bars),
                    },
                )
            )
        return series, error
