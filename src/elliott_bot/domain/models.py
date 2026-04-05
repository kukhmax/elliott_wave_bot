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


class MarketDataErrorCategory(StrEnum):
    """Represents structured categories returned by the market data layer."""

    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    INVALID_SYMBOL = "invalid_symbol"
    EMPTY_RESPONSE = "empty_response"
    INVALID_RESPONSE = "invalid_response"
    INSUFFICIENT_HISTORY = "insufficient_history"


class ExtremumKind(StrEnum):
    """Represents the direction of a detected local extremum."""

    HIGH = "high"
    LOW = "low"


class WaveDirection(StrEnum):
    """Represents the direction of a candidate Elliott structure."""

    LONG = "long"
    SHORT = "short"


class EventCategory(StrEnum):
    """Represents logical categories for persistent event logs."""

    SYSTEM = "system_events"
    MARKET_DATA = "market_data_events"
    ANALYSIS = "analysis_events"
    NOTIFICATION = "notification_events"
    STORAGE = "storage_events"


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
class OHLCVBar:
    """Represents a normalized market candle."""

    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the candle into a JSON-serializable dictionary."""

        return asdict(self)


@dataclass(slots=True)
class MarketSeries:
    """Represents a normalized candle series returned by a market provider."""

    symbol: str
    timeframe: str
    bars: list[OHLCVBar]
    loaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert the series into a JSON-serializable dictionary."""

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bars": [bar.to_dict() for bar in self.bars],
            "loaded_at": self.loaded_at,
            "source": self.source,
        }


@dataclass(slots=True)
class MarketDataError:
    """Represents a structured market data failure."""

    category: MarketDataErrorCategory
    message: str
    retryable: bool
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the error into a JSON-serializable dictionary."""

        return {
            "category": self.category.value,
            "message": self.message,
            "retryable": self.retryable,
            "context": self.context,
        }


@dataclass(slots=True)
class ExtremumPoint:
    """Represents a normalized local extremum derived from OHLCV bars."""

    index: int
    timestamp: int
    price: float
    kind: ExtremumKind
    strength: float
    bar_distance_from_previous: int

    def to_dict(self) -> dict[str, Any]:
        """Convert the extremum point into a JSON-serializable dictionary."""

        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(slots=True)
class WavePointSet:
    """Represents the six pivot points used by a wave candidate."""

    p0: ExtremumPoint
    p1: ExtremumPoint
    p2: ExtremumPoint
    p3: ExtremumPoint
    p4: ExtremumPoint
    p5: ExtremumPoint
    direction: WaveDirection

    def to_dict(self) -> dict[str, Any]:
        """Convert the wave point set into a JSON-serializable dictionary."""

        return {
            "p0": self.p0.to_dict(),
            "p1": self.p1.to_dict(),
            "p2": self.p2.to_dict(),
            "p3": self.p3.to_dict(),
            "p4": self.p4.to_dict(),
            "p5": self.p5.to_dict(),
            "direction": self.direction.value,
        }


@dataclass(slots=True)
class WaveCandidate:
    """Represents a candidate five-wave structure after early filtering."""

    candidate_id: str
    symbol: str
    timeframe: str
    direction: WaveDirection
    points: WavePointSet
    length_wave1: float
    length_wave2: float
    length_wave3: float
    length_wave4: float
    length_wave5: float
    source_extremums: list[ExtremumPoint]
    structural_notes: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert the wave candidate into a JSON-serializable dictionary."""

        return {
            "candidate_id": self.candidate_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "points": self.points.to_dict(),
            "length_wave1": self.length_wave1,
            "length_wave2": self.length_wave2,
            "length_wave3": self.length_wave3,
            "length_wave4": self.length_wave4,
            "length_wave5": self.length_wave5,
            "source_extremums": [point.to_dict() for point in self.source_extremums],
            "structural_notes": self.structural_notes,
            "rejection_reasons": self.rejection_reasons,
            "generated_at": self.generated_at,
        }


@dataclass(slots=True)
class WaveAnalysisResult:
    """Represents the full output of the early wave-analysis pipeline."""

    symbol: str
    timeframe: str
    candidates: list[WaveCandidate]
    rejected_windows: list[dict[str, Any]]
    extremums: list[ExtremumPoint]
    analyzed_bars: int

    @property
    def has_candidates(self) -> bool:
        """Return whether the analysis produced at least one valid candidate."""

        return bool(self.candidates)


@dataclass(slots=True)
class ElliottValidationResult:
    """Represents the result of Fibonacci and proportion validation."""

    candidate_id: str
    status: SignalStatus
    confidence_score: float
    strong_matches: list[str] = field(default_factory=list)
    acceptable_matches: list[str] = field(default_factory=list)
    weak_matches: list[str] = field(default_factory=list)
    downgrade_reasons: list[str] = field(default_factory=list)
    diagnostic_summary: str = ""
    ratios: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the validation result into a JSON-serializable dictionary."""

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
    category: EventCategory = EventCategory.SYSTEM
    reason_code: str | None = None
    context: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a JSON-serializable dictionary."""

        return {
            "level": self.level,
            "category": self.category.value,
            "module": self.module,
            "event_type": self.event_type,
            "message": self.message,
            "reason_code": self.reason_code,
            "context": self.context or {},
            "created_at": self.created_at,
        }
