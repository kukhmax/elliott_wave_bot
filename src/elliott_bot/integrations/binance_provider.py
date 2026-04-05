"""Binance Spot provider for symbol discovery and OHLCV loading."""

from __future__ import annotations

from datetime import datetime, timezone

import aiohttp

from elliott_bot.domain.models import MarketDataError, MarketDataErrorCategory, MarketSeries, OHLCVBar
from elliott_bot.shared.config import AppSettings
from elliott_bot.shared.logging import get_logger


class BinanceMarketDataProvider:
    """Load exchange info and OHLCV data from Binance Spot."""

    EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
    KLINES_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._logger = get_logger(self.__class__.__name__)

    async def fetch_available_symbols(self) -> tuple[set[str], MarketDataError | None]:
        """Fetch the currently tradable Binance Spot symbols."""

        try:
            timeout = aiohttp.ClientTimeout(total=self._settings.request_timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.EXCHANGE_INFO_URL) as response:
                    if response.status == 429:
                        return set(), MarketDataError(
                            category=MarketDataErrorCategory.RATE_LIMIT,
                            message="Binance rate limit exceeded while fetching exchange info.",
                            retryable=True,
                            context={"status": response.status},
                        )

                    response.raise_for_status()
                    payload = await response.json()
                    return self.parse_available_symbols(payload), None
        except aiohttp.ClientConnectionError as error:
            self._logger.error("Binance exchange info network error: %s", error)
            return set(), MarketDataError(
                category=MarketDataErrorCategory.NETWORK,
                message="Binance exchange info network error.",
                retryable=True,
                context={"details": str(error)},
            )
        except TimeoutError as error:
            self._logger.error("Binance exchange info timeout: %s", error)
            return set(), MarketDataError(
                category=MarketDataErrorCategory.TIMEOUT,
                message="Binance exchange info request timed out.",
                retryable=True,
                context={"details": str(error)},
            )
        except aiohttp.ClientResponseError as error:
            self._logger.error("Binance exchange info response error: %s", error)
            return set(), MarketDataError(
                category=MarketDataErrorCategory.INVALID_RESPONSE,
                message="Binance exchange info returned an invalid response.",
                retryable=False,
                context={"status": error.status, "message": error.message},
            )

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> tuple[MarketSeries | None, MarketDataError | None]:
        """Fetch Binance klines and normalize them into the internal candle contract."""

        params = {"symbol": symbol, "interval": timeframe, "limit": limit}

        try:
            timeout = aiohttp.ClientTimeout(total=self._settings.request_timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.KLINES_URL, params=params) as response:
                    if response.status == 429:
                        return None, MarketDataError(
                            category=MarketDataErrorCategory.RATE_LIMIT,
                            message="Binance rate limit exceeded while fetching klines.",
                            retryable=True,
                            context={"status": response.status, "symbol": symbol},
                        )

                    if response.status == 400:
                        return None, MarketDataError(
                            category=MarketDataErrorCategory.INVALID_SYMBOL,
                            message="Binance rejected the requested trading pair or timeframe.",
                            retryable=False,
                            context={"status": response.status, "symbol": symbol, "timeframe": timeframe},
                        )

                    response.raise_for_status()
                    payload = await response.json()
                    if not payload:
                        return None, MarketDataError(
                            category=MarketDataErrorCategory.EMPTY_RESPONSE,
                            message="Binance returned an empty candle payload.",
                            retryable=False,
                            context={"symbol": symbol, "timeframe": timeframe},
                        )

                    return self.normalize_klines(symbol=symbol, timeframe=timeframe, payload=payload), None
        except aiohttp.ClientConnectionError as error:
            self._logger.error("Binance klines network error: %s", error)
            return None, MarketDataError(
                category=MarketDataErrorCategory.NETWORK,
                message="Binance klines network error.",
                retryable=True,
                context={"details": str(error), "symbol": symbol},
            )
        except TimeoutError as error:
            self._logger.error("Binance klines timeout: %s", error)
            return None, MarketDataError(
                category=MarketDataErrorCategory.TIMEOUT,
                message="Binance klines request timed out.",
                retryable=True,
                context={"details": str(error), "symbol": symbol},
            )
        except (ValueError, TypeError) as error:
            self._logger.error("Binance normalization error: %s", error)
            return None, MarketDataError(
                category=MarketDataErrorCategory.INVALID_RESPONSE,
                message="Binance klines payload could not be normalized.",
                retryable=False,
                context={"details": str(error), "symbol": symbol, "timeframe": timeframe},
            )

    def parse_available_symbols(self, payload: dict) -> set[str]:
        """Extract active symbol names from Binance exchange info payload."""

        symbols: set[str] = set()
        for item in payload.get("symbols", []):
            symbol = str(item.get("symbol", "")).upper().strip()
            if symbol and item.get("status") == "TRADING":
                symbols.add(symbol)

        self._logger.info("Parsed %s tradable Binance symbols.", len(symbols))
        return symbols

    def normalize_klines(self, symbol: str, timeframe: str, payload: list[list]) -> MarketSeries:
        """Convert raw Binance klines into the normalized internal candle series."""

        bars = [
            OHLCVBar(
                open_time=int(item[0]),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
                close_time=int(item[6]),
                symbol=symbol,
                timeframe=timeframe,
            )
            for item in payload
        ]
        bars.sort(key=lambda bar: bar.open_time)

        series = MarketSeries(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            loaded_at=datetime.now(timezone.utc).isoformat(),
            source="binance_spot",
        )
        self._logger.info(
            "Normalized %s candles for %s on timeframe %s.",
            len(series.bars),
            symbol,
            timeframe,
        )
        return series
