"""Service responsible for persistent application settings."""

from __future__ import annotations

from elliott_bot.domain.models import EventCategory, ServiceEvent
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


class SettingsService:
    """Persist and restore application settings snapshots."""

    EDITABLE_FIELDS = {
        "default_timeframe",
        "scan_interval_seconds",
        "default_history_depth",
        "max_auto_pairs",
        "search_mode",
        "extremum_sensitivity",
        "notifications_enabled",
        "manual_check_explain_rejections",
    }

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

    def update(self, settings: AppSettings, field_name: str, value: object) -> AppSettings:
        """Validate and apply a mutable settings update to the live settings object."""

        if field_name not in self.EDITABLE_FIELDS:
            raise ValueError(f"Unsupported editable setting: {field_name}")

        payload = settings.model_dump(mode="json")
        payload["telegram_bot_token"] = settings.telegram_bot_token
        payload["cmc_api_key"] = settings.cmc_api_key
        payload[field_name] = value
        validated = AppSettings(**payload)

        for editable_field in self.EDITABLE_FIELDS:
            setattr(settings, editable_field, getattr(validated, editable_field))

        self.save(settings)
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
