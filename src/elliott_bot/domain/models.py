"""Domain models shared across the first implementation step."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MonitoringStatus(StrEnum):
    """Represents the current monitoring lifecycle state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(slots=True)
class RuntimeState:
    """Persistent runtime state stored between restarts."""

    monitoring_status: MonitoringStatus = MonitoringStatus.STOPPED
    started_at: str | None = None
    current_cycle_started_at: str | None = None
    current_pair: str | None = None
    queue_size: int = 0
    last_error: str | None = None

    @classmethod
    def default(cls) -> "RuntimeState":
        """Create the default runtime state for a fresh application start."""

        return cls()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeState":
        """Restore runtime state from a plain dictionary."""

        status_value = payload.get("monitoring_status", MonitoringStatus.STOPPED.value)
        return cls(
            monitoring_status=MonitoringStatus(status_value),
            started_at=payload.get("started_at"),
            current_cycle_started_at=payload.get("current_cycle_started_at"),
            current_pair=payload.get("current_pair"),
            queue_size=int(payload.get("queue_size", 0)),
            last_error=payload.get("last_error"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the runtime state into a JSON-serializable dictionary."""

        payload = asdict(self)
        payload["monitoring_status"] = self.monitoring_status.value
        return payload


@dataclass(slots=True)
class ServiceEvent:
    """Represents a structured service event for persistent logging."""

    level: str
    module: str
    event_type: str
    message: str
    context: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a JSON-serializable dictionary."""

        return {
            "level": self.level,
            "module": self.module,
            "event_type": self.event_type,
            "message": self.message,
            "context": self.context or {},
            "created_at": self.created_at,
        }
