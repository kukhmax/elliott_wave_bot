"""Telegram runtime primitives for the initial application scaffold."""

from __future__ import annotations

from aiogram import Bot, Dispatcher

from elliott_bot.interfaces.telegram.handlers import router
from elliott_bot.services.application_context import ApplicationContext

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

    def create_dispatcher(self, app_context: ApplicationContext) -> Dispatcher:
        """Create a dispatcher preloaded with the shared application context."""

        dispatcher = Dispatcher()
        dispatcher["app_context"] = app_context
        dispatcher.include_router(router)
        self._logger.info("Telegram dispatcher created and router registered.")
        return dispatcher
