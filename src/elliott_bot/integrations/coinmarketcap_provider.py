"""CoinMarketCap market-universe provider for top-asset discovery."""

from __future__ import annotations

import aiohttp

from elliott_bot.domain.models import MarketDataError, MarketDataErrorCategory
from elliott_bot.shared.config import AppSettings
from elliott_bot.shared.logging import get_logger


class CoinMarketCapProvider:
    """Load top crypto assets from CoinMarketCap and normalize them into symbols."""

    BASE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._logger = get_logger(self.__class__.__name__)

    async def fetch_top_assets(self, limit: int | None = None) -> tuple[list[str], MarketDataError | None]:
        """Fetch top assets and return their canonical symbols."""

        if not self._settings.cmc_api_key:
            return [], MarketDataError(
                category=MarketDataErrorCategory.INVALID_RESPONSE,
                message="CoinMarketCap API key is not configured.",
                retryable=False,
                context={"provider": "coinmarketcap"},
            )

        params = {"limit": limit or self._settings.max_auto_pairs, "convert": "USD"}
        headers = {"X-CMC_PRO_API_KEY": self._settings.cmc_api_key}

        try:
            timeout = aiohttp.ClientTimeout(total=self._settings.request_timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.BASE_URL, params=params, headers=headers) as response:
                    if response.status == 429:
                        return [], MarketDataError(
                            category=MarketDataErrorCategory.RATE_LIMIT,
                            message="CoinMarketCap rate limit exceeded.",
                            retryable=True,
                            context={"status": response.status},
                        )

                    response.raise_for_status()
                    payload = await response.json()
                    symbols = self.parse_top_assets(payload, params["limit"])
                    return symbols, None
        except aiohttp.ClientConnectionError as error:
            self._logger.error("CoinMarketCap network error: %s", error)
            return [], MarketDataError(
                category=MarketDataErrorCategory.NETWORK,
                message="CoinMarketCap network error.",
                retryable=True,
                context={"details": str(error)},
            )
        except TimeoutError as error:
            self._logger.error("CoinMarketCap timeout: %s", error)
            return [], MarketDataError(
                category=MarketDataErrorCategory.TIMEOUT,
                message="CoinMarketCap request timed out.",
                retryable=True,
                context={"details": str(error)},
            )
        except aiohttp.ClientResponseError as error:
            self._logger.error("CoinMarketCap response error: %s", error)
            return [], MarketDataError(
                category=MarketDataErrorCategory.INVALID_RESPONSE,
                message="CoinMarketCap returned an invalid response.",
                retryable=False,
                context={"status": error.status, "message": error.message},
            )

    def parse_top_assets(self, payload: dict, limit: int) -> list[str]:
        """Parse CoinMarketCap response payload into canonical asset symbols."""

        assets = payload.get("data", [])
        symbols: list[str] = []
        for item in assets[:limit]:
            symbol = str(item.get("symbol", "")).upper().strip()
            if symbol:
                symbols.append(symbol)

        self._logger.info("Parsed %s top assets from CoinMarketCap payload.", len(symbols))
        return symbols
