"""Telegram handlers for the current management scenarios."""

from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from elliott_bot.domain.models import MonitoringStatus, PairSourceOrigin, PairStatus, SignalStatus
from elliott_bot.interfaces.telegram.keyboards import (
    build_auto_pairs_keyboard,
    build_boolean_keyboard,
    build_cancel_keyboard,
    build_extremum_sensitivity_keyboard,
    build_main_menu_keyboard,
    build_scan_interval_keyboard,
    build_search_mode_keyboard,
    build_settings_keyboard,
    build_timeframe_keyboard,
    build_history_depth_keyboard,
)
from elliott_bot.interfaces.telegram.presenters import (
    format_setting_update_prompt,
    format_setting_updated_text,
    format_settings_menu_text,
    format_settings_text,
    format_status_text,
    format_watchlist_text,
    format_welcome_text,
    is_supported_timeframe,
    normalize_symbol,
    normalize_timeframe,
)
from elliott_bot.interfaces.telegram.states import (
    AddPairStates,
    ChangeTimeframeStates,
    DeletePairStates,
    ManualCheckStates,
    SettingsStates,
)
from elliott_bot.services.application_context import ApplicationContext
from elliott_bot.shared.logging import get_logger

router = Router(name="telegram_management")
LOGGER = get_logger("elliott_bot.telegram.handlers")


def _main_menu(context: ApplicationContext):
    """Build the current main menu based on runtime state."""

    return build_main_menu_keyboard(
        monitoring_running=context.runtime_state.monitoring_status == MonitoringStatus.RUNNING
    )


@router.message(CommandStart())
@router.message(Command("menu"))
async def handle_start_command(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Show the main welcome screen and reset any pending scenario."""

    await state.clear()
    await message.answer(
        format_welcome_text(app_context),
        reply_markup=_main_menu(app_context),
    )


@router.message(F.text == "Назад")
async def handle_back_to_menu(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Return from nested menus back to the main menu."""

    await state.clear()
    await message.answer("↩️ Возврат в главное меню.", reply_markup=_main_menu(app_context))


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
async def handle_cancel(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Cancel the active multi-step scenario and return to the main menu."""

    await state.clear()
    await message.answer("↩️ Текущий сценарий отменен.", reply_markup=_main_menu(app_context))


@router.message(F.text == "Статус")
async def handle_status(message: Message, app_context: ApplicationContext) -> None:
    """Show the current monitoring and configuration status."""

    await message.answer(format_status_text(app_context), reply_markup=_main_menu(app_context))


@router.message(F.text == "Старт")
async def handle_monitoring_start(message: Message, app_context: ApplicationContext) -> None:
    """Move monitoring into the running state and report the result."""

    await message.answer("🌐 Загружаю пары с рынка и подготавливаю watchlist...", reply_markup=_main_menu(app_context))
    sync_result = await app_context.ensure_auto_watchlist()
    if sync_result["error_message"] is not None:
        await message.answer(
            f"⚠️ Не удалось загрузить авто-пары: {sync_result['error_message']}",
            reply_markup=_main_menu(app_context),
        )
        return
    if sync_result["active_total_pairs"] == 0:
        await message.answer(
            "⚠️ Не удалось сформировать список пар для мониторинга. Проверьте ключ CMC и доступность рынка.",
            reply_markup=_main_menu(app_context),
        )
        return

    app_context.start_monitoring()
    LOGGER.info("Monitoring started from Telegram command.")
    await message.answer(
        "🚀 Мониторинг запущен.\n"
        f"➕ Авто-пар добавлено: {sync_result['added_count']}\n"
        f"📌 Отслеживаемых пар: {app_context.active_pairs_count}\n"
        f"🤖 Авто-пар активно: {sync_result['active_auto_pairs']}\n"
        f"⏱ Дефолтный таймфрейм: {app_context.settings.default_timeframe}\n"
        f"🔁 Интервал сканирования: {app_context.settings.scan_interval_seconds} сек.",
        reply_markup=_main_menu(app_context),
    )


@router.message(F.text == "Стоп")
async def handle_monitoring_stop(message: Message, app_context: ApplicationContext) -> None:
    """Move monitoring into the stopped state and report the result."""

    app_context.stop_monitoring()
    LOGGER.info("Monitoring stopped from Telegram command.")
    await message.answer(
        "🛑 Мониторинг остановлен.\n"
        "💾 Список пар, настройки и история сигналов сохранены.",
        reply_markup=_main_menu(app_context),
    )


@router.message(F.text == "Список пар")
async def handle_watchlist(message: Message, app_context: ApplicationContext) -> None:
    """Show the current watchlist."""

    await message.answer(format_watchlist_text(app_context), reply_markup=_main_menu(app_context))


@router.message(F.text == "Настройки")
async def handle_settings(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Show the current application settings and enter editing mode."""

    await state.set_state(SettingsStates.waiting_for_setting)
    await message.answer(format_settings_menu_text(app_context), reply_markup=build_settings_keyboard())


@router.message(SettingsStates.waiting_for_setting)
async def handle_settings_selection(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Select which setting should be updated."""

    field_name = _resolve_settings_field(message.text or "")
    if field_name is None:
        await message.answer("⚠️ Выберите параметр из меню настроек.", reply_markup=build_settings_keyboard())
        return

    await state.update_data(setting_field=field_name)
    await state.set_state(SettingsStates.waiting_for_value)
    await message.answer(
        format_setting_update_prompt(field_name, getattr(app_context.settings, field_name)),
        reply_markup=_settings_value_keyboard(app_context, field_name),
    )


@router.message(SettingsStates.waiting_for_value)
async def handle_settings_value(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Validate and persist a new settings value."""

    if (message.text or "") == "Назад":
        await state.set_state(SettingsStates.waiting_for_setting)
        await message.answer(format_settings_menu_text(app_context), reply_markup=build_settings_keyboard())
        return

    state_data = await state.get_data()
    field_name = state_data["setting_field"]
    try:
        value = _parse_settings_value(field_name, message.text or "")
        app_context.update_setting(field_name, value)
    except ValueError as error:
        await message.answer(
            f"⚠️ {error}",
            reply_markup=_settings_value_keyboard(app_context, field_name),
        )
        return

    await state.set_state(SettingsStates.waiting_for_setting)
    await message.answer(
        f"{format_setting_updated_text(field_name, getattr(app_context.settings, field_name))}\n\n"
        f"{format_settings_menu_text(app_context)}",
        reply_markup=build_settings_keyboard(),
    )


@router.message(F.text == "Проверить пару")
async def handle_manual_check_entry(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Start the manual check flow for a single trading pair."""

    await state.set_state(ManualCheckStates.waiting_for_symbol)
    await message.answer(
        "🔎 Введите торговую пару для ручной проверки, например BTCUSDT или BTC/USDT.",
        reply_markup=build_cancel_keyboard(),
    )


@router.message(ManualCheckStates.waiting_for_symbol)
async def handle_manual_check_symbol(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Capture the symbol used for the manual market check."""

    symbol = normalize_symbol(message.text or "")
    if not symbol:
        await message.answer("⚠️ Не удалось распознать пару. Попробуйте еще раз.", reply_markup=build_cancel_keyboard())
        return

    await state.update_data(symbol=symbol)
    await state.set_state(ManualCheckStates.waiting_for_timeframe)
    await message.answer(
        f"✅ Пара {symbol} распознана. Выберите таймфрейм для проверки или используйте {app_context.settings.default_timeframe}.",
        reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
    )


@router.message(ManualCheckStates.waiting_for_timeframe)
async def handle_manual_check_timeframe(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Run the manual check once the symbol and timeframe are available."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer(
            "⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.",
            reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
        )
        return

    state_data = await state.get_data()
    symbol = state_data["symbol"]
    await state.clear()

    await message.answer("⏳ Загружаю данные и запускаю базовый волновой анализ...", reply_markup=_main_menu(app_context))
    result = await app_context.manual_check_service.run(symbol=symbol, timeframe=timeframe)
    LOGGER.info("Manual check completed for %s on %s with status %s.", symbol, timeframe, result.status)
    caption = app_context.notification_message_service.build_manual_check_caption(result)
    chart_path = app_context.chart_rendering_service.render_manual_check_chart(result)
    signal_signature = _build_manual_signal_signature(app_context, result)
    sent_to_telegram = False
    try:
        if chart_path is not None:
            await message.answer_photo(
                photo=FSInputFile(chart_path),
                caption=caption,
                reply_markup=_main_menu(app_context),
            )
            sent_to_telegram = True
        else:
            await message.answer(caption, reply_markup=_main_menu(app_context))
            sent_to_telegram = result.status != SignalStatus.REJECTED.value
    finally:
        _cleanup_chart_file(chart_path)

    app_context.record_signal_decision(
        signal_signature=signal_signature,
        symbol=result.symbol,
        timeframe=result.timeframe,
        direction=result.best_candidate.direction.value if result.best_candidate is not None else "unknown",
        status=SignalStatus(result.status),
        sent_to_telegram=sent_to_telegram,
        suppressed_reason=None if result.status != SignalStatus.REJECTED.value else result.summary,
    )


@router.message(F.text == "Добавить пару")
async def handle_add_pair_entry(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Start the add-pair scenario."""

    await state.set_state(AddPairStates.waiting_for_symbol)
    await message.answer(
        "➕ Введите торговую пару, например BTCUSDT или BTC/USDT.",
        reply_markup=build_cancel_keyboard(),
    )
    LOGGER.info("Add pair scenario started.")


@router.message(AddPairStates.waiting_for_symbol)
async def handle_add_pair_symbol(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Capture the symbol entered by the user and move to timeframe selection."""

    symbol = normalize_symbol(message.text or "")
    if not symbol:
        await message.answer("⚠️ Не удалось распознать пару. Попробуйте еще раз.", reply_markup=build_cancel_keyboard())
        return

    await state.update_data(symbol=symbol)
    await state.set_state(AddPairStates.waiting_for_timeframe)
    await message.answer(
        f"✅ Пара {symbol} распознана. Теперь выберите таймфрейм или используйте {app_context.settings.default_timeframe}.",
        reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
    )


@router.message(AddPairStates.waiting_for_timeframe)
async def handle_add_pair_timeframe(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Persist the new pair using the selected or default timeframe."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer(
            "⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.",
            reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
        )
        return

    state_data = await state.get_data()
    symbol = state_data["symbol"]
    base_asset = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
    app_context.watchlist_state = app_context.watchlist_service.ensure_pair(
        state=app_context.watchlist_state,
        settings=app_context.settings,
        symbol=symbol,
        base_asset=base_asset,
        quote_asset="USDT",
        source_origin=PairSourceOrigin.MANUAL,
        timeframe=timeframe,
    )
    app_context.persist_watchlist()
    await state.clear()
    LOGGER.info("Trading pair %s added to the watchlist with timeframe %s.", symbol, timeframe)
    await message.answer(
        f"✅ Пара {symbol} добавлена.\n⏱ Таймфрейм: {timeframe}\n🛰 Пара участвует в фоновом мониторинге.",
        reply_markup=_main_menu(app_context),
    )


@router.message(F.text == "Изменить таймфрейм")
async def handle_change_timeframe_entry(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Start the change-timeframe scenario."""

    await state.set_state(ChangeTimeframeStates.waiting_for_symbol)
    await message.answer(
        "✏️ Введите символ пары, для которой нужно изменить таймфрейм.",
        reply_markup=build_cancel_keyboard(),
    )


@router.message(ChangeTimeframeStates.waiting_for_symbol)
async def handle_change_timeframe_symbol(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Validate the selected symbol before asking for a new timeframe."""

    symbol = normalize_symbol(message.text or "")
    known_symbols = {pair.symbol for pair in app_context.watchlist_state.pairs if pair.status == PairStatus.ACTIVE}
    if symbol not in known_symbols:
        await message.answer("⚠️ Такой пары нет в активном списке. Сначала добавьте ее.", reply_markup=build_cancel_keyboard())
        return

    await state.update_data(symbol=symbol)
    await state.set_state(ChangeTimeframeStates.waiting_for_timeframe)
    await message.answer(
        "⏱ Выберите новый таймфрейм.",
        reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
    )


@router.message(ChangeTimeframeStates.waiting_for_timeframe)
async def handle_change_timeframe_value(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Persist the new timeframe for the selected pair."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer(
            "⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.",
            reply_markup=build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe),
        )
        return

    state_data = await state.get_data()
    symbol = state_data["symbol"]
    for config in app_context.watchlist_state.configs:
        if config.symbol == symbol:
            config.timeframe = timeframe
            break

    app_context.persist_watchlist()
    await state.clear()
    LOGGER.info("Timeframe updated for %s to %s.", symbol, timeframe)
    await message.answer(
        f"✅ Таймфрейм для {symbol} обновлен на {timeframe}.",
        reply_markup=_main_menu(app_context),
    )


@router.message(F.text == "Удалить пару")
async def handle_delete_pair_entry(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Start the delete-pair scenario."""

    await state.set_state(DeletePairStates.waiting_for_symbol)
    await message.answer(
        "🗑 Введите символ пары, которую нужно удалить из мониторинга.",
        reply_markup=build_cancel_keyboard(),
    )


@router.message(DeletePairStates.waiting_for_symbol)
async def handle_delete_pair_symbol(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Remove the selected pair from the active watchlist."""

    symbol = normalize_symbol(message.text or "")
    removed = False
    for pair in app_context.watchlist_state.pairs:
        if pair.symbol == symbol:
            pair.status = PairStatus.REMOVED
            removed = True

    if not removed:
        await message.answer("⚠️ Такая пара не найдена в watchlist.", reply_markup=build_cancel_keyboard())
        return

    app_context.persist_watchlist()
    await state.clear()
    LOGGER.info("Trading pair %s removed from active watchlist.", symbol)
    await message.answer(
        f"✅ Пара {symbol} удалена из активного мониторинга.\n🗂 История сигналов сохранена.",
        reply_markup=_main_menu(app_context),
    )


@router.message()
async def handle_unknown_action(message: Message, app_context: ApplicationContext) -> None:
    """Fallback for unsupported or out-of-flow user messages."""

    await message.answer(
        "❓ Команда не распознана. Используйте кнопки меню или /start для возврата в главное меню.",
        reply_markup=_main_menu(app_context),
    )


def _resolve_settings_field(raw_value: str) -> str | None:
    """Map a settings menu label to the corresponding settings field."""

    return {
        "Таймфрейм": "default_timeframe",
        "Интервал": "scan_interval_seconds",
        "История": "default_history_depth",
        "Авто-пары": "max_auto_pairs",
        "Поиск": "search_mode",
        "Экстремумы": "extremum_sensitivity",
        "Уведомления": "notifications_enabled",
        "Пояснять отказы": "manual_check_explain_rejections",
    }.get(raw_value.strip())


def _settings_value_keyboard(app_context: ApplicationContext, field_name: str):
    """Return a suitable keyboard for the selected settings field."""

    if field_name == "default_timeframe":
        return build_timeframe_keyboard(default_timeframe=app_context.settings.default_timeframe)
    if field_name == "scan_interval_seconds":
        return build_scan_interval_keyboard()
    if field_name == "default_history_depth":
        return build_history_depth_keyboard()
    if field_name == "max_auto_pairs":
        return build_auto_pairs_keyboard()
    if field_name == "search_mode":
        return build_search_mode_keyboard()
    if field_name == "extremum_sensitivity":
        return build_extremum_sensitivity_keyboard()
    if field_name in {"notifications_enabled", "manual_check_explain_rejections"}:
        return build_boolean_keyboard()
    return build_cancel_keyboard()


def _parse_settings_value(field_name: str, raw_value: str) -> object:
    """Parse a Telegram-entered value for a selected settings field."""

    value = raw_value.strip()
    if field_name == "default_timeframe" and value.startswith("Использовать "):
        value = value.replace("Использовать ", "", 1)
    if field_name == "default_timeframe":
        if not is_supported_timeframe(value):
            raise ValueError("Таймфрейм не поддерживается. Выберите один из предложенных.")
        return value
    if field_name == "scan_interval_seconds":
        parsed = _parse_positive_int(value, "Интервал должен быть целым числом в секундах.")
        if parsed < 30:
            raise ValueError("Интервал должен быть не меньше 30 секунд.")
        return parsed
    if field_name == "default_history_depth":
        parsed = _parse_positive_int(value, "Глубина истории должна быть целым числом.")
        if parsed < 50:
            raise ValueError("Глубина истории должна быть не меньше 50 свечей.")
        return parsed
    if field_name == "max_auto_pairs":
        parsed = _parse_positive_int(value, "Количество авто-пар должно быть целым числом.")
        if parsed < 1 or parsed > 100:
            raise ValueError("Количество авто-пар должно быть от 1 до 100.")
        return parsed
    if field_name == "search_mode":
        if value not in {"standard", "aggressive"}:
            raise ValueError("Режим поиска должен быть standard или aggressive.")
        return value
    if field_name == "extremum_sensitivity":
        if value not in {"strict", "standard", "aggressive"}:
            raise ValueError("Чувствительность должна быть strict, standard или aggressive.")
        return value
    if field_name in {"notifications_enabled", "manual_check_explain_rejections"}:
        if value == "Включить":
            return True
        if value == "Выключить":
            return False
        raise ValueError("Выберите Включить или Выключить.")
    raise ValueError("Параметр не поддерживается.")


def _parse_positive_int(raw_value: str, error_message: str) -> int:
    """Parse an integer value and return a user-friendly error when it is invalid."""

    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(error_message) from error


def _build_manual_signal_signature(app_context: ApplicationContext, result) -> str:
    """Build a deterministic history signature for manual check results."""

    if result.best_candidate is not None and result.validation_result is not None:
        return app_context.notification_message_service.build_signal_signature(
            result.best_candidate,
            result.validation_result,
        )
    return f"manual:{result.symbol}:{result.timeframe}:{result.status}"


def _cleanup_chart_file(chart_path: Path | None) -> None:
    """Delete temporary rendered chart files after Telegram delivery."""

    if chart_path is None:
        return
    try:
        chart_path.unlink(missing_ok=True)
    except OSError:
        return
