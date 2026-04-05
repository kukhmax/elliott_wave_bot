"""Service responsible for signal history persistence and anti-duplicate state."""

from __future__ import annotations

from elliott_bot.domain.models import ServiceEvent, SignalRecord
from elliott_bot.storage.file_storage import FileStorage


class SignalHistoryService:
    """Manage persisted signal history records."""

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
                context={"records_count": len(records)},
            )
        )
        return records

    def save(self, records: list[SignalRecord]) -> None:
        """Persist the full signal history."""

        payload = [record.to_dict() for record in records]
        self._storage.write_json(self._storage.signal_history_path, payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="signal_history_saved",
                message="Signal history saved to persistent storage.",
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
                context={
                    "signal_id": record.signal_id,
                    "symbol": record.symbol,
                    "status": record.status.value,
                },
            )
        )
        return records
