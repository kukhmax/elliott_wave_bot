"""Service responsible for signal history persistence and anti-duplicate state."""

from __future__ import annotations

from uuid import uuid4

from elliott_bot.domain.models import EventCategory, ServiceEvent, SignalRecord, SignalStatus
from elliott_bot.storage.file_storage import FileStorage


class SignalHistoryService:
    """Manage persisted signal history records."""

    MAX_SIGNAL_RECORDS = 500

    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    def load(self) -> list[SignalRecord]:
        """Load signal history from persistent storage."""

        payload = self._storage.read_json(self._storage.signal_history_path, [])
        records = [SignalRecord.from_dict(item) for item in payload]
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="signal_history_loaded",
                message="Signal history loaded from persistent storage.",
                category=EventCategory.STORAGE,
                context={"records_count": len(records)},
            )
        )
        return records

    def save(self, records: list[SignalRecord]) -> None:
        """Persist the full signal history."""

        payload = [record.to_dict() for record in self._trim_records(records)]
        self._storage.write_json(self._storage.signal_history_path, payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="signal_history_saved",
                message="Signal history saved to persistent storage.",
                category=EventCategory.STORAGE,
                context={"records_count": len(records)},
            )
        )

    def register(self, records: list[SignalRecord], record: SignalRecord) -> list[SignalRecord]:
        """Append a new signal record and return the updated collection."""

        records.append(record)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="signal_registered",
                message="Signal record appended to in-memory history.",
                category=EventCategory.NOTIFICATION,
                context={
                    "signal_id": record.signal_id,
                    "symbol": record.symbol,
                    "status": record.status.value,
                },
            )
        )
        return self._trim_records(records)

    def find_duplicate(self, records: list[SignalRecord], signal_signature: str) -> SignalRecord | None:
        """Find the latest signal record with the same deterministic signature."""

        for record in reversed(records):
            if record.signal_signature == signal_signature:
                return record
        return None

    def register_decision(
        self,
        records: list[SignalRecord],
        *,
        signal_signature: str,
        symbol: str,
        timeframe: str,
        direction: str,
        status: SignalStatus,
        sent_to_telegram: bool,
        duplicate_of: str | None = None,
        suppressed_reason: str | None = None,
    ) -> list[SignalRecord]:
        """Create, register and keep a bounded decision history record."""

        record = SignalRecord(
            signal_id=str(uuid4()),
            signal_signature=signal_signature,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            status=status,
            sent_to_telegram=sent_to_telegram,
            duplicate_of=duplicate_of,
            suppressed_reason=suppressed_reason,
        )
        return self.register(records, record)

    def _trim_records(self, records: list[SignalRecord]) -> list[SignalRecord]:
        """Keep the history within the configured bounded window."""

        if len(records) <= self.MAX_SIGNAL_RECORDS:
            return records
        return records[-self.MAX_SIGNAL_RECORDS :]
