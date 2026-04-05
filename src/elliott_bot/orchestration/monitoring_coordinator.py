"""Monitoring orchestration primitives for the first implementation step."""

from __future__ import annotations

from datetime import datetime, timezone

from elliott_bot.domain.models import RuntimeState, ServiceEvent
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.shared.logging import get_logger
from elliott_bot.storage.file_storage import FileStorage


class MonitoringCoordinator:
    """Own the high-level monitoring lifecycle of the bot."""

    def __init__(self, runtime_state_service: RuntimeStateService, storage: FileStorage) -> None:
        self._runtime_state_service = runtime_state_service
        self._storage = storage
        self._logger = get_logger(self.__class__.__name__)

    def bootstrap_state(self) -> RuntimeState:
        """Load and return the persisted runtime state."""

        state = self._runtime_state_service.load()
        self._logger.info("Monitoring coordinator bootstrapped with state: %s", state.monitoring_status.value)
        return state

    def start(self, state: RuntimeState) -> RuntimeState:
        """Mark monitoring as running and persist the updated state."""

        state = self._runtime_state_service.mark_running(state)
        state.started_at = datetime.now(timezone.utc).isoformat()
        self._runtime_state_service.save(state)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="monitoring_started",
                message="Monitoring lifecycle moved to the running state.",
                context={"monitoring_status": state.monitoring_status.value},
            )
        )
        self._logger.info("Monitoring started.")
        return state

    def stop(self, state: RuntimeState) -> RuntimeState:
        """Mark monitoring as stopped and persist the updated state."""

        state = self._runtime_state_service.mark_stopped(state)
        self._runtime_state_service.save(state)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="monitoring_stopped",
                message="Monitoring lifecycle moved to the stopped state.",
                context={"monitoring_status": state.monitoring_status.value},
            )
        )
        self._logger.info("Monitoring stopped.")
        return state
