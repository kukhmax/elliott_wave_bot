"""Formatting helpers for Telegram responses."""

from __future__ import annotations

from elliott_bot.domain.models import PairStatus
from elliott_bot.services.application_context import ApplicationContext
from elliott_bot.services.manual_check_service import ManualCheckResult
from elliott_bot.services.notification_message_service import NotificationMessageService


SUPPORTED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d"}
SETTINGS_FIELD_LABELS = {
    "default_timeframe": "⏱ Таймфрейм",
    "scan_interval_seconds": "🔁 Интервал",
    "default_history_depth": "🕯 История",
    "max_auto_pairs": "📌 Авто-пары",
    "search_mode": "🎯 Режим поиска",
    "extremum_sensitivity": "📐 Экстремумы",
    "notifications_enabled": "🔔 Уведомления",
    "manual_check_explain_rejections": "🧾 Пояснять отказы",
}


def normalize_symbol(raw_value: str) -> str:
    """Normalize a trading pair symbol entered by the user."""

    return raw_value.replace("/", "").replace(" ", "").upper()


def normalize_timeframe(raw_value: str, default_timeframe: str) -> str:
    """Normalize timeframe input while supporting the default-timeframe shortcut."""

    value = raw_value.strip()
    if "Использовать " in value:
        return default_timeframe
    return value


def is_supported_timeframe(value: str) -> bool:
    """Return whether the timeframe is supported by the current first version."""

    return value in SUPPORTED_TIMEFRAMES


def format_welcome_text(context: ApplicationContext) -> str:
    """Build the welcome message shown on the first interaction."""

    return (
        "🤖 Elliott Bot готов к работе.\n"
        "📈 Бот ищет классическую 5-волновую структуру Эллиотта.\n"
        f"⏱ Дефолтный таймфрейм старта: {context.settings.default_timeframe}.\n"
        f"🛰 Текущее состояние мониторинга: {context.runtime_state.monitoring_status.value}.\n"
        "⌨️ Основное управление доступно через нижнюю клавиатуру."
    )


def format_status_text(context: ApplicationContext) -> str:
    """Build a human-readable status summary for the current application state."""

    last_error = context.runtime_state.last_error or "нет"
    current_pair = context.runtime_state.current_pair or "нет"
    queue_size = context.runtime_state.queue_size
    cycle_started_at = context.runtime_state.current_cycle_started_at or "нет"
    return (
        "📊 Статус бота:\n"
        f"🛰 Мониторинг: {context.runtime_state.monitoring_status.value}\n"
        f"📌 Отслеживаемых пар: {context.active_pairs_count}\n"
        f"🔎 Текущая пара: {current_pair}\n"
        f"🧾 Осталось в очереди: {queue_size}\n"
        f"🕒 Цикл начат: {cycle_started_at}\n"
        f"⏱ Дефолтный таймфрейм: {context.settings.default_timeframe}\n"
        f"🔁 Интервал сканирования: {context.settings.scan_interval_seconds} сек.\n"
        f"🏦 Биржа: {context.settings.exchange}\n"
        f"⚠️ Последняя ошибка: {last_error}"
    )


def format_watchlist_text(context: ApplicationContext) -> str:
    """Build a watchlist summary for Telegram output."""

    active_pairs = [pair for pair in context.watchlist_state.pairs if pair.status == PairStatus.ACTIVE]
    if not active_pairs:
        return "📭 Список пар пуст. Добавьте пару вручную или запустите мониторинг позже."

    config_map = {config.symbol: config for config in context.watchlist_state.configs}
    lines = ["📋 Текущий список пар:"]
    for pair in active_pairs:
        config = config_map.get(pair.symbol)
        timeframe = config.timeframe if config else context.settings.default_timeframe
        lines.append(
            f"• {pair.symbol} | ⏱ {timeframe} | 🔖 {pair.source_origin.value} | 📍 {pair.status.value}"
        )
    return "\n".join(lines)


def format_settings_text(context: ApplicationContext) -> str:
    """Build a compact settings summary for Telegram output."""

    return (
        "⚙️ Текущие настройки:\n"
        f"⏱ Таймфрейм по умолчанию: {context.settings.default_timeframe}\n"
        f"🔁 Интервал сканирования: {context.settings.scan_interval_seconds} сек.\n"
        f"🕯 Глубина истории: {context.settings.default_history_depth}\n"
        f"📌 Максимум авто-пар: {context.settings.max_auto_pairs}\n"
        f"🎯 Режим поиска: {context.settings.search_mode}\n"
        f"📐 Чувствительность экстремумов: {context.settings.extremum_sensitivity}\n"
        f"🔔 Уведомления: {context.settings.notifications_enabled}\n"
        f"🏦 Биржа: {context.settings.exchange}"
    )


def format_manual_check_result(result: ManualCheckResult) -> str:
    """Build a human-readable Telegram response for a manual check result."""

    return NotificationMessageService().build_manual_check_caption(result)


def format_settings_menu_text(context: ApplicationContext) -> str:
    """Build the settings editing menu text."""

    return (
        f"{format_settings_text(context)}\n"
        "🛠 Выберите параметр, который хотите изменить."
    )


def format_setting_update_prompt(field_name: str, current_value: object) -> str:
    """Build a prompt for entering a new value for a selected setting."""

    label = SETTINGS_FIELD_LABELS.get(field_name, field_name)
    return (
        f"{label}\n"
        f"📍 Текущее значение: {current_value}\n"
        "✍️ Выберите новое значение или введите его вручную."
    )


def format_setting_updated_text(field_name: str, new_value: object) -> str:
    """Build a success message for an updated setting."""

    label = SETTINGS_FIELD_LABELS.get(field_name, field_name)
    return f"✅ {label} обновлен: {new_value}"
