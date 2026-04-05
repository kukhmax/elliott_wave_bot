"""Application context shared between Telegram handlers and core services."""

from __future__ import annotations

from dataclasses import dataclass

from elliott_bot.domain.models import PairStatus, RuntimeState, SignalRecord, WatchlistState
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
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

    def persist_signal_history(self) -> None:
        """Persist the current in-memory signal history."""

        self.signal_history_service.save(self.signal_history)
