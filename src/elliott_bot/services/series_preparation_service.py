"""Utilities for preparing normalized market series before analysis."""

from __future__ import annotations

from elliott_bot.domain.models import MarketDataError, MarketDataErrorCategory, MarketSeries


class SeriesPreparationService:
    """Prepare market series for deterministic downstream analysis."""

    def prepare(self, series: MarketSeries, minimum_bars: int = 7) -> tuple[MarketSeries | None, MarketDataError | None]:
        """Drop incomplete data edges and validate the minimum history depth."""

        bars = sorted(series.bars, key=lambda item: item.open_time)
        if len(bars) > 1:
            bars = bars[:-1]

        if len(bars) < minimum_bars:
            return None, MarketDataError(
                category=MarketDataErrorCategory.INSUFFICIENT_HISTORY,
                message="Недостаточно свечей для базового волнового анализа.",
                retryable=False,
                context={
                    "symbol": series.symbol,
                    "timeframe": series.timeframe,
                    "bars_count": len(bars),
                    "minimum_bars": minimum_bars,
                },
            )

        prepared = MarketSeries(
            symbol=series.symbol,
            timeframe=series.timeframe,
            bars=bars,
            loaded_at=series.loaded_at,
            source=series.source,
        )
        return prepared, None
