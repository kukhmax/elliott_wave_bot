"""Service responsible for runtime state persistence and lifecycle events."""

from __future__ import annotations

from elliott_bot.domain.models import EventCategory, MonitoringStatus, RuntimeState, ServiceEvent
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
        if state.monitoring_status in {MonitoringStatus.RUNNING, MonitoringStatus.PAUSED}:
            state = self.mark_stopped(state)
            state.last_error = "Recovered after restart from a non-terminal runtime state."
            self._storage.append_event(
                ServiceEvent(
                    level="WARNING",
                    module=self.__class__.__name__,
                    event_type="runtime_state_recovered_after_restart",
                    message="Runtime state recovered after restart and reset to stopped.",
                    category=EventCategory.SYSTEM,
                    reason_code="restart_recovery",
                    context={"previous_state": payload.get("monitoring_status", "unknown")},
                )
            )
            self.save(state)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="runtime_state_loaded",
                message="Runtime state loaded from persistent storage.",
                category=EventCategory.STORAGE,
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
                category=EventCategory.STORAGE,
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
