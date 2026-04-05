"""Application context shared between Telegram handlers and core services."""

from __future__ import annotations

from dataclasses import dataclass

from elliott_bot.domain.models import PairSourceOrigin, PairStatus, RuntimeState, SignalRecord, SignalStatus, WatchlistState
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.chart_rendering_service import ChartRenderingService
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.manual_check_service import ManualCheckService
from elliott_bot.services.market_data_service import MarketDataService
from elliott_bot.services.market_universe_service import MarketUniverseService
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.notification_message_service import NotificationMessageService
from elliott_bot.services.symbol_mapping_service import SymbolMappingService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.services.watchlist_service import WatchlistService
from elliott_bot.shared.config import AppSettings


@dataclass(slots=True)
class ApplicationContext:
    """Bundle mutable application state together with the services that manage it."""

    settings: AppSettings
    runtime_state: RuntimeState
    watchlist_state: WatchlistState
    signal_history: list[SignalRecord]
    settings_service: SettingsService
    runtime_state_service: RuntimeStateService
    watchlist_service: WatchlistService
    signal_history_service: SignalHistoryService
    monitoring_coordinator: MonitoringCoordinator
    symbol_mapping_service: SymbolMappingService
    market_universe_service: MarketUniverseService
    market_data_service: MarketDataService
    series_preparation_service: SeriesPreparationService
    extremum_detection_service: ExtremumDetectionService
    wave_analysis_service: WaveAnalysisService
    elliott_validation_service: ElliottValidationService
    manual_check_service: ManualCheckService
    chart_rendering_service: ChartRenderingService
    notification_message_service: NotificationMessageService

    @property
    def active_pairs_count(self) -> int:
        """Return the number of active tracked pairs."""

        return len([pair for pair in self.watchlist_state.pairs if pair.status == PairStatus.ACTIVE])

    def start_monitoring(self) -> RuntimeState:
        """Move monitoring into the running state and persist it."""

        self.runtime_state = self.monitoring_coordinator.start(self.runtime_state)
        return self.runtime_state

    def stop_monitoring(self) -> RuntimeState:
        """Move monitoring into the stopped state and persist it."""

        self.runtime_state = self.monitoring_coordinator.stop(self.runtime_state)
        return self.runtime_state

    def persist_watchlist(self) -> None:
        """Persist the current in-memory watchlist state."""

        self.watchlist_service.save(self.watchlist_state)

    def persist_settings(self) -> None:
        """Persist the current in-memory settings snapshot."""

        self.settings_service.save(self.settings)

    def persist_signal_history(self) -> None:
        """Persist the current in-memory signal history."""

        self.signal_history_service.save(self.signal_history)

    def record_signal_decision(
        self,
        *,
        signal_signature: str,
        symbol: str,
        timeframe: str,
        direction: str,
        status: SignalStatus,
        sent_to_telegram: bool,
        duplicate_of: str | None = None,
        suppressed_reason: str | None = None,
    ) -> None:
        """Append and persist a new signal-history decision record."""

        self.signal_history = self.signal_history_service.register_decision(
            self.signal_history,
            signal_signature=signal_signature,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            status=status,
            sent_to_telegram=sent_to_telegram,
            duplicate_of=duplicate_of,
            suppressed_reason=suppressed_reason,
        )
        self.persist_signal_history()

    def update_setting(self, field_name: str, value: object) -> None:
        """Validate, apply and persist a settings update."""

        self.settings = self.settings_service.update(self.settings, field_name, value)

    async def ensure_auto_watchlist(self) -> dict[str, object]:
        """Populate the automatic watchlist from CMC and exchange symbols if needed."""

        target_auto_pairs = self.settings.max_auto_pairs
        active_auto_symbols = {
            pair.symbol
            for pair in self.watchlist_state.pairs
            if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
        }
        if len(active_auto_symbols) >= target_auto_pairs:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": None,
            }

        available_symbols, symbols_error = await self.market_data_service.load_available_symbols()
        if symbols_error is not None:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": symbols_error.message,
            }

        matched_symbols, unmatched_assets, universe_error = await self.market_universe_service.load_watchlist_candidates(
            available_symbols,
            target_count=target_auto_pairs,
        )
        if universe_error is not None:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": universe_error.message,
            }

        existing_active_symbols = {
            pair.symbol
            for pair in self.watchlist_state.pairs
            if pair.status == PairStatus.ACTIVE
        }
        added_count = 0
        for symbol in matched_symbols:
            current_auto_count = len(
                [
                    pair
                    for pair in self.watchlist_state.pairs
                    if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
                ]
            )
            if current_auto_count >= target_auto_pairs:
                break
            if symbol in existing_active_symbols:
                continue

            quote_asset = self.settings.default_quote_asset
            base_asset = symbol[: -len(quote_asset)] if symbol.endswith(quote_asset) else symbol
            self.watchlist_state = self.watchlist_service.ensure_pair(
                state=self.watchlist_state,
                settings=self.settings,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                source_origin=PairSourceOrigin.AUTO,
            )
            existing_active_symbols.add(symbol)
            added_count += 1

        if added_count > 0:
            self.persist_watchlist()

        active_auto_count = len(
            [
                pair
                for pair in self.watchlist_state.pairs
                if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
            ]
        )
        return {
            "added_count": added_count,
            "active_auto_pairs": active_auto_count,
            "active_total_pairs": self.active_pairs_count,
            "unmatched_assets": len(unmatched_assets),
            "error_message": None,
        }
