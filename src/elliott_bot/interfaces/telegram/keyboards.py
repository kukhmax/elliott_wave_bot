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


def build_timeframe_keyboard(*, default_timeframe: str = "5m") -> ReplyKeyboardMarkup:
    """Build a Reply Keyboard used when the user needs to choose a timeframe."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1m"), KeyboardButton(text="5m"), KeyboardButton(text="15m")],
            [KeyboardButton(text="1h"), KeyboardButton(text="1d")],
            [KeyboardButton(text=f"Использовать {default_timeframe}"), KeyboardButton(text="Отмена")],
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


def build_settings_keyboard() -> ReplyKeyboardMarkup:
    """Build a Reply Keyboard for editable bot settings."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Таймфрейм"), KeyboardButton(text="Интервал")],
            [KeyboardButton(text="История"), KeyboardButton(text="Авто-пары")],
            [KeyboardButton(text="Поиск"), KeyboardButton(text="Экстремумы")],
            [KeyboardButton(text="Уведомления"), KeyboardButton(text="Пояснять отказы")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите параметр для изменения",
    )


def build_scan_interval_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for scan interval updates."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="60"), KeyboardButton(text="120"), KeyboardButton(text="300")],
            [KeyboardButton(text="600"), KeyboardButton(text="900")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите интервал в секундах",
    )


def build_history_depth_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for default history depth."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="120"), KeyboardButton(text="150"), KeyboardButton(text="200")],
            [KeyboardButton(text="300"), KeyboardButton(text="500")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите глубину истории",
    )


def build_auto_pairs_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for the automatic watchlist size."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="10"), KeyboardButton(text="20"), KeyboardButton(text="30")],
            [KeyboardButton(text="40"), KeyboardButton(text="50")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите количество авто-пар",
    )


def build_search_mode_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for search mode changes."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="standard"), KeyboardButton(text="aggressive")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите режим поиска",
    )


def build_extremum_sensitivity_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for extremum sensitivity changes."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="strict"), KeyboardButton(text="standard"), KeyboardButton(text="aggressive")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите чувствительность",
    )


def build_boolean_keyboard() -> ReplyKeyboardMarkup:
    """Build preset choices for boolean settings."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Включить"), KeyboardButton(text="Выключить")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
