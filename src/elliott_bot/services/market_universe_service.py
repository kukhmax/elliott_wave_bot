"""Service responsible for market-universe loading and pair selection."""

from __future__ import annotations

from elliott_bot.domain.models import MarketDataError, ServiceEvent
from elliott_bot.integrations.coinmarketcap_provider import CoinMarketCapProvider
from elliott_bot.storage.file_storage import FileStorage

from elliott_bot.services.symbol_mapping_service import SymbolMappingService


class MarketUniverseService:
    """Load top assets and map them into tradable exchange symbols."""

    def __init__(
        self,
        provider: CoinMarketCapProvider,
        symbol_mapping_service: SymbolMappingService,
        storage: FileStorage,
    ) -> None:
        self._provider = provider
        self._symbol_mapping_service = symbol_mapping_service
        self._storage = storage

    async def load_watchlist_candidates(
        self,
        available_symbols: set[str],
        *,
        target_count: int | None = None,
    ) -> tuple[list[str], list[str], MarketDataError | None]:
        """Load top assets and convert them into exchange-ready trading symbols."""

        requested_count = target_count or 20
        fetch_limit = max(requested_count * 3, requested_count)
        assets, error = await self._provider.fetch_top_assets(limit=fetch_limit)
        if error is not None:
            return [], [], error

        matched_symbols, unmatched_assets = self._symbol_mapping_service.map_assets_to_symbols(assets, available_symbols)
        matched_symbols = matched_symbols[:requested_count]
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="market_universe_loaded",
                message="Market universe loaded and mapped to exchange symbols.",
                context={
                    "matched_symbols": len(matched_symbols),
                    "unmatched_assets": len(unmatched_assets),
                },
            )
        )
        return matched_symbols, unmatched_assets, None
