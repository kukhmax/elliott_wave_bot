"""Telegram runtime primitives for the initial application scaffold."""

from __future__ import annotations

from aiogram import Bot

from elliott_bot.shared.logging import get_logger


class TelegramBotRuntime:
    """Lightweight wrapper around the Telegram bot client."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._logger = get_logger(self.__class__.__name__)
        self._bot: Bot | None = None

    @property
    def configured(self) -> bool:
        """Return whether the runtime has a token and can create a bot client."""

        return bool(self._token)

    def create_bot(self) -> Bot | None:
        """Create the Telegram bot client lazily when a token is configured."""

        if not self.configured:
            self._logger.warning("Telegram runtime is not configured because the bot token is empty.")
            return None

        if self._bot is None:
            self._bot = Bot(token=self._token)
            self._logger.info("Telegram bot client created.")

        return self._bot
