"""Service responsible for runtime state persistence and lifecycle events."""

from __future__ import annotations

from elliott_bot.domain.models import MonitoringStatus, RuntimeState, ServiceEvent
from elliott_bot.storage.file_storage import FileStorage


class RuntimeStateService:
    """Manage the persistent runtime state of the bot."""

    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    def load(self) -> RuntimeState:
        """Load the previously persisted runtime state."""

        payload = self._storage.read_json(
            file_path=self._storage.runtime_state_path,
            default=RuntimeState.default().to_dict(),
        )
        state = RuntimeState.from_dict(payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="runtime_state_loaded",
                message="Runtime state loaded from persistent storage.",
                context={"monitoring_status": state.monitoring_status.value},
            )
        )
        return state

    def save(self, state: RuntimeState) -> None:
        """Persist the current runtime state."""

        self._storage.write_json(self._storage.runtime_state_path, state.to_dict())
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="runtime_state_saved",
                message="Runtime state saved to persistent storage.",
                context={"monitoring_status": state.monitoring_status.value},
            )
        )

    def mark_running(self, state: RuntimeState) -> RuntimeState:
        """Return a state instance updated to the running status."""

        state.monitoring_status = MonitoringStatus.RUNNING
        state.last_error = None
        return state

    def mark_stopped(self, state: RuntimeState) -> RuntimeState:
        """Return a state instance updated to the stopped status."""

        state.monitoring_status = MonitoringStatus.STOPPED
        state.current_cycle_started_at = None
        state.current_pair = None
        state.queue_size = 0
        return state
