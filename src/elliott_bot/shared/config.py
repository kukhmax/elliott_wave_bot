"""Application configuration models and loaders."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Central configuration object loaded from environment variables."""

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    market_universe_provider: str = Field(default="coinmarketcap", alias="MARKET_UNIVERSE_PROVIDER")
    market_data_provider: str = Field(default="binance", alias="MARKET_DATA_PROVIDER")
    exchange: str = Field(default="binance_spot", alias="EXCHANGE")
    default_timeframe: str = Field(default="5m", alias="DEFAULT_TIMEFRAME")
    scan_interval_seconds: int = Field(default=300, alias="SCAN_INTERVAL_SECONDS")
    default_history_depth: int = Field(default=150, alias="DEFAULT_HISTORY_DEPTH")
    max_auto_pairs: int = Field(default=20, alias="MAX_AUTO_PAIRS")
    search_mode: str = Field(default="standard", alias="SEARCH_MODE")
    extremum_sensitivity: str = Field(default="standard", alias="EXTREMUM_SENSITIVITY")
    cmc_api_key: str = Field(default="", alias="CMC_API_KEY")
    default_quote_asset: str = Field(default="USDT", alias="DEFAULT_QUOTE_ASSET")
    request_timeout_seconds: int = Field(default=10, alias="REQUEST_TIMEOUT_SECONDS")
    retry_count: int = Field(default=2, alias="RETRY_COUNT")
    rate_limit_delay_ms: int = Field(default=250, alias="RATE_LIMIT_DELAY_MS")
    notifications_enabled: bool = Field(default=True, alias="NOTIFICATIONS_ENABLED")
    manual_check_explain_rejections: bool = Field(default=True, alias="MANUAL_CHECK_EXPLAIN_REJECTIONS")
    chart_timezone: str = Field(default="local", alias="CHART_TIMEZONE")
    storage_path: Path = Field(default=Path("storage"), alias="STORAGE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    def resolved_storage_path(self) -> Path:
        """Return an absolute storage path for file-based persistence."""

        return self.storage_path.resolve()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load settings once and reuse them across the application."""

    return AppSettings()
