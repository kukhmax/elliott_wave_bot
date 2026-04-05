"""Symbol mapping utilities for converting market assets into exchange symbols."""

from __future__ import annotations

from elliott_bot.domain.models import ServiceEvent
from elliott_bot.shared.config import AppSettings
from elliott_bot.storage.file_storage import FileStorage


class SymbolMappingService:
    """Map canonical assets into exchange-ready trading pairs."""

    DEFAULT_STABLECOINS = {
        "USDT",
        "USDC",
        "BUSD",
        "DAI",
        "TUSD",
        "FDUSD",
        "USDE",
        "USDP",
    }

    def __init__(self, settings: AppSettings, storage: FileStorage) -> None:
        self._settings = settings
        self._storage = storage

    def filter_assets(self, assets: list[str]) -> list[str]:
        """Remove duplicates and stablecoins from canonical asset symbols."""

        filtered: list[str] = []
        seen: set[str] = set()
        for asset in assets:
            normalized = asset.upper().strip()
            if not normalized or normalized in self.DEFAULT_STABLECOINS or normalized in seen:
                continue
            filtered.append(normalized)
            seen.add(normalized)

        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="assets_filtered",
                message="Canonical asset list filtered before symbol mapping.",
                context={"input_count": len(assets), "output_count": len(filtered)},
            )
        )
        return filtered

    def build_symbol(self, asset: str) -> str:
        """Build a target exchange symbol using the default quote asset."""

        return f"{asset.upper().strip()}{self._settings.default_quote_asset}"

    def map_assets_to_symbols(self, assets: list[str], available_symbols: set[str]) -> tuple[list[str], list[str]]:
        """Map assets to exchange symbols and split matched and unmatched assets."""

        matched_symbols: list[str] = []
        unmatched_assets: list[str] = []

        for asset in self.filter_assets(assets):
            candidate = self.build_symbol(asset)
            if candidate in available_symbols:
                matched_symbols.append(candidate)
            else:
                unmatched_assets.append(asset)

        self._storage.append_event(
            ServiceEvent(
                level="INFO",
                module=self.__class__.__name__,
                event_type="assets_mapped_to_symbols",
                message="Canonical assets mapped to exchange symbols.",
                context={
                    "matched_count": len(matched_symbols),
                    "unmatched_count": len(unmatched_assets),
                },
            )
        )
        return matched_symbols, unmatched_assets
