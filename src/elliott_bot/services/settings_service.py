"""Service responsible for persistent application settings."""

from __future__ import annotations

from elliott_bot.domain.models import ServiceEvent
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


class SettingsService:
    """Persist and restore application settings snapshots."""

    def __init__(self, storage: FileStorage) -> None:
        self._storage = storage

    def load(self, base_settings: AppSettings) -> AppSettings:
        """Load persisted settings or initialize storage with the base settings."""

        default_payload = base_settings.model_dump(mode="json")
        payload = self._storage.read_json(self._storage.settings_path, default_payload)
        settings = AppSettings(**payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="settings_loaded",
                message="Application settings loaded from persistent storage.",
                context={
                    "exchange": settings.exchange,
                    "default_timeframe": settings.default_timeframe,
                },
            )
        )
        return settings

    def save(self, settings: AppSettings) -> None:
        """Persist application settings snapshot."""

        self._storage.write_json(self._storage.settings_path, settings.model_dump(mode="json"))
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="settings_saved",
                message="Application settings saved to persistent storage.",
                context={
                    "exchange": settings.exchange,
                    "default_timeframe": settings.default_timeframe,
                },
            )
        )
