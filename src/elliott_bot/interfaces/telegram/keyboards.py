"""Reply keyboard builders for Telegram user flows."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_menu_keyboard(*, monitoring_running: bool) -> ReplyKeyboardMarkup:
    """Build the main Reply Keyboard used for the primary navigation flows."""

    start_stop_label = "Стоп" if monitoring_running else "Старт"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=start_stop_label), KeyboardButton(text="Статус")],
            [KeyboardButton(text="Список пар"), KeyboardButton(text="Добавить пару")],
            [KeyboardButton(text="Изменить таймфрейм"), KeyboardButton(text="Удалить пару")],
            [KeyboardButton(text="Проверить пару"), KeyboardButton(text="Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def build_timeframe_keyboard() -> ReplyKeyboardMarkup:
    """Build a Reply Keyboard used when the user needs to choose a timeframe."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1m"), KeyboardButton(text="5m"), KeyboardButton(text="15m")],
            [KeyboardButton(text="1h"), KeyboardButton(text="1d")],
            [KeyboardButton(text="Использовать 5m"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите таймфрейм",
    )


def build_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Build a minimal Reply Keyboard for cancellable multi-step scenarios."""

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        input_field_placeholder="Можно отменить сценарий",
    )
