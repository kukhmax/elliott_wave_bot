"""Service responsible for tracked pairs and pair monitoring configuration."""

from __future__ import annotations

from elliott_bot.domain.models import (
    PairMonitoringConfig,
    PairSourceOrigin,
    PairStatus,
    ServiceEvent,
    TradingPair,
    WatchlistState,
)
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


class WatchlistService:
    """Manage tracked trading pairs and their monitoring settings."""

    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    def load(self) -> WatchlistState:
        """Load the full watchlist state from persistent storage."""

        payload = self._storage.read_json(self._storage.watchlist_path, WatchlistState().to_dict())
        state = WatchlistState.from_dict(payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="watchlist_loaded",
                message="Watchlist state loaded from persistent storage.",
                context={
                    "pairs_count": len(state.pairs),
                    "configs_count": len(state.configs),
                },
            )
        )
        return state

    def save(self, state: WatchlistState) -> None:
        """Persist the full watchlist state."""

        self._storage.write_json(self._storage.watchlist_path, state.to_dict())
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="watchlist_saved",
                message="Watchlist state saved to persistent storage.",
                context={
                    "pairs_count": len(state.pairs),
                    "configs_count": len(state.configs),
                },
            )
        )

    def ensure_pair(
        self,
        state: WatchlistState,
        settings: AppSettings,
        symbol: str,
        base_asset: str,
        quote_asset: str,
        source_origin: PairSourceOrigin = PairSourceOrigin.MANUAL,
        timeframe: str | None = None,
    ) -> WatchlistState:
        """Insert or update a trading pair together with its monitoring config."""

        pair = TradingPair(
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            exchange=settings.exchange,
            status=PairStatus.ACTIVE,
            source_origin=source_origin,
        )
        config = PairMonitoringConfig(
            symbol=symbol,
            timeframe=timeframe or settings.default_timeframe,
            history_depth=settings.default_history_depth,
        )

        state.pairs = [existing for existing in state.pairs if existing.symbol != symbol]
        state.configs = [existing for existing in state.configs if existing.symbol != symbol]
        state.pairs.append(pair)
        state.configs.append(config)

        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="watchlist_pair_upserted",
                message="Trading pair added or updated in the watchlist.",
                context={
                    "symbol": symbol,
                    "timeframe": config.timeframe,
                    "source_origin": source_origin.value,
                },
            )
        )
        return state
