"""Telegram handlers for the current management scenarios."""

from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from elliott_bot.domain.models import MonitoringStatus, PairSourceOrigin, PairStatus, SignalStatus
from elliott_bot.interfaces.telegram.keyboards import (
    build_cancel_keyboard,
    build_main_menu_keyboard,
    build_timeframe_keyboard,
)
from elliott_bot.interfaces.telegram.presenters import (
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

    app_context.start_monitoring()
    LOGGER.info("Monitoring started from Telegram command.")
    await message.answer(
        "🚀 Мониторинг запущен.\n"
        f"📌 Отслеживаемых пар: {app_context.active_pairs_count}\n"
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
async def handle_settings(message: Message, app_context: ApplicationContext) -> None:
    """Show the current application settings."""

    await message.answer(format_settings_text(app_context), reply_markup=_main_menu(app_context))


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
        reply_markup=build_timeframe_keyboard(),
    )


@router.message(ManualCheckStates.waiting_for_timeframe)
async def handle_manual_check_timeframe(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Run the manual check once the symbol and timeframe are available."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer("⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.", reply_markup=build_timeframe_keyboard())
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
        reply_markup=build_timeframe_keyboard(),
    )


@router.message(AddPairStates.waiting_for_timeframe)
async def handle_add_pair_timeframe(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Persist the new pair using the selected or default timeframe."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer("⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.", reply_markup=build_timeframe_keyboard())
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
    await message.answer("⏱ Выберите новый таймфрейм.", reply_markup=build_timeframe_keyboard())


@router.message(ChangeTimeframeStates.waiting_for_timeframe)
async def handle_change_timeframe_value(message: Message, app_context: ApplicationContext, state: FSMContext) -> None:
    """Persist the new timeframe for the selected pair."""

    timeframe = normalize_timeframe(message.text or "", app_context.settings.default_timeframe)
    if not is_supported_timeframe(timeframe):
        await message.answer("⚠️ Таймфрейм не поддерживается. Выберите один из предложенных.", reply_markup=build_timeframe_keyboard())
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
