"""Formatting helpers for Telegram responses."""

from __future__ import annotations

from elliott_bot.domain.models import PairStatus
from elliott_bot.services.application_context import ApplicationContext
from elliott_bot.services.manual_check_service import ManualCheckResult


SUPPORTED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d"}


def normalize_symbol(raw_value: str) -> str:
    """Normalize a trading pair symbol entered by the user."""

    return raw_value.replace("/", "").replace(" ", "").upper()


def normalize_timeframe(raw_value: str, default_timeframe: str) -> str:
    """Normalize timeframe input while supporting the default-timeframe shortcut."""

    value = raw_value.strip()
    if value == "Использовать 5m":
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
    return (
        "📊 Статус бота:\n"
        f"🛰 Мониторинг: {context.runtime_state.monitoring_status.value}\n"
        f"📌 Отслеживаемых пар: {context.active_pairs_count}\n"
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

    if result.best_candidate is None:
        return (
            f"🔎 Проверка пары: {result.symbol}\n"
            f"⏱ Таймфрейм: {result.timeframe}\n"
            f"📉 Статус: {result.status}\n"
            f"⚠️ Итог: {result.summary}"
        )

    candidate = result.best_candidate
    return (
        f"🔎 Проверка пары: {result.symbol}\n"
        f"⏱ Таймфрейм: {result.timeframe}\n"
        f"📈 Статус: {result.status}\n"
        f"🧭 Направление: {candidate.direction.value}\n"
        f"🌊 Кандидат: {candidate.candidate_id}\n"
        f"📌 Примечания: {', '.join(candidate.structural_notes)}\n"
        f"✅ Итог: {result.summary}"
    )
