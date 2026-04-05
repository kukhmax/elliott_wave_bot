"""Service responsible for persistent application settings."""

from __future__ import annotations

from elliott_bot.domain.models import EventCategory, ServiceEvent
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
        payload["telegram_bot_token"] = base_settings.telegram_bot_token
        payload["cmc_api_key"] = base_settings.cmc_api_key
        settings = AppSettings(**payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="settings_loaded",
                message="Application settings loaded from persistent storage.",
                category=EventCategory.STORAGE,
                context={
                    "exchange": settings.exchange,
                    "default_timeframe": settings.default_timeframe,
                },
            )
        )
        return settings

    def save(self, settings: AppSettings) -> None:
        """Persist application settings snapshot."""

        payload = settings.model_dump(mode="json")
        payload.pop("telegram_bot_token", None)
        payload.pop("cmc_api_key", None)
        self._storage.write_json(self._storage.settings_path, payload)
        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="settings_saved",
                message="Application settings saved to persistent storage.",
                category=EventCategory.STORAGE,
                context={
                    "exchange": settings.exchange,
                    "default_timeframe": settings.default_timeframe,
                },
            )
        )
