"""Application context shared between Telegram handlers and core services."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram.types import FSInputFile
from elliott_bot.domain.models import (
    EventCategory,
    MonitoringStatus,
    PairSourceOrigin,
    PairStatus,
    RuntimeState,
    ServiceEvent,
    SignalRecord,
    SignalStatus,
    WatchlistState,
)
from elliott_bot.orchestration.monitoring_coordinator import MonitoringCoordinator
from elliott_bot.services.chart_rendering_service import ChartRenderingService
from elliott_bot.services.elliott_validation_service import ElliottValidationService
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.manual_check_service import ManualCheckService
from elliott_bot.services.market_data_service import MarketDataService
from elliott_bot.services.market_universe_service import MarketUniverseService
from elliott_bot.services.runtime_state_service import RuntimeStateService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.settings_service import SettingsService
from elliott_bot.services.signal_history_service import SignalHistoryService
from elliott_bot.services.notification_message_service import NotificationMessageService
from elliott_bot.services.symbol_mapping_service import SymbolMappingService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.services.watchlist_service import WatchlistService
from elliott_bot.shared.config import AppSettings
from elliott_bot.shared.logging import get_logger
from elliott_bot.storage.file_storage import FileStorage

if TYPE_CHECKING:
    from aiogram import Bot


@dataclass(slots=True)
class ApplicationContext:
    """Bundle mutable application state together with the services that manage it."""

    settings: AppSettings
    runtime_state: RuntimeState
    watchlist_state: WatchlistState
    signal_history: list[SignalRecord]
    storage: FileStorage
    settings_service: SettingsService
    runtime_state_service: RuntimeStateService
    watchlist_service: WatchlistService
    signal_history_service: SignalHistoryService
    monitoring_coordinator: MonitoringCoordinator
    symbol_mapping_service: SymbolMappingService
    market_universe_service: MarketUniverseService
    market_data_service: MarketDataService
    series_preparation_service: SeriesPreparationService
    extremum_detection_service: ExtremumDetectionService
    wave_analysis_service: WaveAnalysisService
    elliott_validation_service: ElliottValidationService
    manual_check_service: ManualCheckService
    chart_rendering_service: ChartRenderingService
    notification_message_service: NotificationMessageService
    telegram_bot: Bot | None = None
    monitoring_task: asyncio.Task[None] | None = None
    subscribed_chat_ids: set[int] = field(default_factory=set)
    transient_message_ttl_seconds: int = 15

    @property
    def active_pairs_count(self) -> int:
        """Return the number of active tracked pairs."""

        return len([pair for pair in self.watchlist_state.pairs if pair.status == PairStatus.ACTIVE])

    def start_monitoring(self) -> RuntimeState:
        """Move monitoring into the running state and persist it."""

        self.runtime_state = self.monitoring_coordinator.start(self.runtime_state)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self.runtime_state

        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(
                self.run_monitoring_loop(),
                name="elliott-bot-monitoring-loop",
            )
            get_logger("elliott_bot.monitoring.loop").info("Monitoring scan loop task started.")
        return self.runtime_state

    def stop_monitoring(self) -> RuntimeState:
        """Move monitoring into the stopped state and persist it."""

        self.runtime_state = self.monitoring_coordinator.stop(self.runtime_state)
        if self.monitoring_task is not None and not self.monitoring_task.done():
            self.monitoring_task.cancel()
        self.monitoring_task = None
        return self.runtime_state

    def persist_watchlist(self) -> None:
        """Persist the current in-memory watchlist state."""

        self.watchlist_service.save(self.watchlist_state)

    def persist_settings(self) -> None:
        """Persist the current in-memory settings snapshot."""

        self.settings_service.save(self.settings)

    def persist_signal_history(self) -> None:
        """Persist the current in-memory signal history."""

        self.signal_history_service.save(self.signal_history)

    def record_signal_decision(
        self,
        *,
        signal_signature: str,
        symbol: str,
        timeframe: str,
        direction: str,
        status: SignalStatus,
        sent_to_telegram: bool,
        duplicate_of: str | None = None,
        suppressed_reason: str | None = None,
    ) -> None:
        """Append and persist a new signal-history decision record."""

        self.signal_history = self.signal_history_service.register_decision(
            self.signal_history,
            signal_signature=signal_signature,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            status=status,
            sent_to_telegram=sent_to_telegram,
            duplicate_of=duplicate_of,
            suppressed_reason=suppressed_reason,
        )
        self.persist_signal_history()

    def update_setting(self, field_name: str, value: object) -> None:
        """Validate, apply and persist a settings update."""

        self.settings = self.settings_service.update(self.settings, field_name, value)

    def attach_bot(self, bot: Bot | None) -> None:
        """Attach the Telegram bot instance used for outbound notifications."""

        self.telegram_bot = bot

    def register_chat(self, chat_id: int) -> None:
        """Register a Telegram chat as an eligible destination for summaries."""

        self.subscribed_chat_ids.add(chat_id)

    async def send_temporary_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: object | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Send a short-lived informational message when a bot instance is available."""

        if self.telegram_bot is None:
            return
        sent_message = await self.telegram_bot.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        self.schedule_message_cleanup(
            chat_id,
            sent_message.message_id,
            ttl_seconds=ttl_seconds or self.transient_message_ttl_seconds,
        )

    def schedule_message_cleanup(self, chat_id: int, message_id: int, *, ttl_seconds: int) -> None:
        """Schedule deletion of a transient Telegram message."""

        if self.telegram_bot is None:
            return
        asyncio.create_task(
            self._delete_message_later(chat_id, message_id, ttl_seconds),
            name=f"elliott-bot-delete-message-{message_id}",
        )

    async def shutdown(self) -> None:
        """Cancel background monitoring when the application stops."""

        if self.monitoring_task is not None and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitoring_task
        self.monitoring_task = None

    async def ensure_auto_watchlist(self) -> dict[str, object]:
        """Populate the automatic watchlist from CMC and exchange symbols if needed."""

        target_auto_pairs = self.settings.max_auto_pairs
        active_auto_symbols = {
            pair.symbol
            for pair in self.watchlist_state.pairs
            if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
        }
        if len(active_auto_symbols) >= target_auto_pairs:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": None,
            }

        available_symbols, symbols_error = await self.market_data_service.load_available_symbols()
        if symbols_error is not None:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": symbols_error.message,
            }

        matched_symbols, unmatched_assets, universe_error = await self.market_universe_service.load_watchlist_candidates(
            available_symbols,
            target_count=target_auto_pairs,
        )
        if universe_error is not None:
            return {
                "added_count": 0,
                "active_auto_pairs": len(active_auto_symbols),
                "active_total_pairs": self.active_pairs_count,
                "unmatched_assets": 0,
                "error_message": universe_error.message,
            }

        existing_active_symbols = {
            pair.symbol
            for pair in self.watchlist_state.pairs
            if pair.status == PairStatus.ACTIVE
        }
        added_count = 0
        for symbol in matched_symbols:
            current_auto_count = len(
                [
                    pair
                    for pair in self.watchlist_state.pairs
                    if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
                ]
            )
            if current_auto_count >= target_auto_pairs:
                break
            if symbol in existing_active_symbols:
                continue

            quote_asset = self.settings.default_quote_asset
            base_asset = symbol[: -len(quote_asset)] if symbol.endswith(quote_asset) else symbol
            self.watchlist_state = self.watchlist_service.ensure_pair(
                state=self.watchlist_state,
                settings=self.settings,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                source_origin=PairSourceOrigin.AUTO,
            )
            existing_active_symbols.add(symbol)
            added_count += 1

        if added_count > 0:
            self.persist_watchlist()

        active_auto_count = len(
            [
                pair
                for pair in self.watchlist_state.pairs
                if pair.status == PairStatus.ACTIVE and pair.source_origin == PairSourceOrigin.AUTO
            ]
        )
        return {
            "added_count": added_count,
            "active_auto_pairs": active_auto_count,
            "active_total_pairs": self.active_pairs_count,
            "unmatched_assets": len(unmatched_assets),
            "error_message": None,
        }

    async def run_monitoring_loop(self) -> None:
        """Continuously execute scan cycles while monitoring stays in the running state."""

        logger = get_logger("elliott_bot.monitoring.loop")
        try:
            while self.runtime_state.monitoring_status == MonitoringStatus.RUNNING:
                cycle_summary = await self.run_monitoring_cycle()
                await self.broadcast_scan_summary(cycle_summary)
                if self.runtime_state.monitoring_status != MonitoringStatus.RUNNING:
                    break

                wait_seconds = self.settings.scan_interval_seconds
                logger.info("Next scan cycle scheduled in %s seconds.", wait_seconds)
                self.storage.append_event(
                    ServiceEvent(
                        level="INFO",
                        module=self.__class__.__name__,
                        event_type="scan_cycle_waiting",
                        message="Next monitoring scan cycle scheduled.",
                        category=EventCategory.SYSTEM,
                        context={"wait_seconds": wait_seconds},
                    )
                )
                await asyncio.sleep(wait_seconds)
                logger.info("Restarting monitoring scan cycle after wait interval.")
        except asyncio.CancelledError:
            logger.info("Monitoring scan loop cancelled.")
            raise
        finally:
            self.monitoring_task = None

    async def run_monitoring_cycle(self) -> dict[str, int]:
        """Run a full scan cycle across the active watchlist."""

        logger = get_logger("elliott_bot.monitoring.loop")
        active_pairs = [pair for pair in self.watchlist_state.pairs if pair.status == PairStatus.ACTIVE]
        config_map = {config.symbol: config for config in self.watchlist_state.configs if config.scan_enabled}
        active_configs = [
            config_map[pair.symbol]
            for pair in active_pairs
            if pair.symbol in config_map
        ]
        active_configs.sort(key=lambda item: item.priority)

        summary = {
            "checked_pairs": 0,
            "confirmed_count": 0,
            "probable_count": 0,
            "rejected_count": 0,
            "error_count": 0,
            "duplicate_count": 0,
            "sent_count": 0,
        }
        self.runtime_state.current_cycle_started_at = datetime.now(timezone.utc).isoformat()
        self.runtime_state.queue_size = len(active_configs)
        self.runtime_state.current_pair = None
        self.runtime_state_service.save(self.runtime_state)
        self.storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="scan_cycle_started",
                message="Monitoring scan cycle started.",
                category=EventCategory.ANALYSIS,
                context={"pairs_count": len(active_configs)},
            )
        )
        logger.info("Monitoring scan cycle started. pairs=%s", len(active_configs))

        for index, config in enumerate(active_configs, start=1):
            if self.runtime_state.monitoring_status != MonitoringStatus.RUNNING:
                break

            self.runtime_state.current_pair = config.symbol
            self.runtime_state.queue_size = len(active_configs) - index + 1
            self.runtime_state_service.save(self.runtime_state)
            logger.info(
                "Scanning pair %s (%s/%s) timeframe=%s history=%s",
                config.symbol,
                index,
                len(active_configs),
                config.timeframe,
                config.history_depth,
            )
            self.storage.append_event(
                ServiceEvent(
                    level="INFO",
                    module=self.__class__.__name__,
                    event_type="scan_pair_started",
                    message="Monitoring scan started for a pair.",
                    category=EventCategory.ANALYSIS,
                    context={
                        "symbol": config.symbol,
                        "position": index,
                        "total_pairs": len(active_configs),
                        "timeframe": config.timeframe,
                    },
                )
            )
            try:
                result = await self.manual_check_service.run(symbol=config.symbol, timeframe=config.timeframe)
                checked_at = datetime.now(timezone.utc).isoformat()
                config.last_checked_at = checked_at
                summary["checked_pairs"] += 1

                if result.status == SignalStatus.CONFIRMED.value:
                    summary["confirmed_count"] += 1
                elif result.status == SignalStatus.PROBABLE.value:
                    summary["probable_count"] += 1
                else:
                    summary["rejected_count"] += 1

                duplicate_record = None
                signal_signature = None
                if result.best_candidate is not None and result.validation_result is not None:
                    signal_signature = self.notification_message_service.build_signal_signature(
                        result.best_candidate,
                        result.validation_result,
                    )
                    duplicate_record = self.signal_history_service.find_duplicate(
                        self.signal_history,
                        signal_signature,
                    )

                sent_to_telegram = False
                suppressed_reason = result.summary if result.status == SignalStatus.REJECTED.value else None
                duplicate_of = None
                if signal_signature is not None and duplicate_record is not None and duplicate_record.sent_to_telegram:
                    summary["duplicate_count"] += 1
                    duplicate_of = duplicate_record.signal_id
                    suppressed_reason = "duplicate_signal"
                    logger.info("Duplicate signal skipped for %s signature=%s", config.symbol, signal_signature)
                elif result.status in {SignalStatus.CONFIRMED.value, SignalStatus.PROBABLE.value}:
                    sent_to_telegram = await self.broadcast_scan_result(result)
                    if sent_to_telegram:
                        summary["sent_count"] += 1
                        config.last_signal_at = checked_at
                        config.last_signal_signature = signal_signature

                if signal_signature is not None:
                    self.record_signal_decision(
                        signal_signature=signal_signature,
                        symbol=result.symbol,
                        timeframe=result.timeframe,
                        direction=result.best_candidate.direction.value if result.best_candidate is not None else "unknown",
                        status=SignalStatus(result.status),
                        sent_to_telegram=sent_to_telegram,
                        duplicate_of=duplicate_of,
                        suppressed_reason=suppressed_reason,
                    )

                logger.info(
                    "Scan result for %s timeframe=%s status=%s sent=%s",
                    config.symbol,
                    config.timeframe,
                    result.status,
                    sent_to_telegram,
                )
                self.storage.append_event(
                    ServiceEvent(
                        level="INFO",
                        module=self.__class__.__name__,
                        event_type="scan_pair_completed",
                        message="Monitoring scan finished for a pair.",
                        category=EventCategory.ANALYSIS,
                        context={
                            "symbol": config.symbol,
                            "timeframe": config.timeframe,
                            "status": result.status,
                            "sent_to_telegram": sent_to_telegram,
                        },
                    )
                )
            except Exception as error:
                summary["error_count"] += 1
                self.runtime_state.last_error = str(error)
                logger.exception("Monitoring scan failed for %s: %s", config.symbol, error)
                self.storage.append_event(
                    ServiceEvent(
                        level="ERROR",
                        module=self.__class__.__name__,
                        event_type="scan_pair_failed",
                        message="Monitoring scan failed for a pair.",
                        category=EventCategory.ANALYSIS,
                        reason_code="scan_pair_failed",
                        context={"symbol": config.symbol, "details": str(error)},
                    )
                )

        self.persist_watchlist()
        self.runtime_state.current_pair = None
        self.runtime_state.queue_size = 0
        self.runtime_state_service.save(self.runtime_state)
        logger.info(
            "Monitoring scan cycle completed. checked=%s confirmed=%s probable=%s rejected=%s duplicates=%s errors=%s",
            summary["checked_pairs"],
            summary["confirmed_count"],
            summary["probable_count"],
            summary["rejected_count"],
            summary["duplicate_count"],
            summary["error_count"],
        )
        self.storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="scan_cycle_completed",
                message="Monitoring scan cycle completed.",
                category=EventCategory.ANALYSIS,
                context=summary,
            )
        )
        return summary

    async def broadcast_scan_result(self, result) -> bool:
        """Broadcast a detected scan result to subscribed Telegram chats."""

        if self.telegram_bot is None or not self.subscribed_chat_ids or result.best_candidate is None or result.validation_result is None:
            return False

        caption = self.notification_message_service.build_signal_alert_caption(
            result.best_candidate,
            result.validation_result,
        )
        chart_path = self.chart_rendering_service.render_manual_check_chart(result)
        delivered = False
        try:
            for chat_id in self.subscribed_chat_ids:
                if chart_path is not None:
                    await self.telegram_bot.send_photo(chat_id, photo=FSInputFile(chart_path), caption=caption)
                else:
                    await self.telegram_bot.send_message(chat_id, caption)
                delivered = True
        finally:
            if chart_path is not None:
                with contextlib.suppress(OSError):
                    Path(chart_path).unlink(missing_ok=True)
        return delivered

    async def broadcast_scan_summary(self, summary: dict[str, int]) -> None:
        """Send a short-lived summary after each completed scan cycle."""

        if self.telegram_bot is None or not self.subscribed_chat_ids:
            return

        text = (
            "🔄 Цикл сканирования завершен.\n"
            f"📌 Проверено пар: {summary['checked_pairs']}\n"
            f"✅ Confirmed: {summary['confirmed_count']}\n"
            f"🟡 Probable: {summary['probable_count']}\n"
            f"⚪ Rejected: {summary['rejected_count']}\n"
            f"♻️ Дубликатов: {summary['duplicate_count']}\n"
            f"🚨 Ошибок: {summary['error_count']}\n"
            f"📤 Отправлено сигналов: {summary['sent_count']}"
        )
        for chat_id in self.subscribed_chat_ids:
            sent_message = await self.telegram_bot.send_message(chat_id, text)
            self.schedule_message_cleanup(chat_id, sent_message.message_id, ttl_seconds=45)

    async def _delete_message_later(self, chat_id: int, message_id: int, ttl_seconds: int) -> None:
        """Delete a Telegram message after a short delay."""

        if self.telegram_bot is None:
            return
        await asyncio.sleep(ttl_seconds)
        with contextlib.suppress(Exception):
            await self.telegram_bot.delete_message(chat_id, message_id)
