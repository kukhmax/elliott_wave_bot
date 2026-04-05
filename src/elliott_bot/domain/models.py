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


class PairStatus(StrEnum):
    """Represents the current state of a tracked trading pair."""

    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"


class PairSourceOrigin(StrEnum):
    """Represents how a trading pair was added to the system."""

    AUTO = "auto"
    MANUAL = "manual"


class SignalStatus(StrEnum):
    """Represents the validation result used for signal storage."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    REJECTED = "rejected"


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
class TradingPair:
    """Represents a tracked market instrument within the bot."""

    symbol: str
    base_asset: str
    quote_asset: str
    exchange: str
    status: PairStatus = PairStatus.ACTIVE
    source_origin: PairSourceOrigin = PairSourceOrigin.AUTO

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TradingPair":
        """Restore a trading pair from a plain dictionary."""

        return cls(
            symbol=payload["symbol"],
            base_asset=payload["base_asset"],
            quote_asset=payload["quote_asset"],
            exchange=payload["exchange"],
            status=PairStatus(payload.get("status", PairStatus.ACTIVE.value)),
            source_origin=PairSourceOrigin(payload.get("source_origin", PairSourceOrigin.AUTO.value)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the trading pair into a JSON-serializable dictionary."""

        payload = asdict(self)
        payload["status"] = self.status.value
        payload["source_origin"] = self.source_origin.value
        return payload


@dataclass(slots=True)
class PairMonitoringConfig:
    """Represents monitoring configuration for a specific trading pair."""

    symbol: str
    timeframe: str
    scan_enabled: bool = True
    priority: int = 100
    history_depth: int = 150
    last_checked_at: str | None = None
    last_signal_at: str | None = None
    last_signal_signature: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PairMonitoringConfig":
        """Restore pair monitoring configuration from a dictionary."""

        return cls(
            symbol=payload["symbol"],
            timeframe=payload["timeframe"],
            scan_enabled=bool(payload.get("scan_enabled", True)),
            priority=int(payload.get("priority", 100)),
            history_depth=int(payload.get("history_depth", 150)),
            last_checked_at=payload.get("last_checked_at"),
            last_signal_at=payload.get("last_signal_at"),
            last_signal_signature=payload.get("last_signal_signature"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the monitoring configuration into a JSON-serializable dictionary."""

        return asdict(self)


@dataclass(slots=True)
class WatchlistState:
    """Represents all persisted watchlist entities."""

    pairs: list[TradingPair] = field(default_factory=list)
    configs: list[PairMonitoringConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WatchlistState":
        """Restore the watchlist state from a dictionary payload."""

        return cls(
            pairs=[TradingPair.from_dict(item) for item in payload.get("pairs", [])],
            configs=[PairMonitoringConfig.from_dict(item) for item in payload.get("configs", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the watchlist state into a JSON-serializable dictionary."""

        return {
            "pairs": [pair.to_dict() for pair in self.pairs],
            "configs": [config.to_dict() for config in self.configs],
        }


@dataclass(slots=True)
class SignalRecord:
    """Represents a stored signal used for history and anti-duplicate checks."""

    signal_id: str
    signal_signature: str
    symbol: str
    timeframe: str
    direction: str
    status: SignalStatus
    sent_to_telegram: bool
    duplicate_of: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    suppressed_reason: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SignalRecord":
        """Restore a signal record from a dictionary."""

        return cls(
            signal_id=payload["signal_id"],
            signal_signature=payload["signal_signature"],
            symbol=payload["symbol"],
            timeframe=payload["timeframe"],
            direction=payload["direction"],
            status=SignalStatus(payload["status"]),
            sent_to_telegram=bool(payload["sent_to_telegram"]),
            duplicate_of=payload.get("duplicate_of"),
            created_at=payload.get("created_at", datetime.now(timezone.utc).isoformat()),
            suppressed_reason=payload.get("suppressed_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the signal record into a JSON-serializable dictionary."""

        payload = asdict(self)
        payload["status"] = self.status.value
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
