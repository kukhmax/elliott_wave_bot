"""File-based persistence utilities for the first implementation step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elliott_bot.domain.models import ServiceEvent
from elliott_bot.shared.logging import get_logger


class FileStorage:
    """Simple JSON file storage used for persistent bot state."""

    MAX_EVENT_LOG_RECORDS = 1000

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._logger = get_logger(self.__class__.__name__)
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def runtime_state_path(self) -> Path:
        """Return the file path used for runtime state persistence."""

        return self._base_path / "runtime_state.json"

    @property
    def event_log_path(self) -> Path:
        """Return the file path used for structured event logging."""

        return self._base_path / "event_log.jsonl"

    @property
    def settings_path(self) -> Path:
        """Return the file path used for persisted application settings."""

        return self._base_path / "settings.json"

    @property
    def watchlist_path(self) -> Path:
        """Return the file path used for persisted tracked pairs."""

        return self._base_path / "watchlist.json"

    @property
    def signal_history_path(self) -> Path:
        """Return the file path used for persisted signal history."""

        return self._base_path / "signal_history.json"

    def read_json(self, file_path: Path, default: Any) -> Any:
        """Read JSON content or return a safe default when the file is absent."""

        if not file_path.exists():
            self._logger.info("Storage file %s does not exist. Using defaults.", file_path)
            return default

        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self._logger.error("Failed to decode JSON from %s: %s", file_path, error)
            return default

    def write_json(self, file_path: Path, payload: Any) -> None:
        """Persist JSON content using a temporary file for safer writes."""

        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(file_path)
        self._logger.info("Persisted JSON payload to %s", file_path)

    def append_event(self, event: ServiceEvent) -> None:
        """Append a structured event to the JSON lines event log."""

        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.event_log_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(f"{line}\n")

        self._truncate_event_log_if_needed()
        self._logger.info("Appended event %s to %s", event.event_type, self.event_log_path)

    def _truncate_event_log_if_needed(self) -> None:
        """Keep the event log within the configured retention window."""

        try:
            lines = self.event_log_path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            self._logger.error("Failed to inspect event log retention window: %s", error)
            return

        if len(lines) <= self.MAX_EVENT_LOG_RECORDS:
            return

        trimmed_lines = lines[-self.MAX_EVENT_LOG_RECORDS :]
        self.event_log_path.write_text("\n".join(trimmed_lines) + "\n", encoding="utf-8")
        self._logger.warning(
            "Event log truncated to the last %s records at %s.",
            self.MAX_EVENT_LOG_RECORDS,
            self.event_log_path,
        )
