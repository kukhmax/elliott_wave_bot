"""Finite-state definitions for Telegram multi-step scenarios."""

from aiogram.fsm.state import State, StatesGroup


class AddPairStates(StatesGroup):
    """Conversation states used while adding a new trading pair."""

    waiting_for_symbol = State()
    waiting_for_timeframe = State()


class ChangeTimeframeStates(StatesGroup):
    """Conversation states used while changing the timeframe of a pair."""

    waiting_for_symbol = State()
    waiting_for_timeframe = State()


class DeletePairStates(StatesGroup):
    """Conversation states used while removing a pair from the watchlist."""

    waiting_for_symbol = State()


class ManualCheckStates(StatesGroup):
    """Conversation states used while running a manual analytical check."""

    waiting_for_symbol = State()
    waiting_for_timeframe = State()


class SettingsStates(StatesGroup):
    """Conversation states used while editing bot settings."""

    waiting_for_setting = State()
    waiting_for_value = State()
