"""Detection of local market extremums used for early wave analysis."""

from __future__ import annotations

from elliott_bot.domain.models import ExtremumKind, ExtremumPoint, MarketSeries
from elliott_bot.shared.logging import get_logger


class ExtremumDetectionService:
    """Detect local high and low pivot points from normalized OHLCV data."""

    WINDOW_BY_SENSITIVITY = {
        "strict": 2,
        "standard": 1,
        "aggressive": 1,
    }

    MIN_STRENGTH_BY_SENSITIVITY = {
        "strict": 0.015,
        "standard": 0.008,
        "aggressive": 0.003,
    }

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def detect(self, series: MarketSeries, sensitivity: str) -> list[ExtremumPoint]:
        """Detect a cleaned list of local extremums from a market series."""

        window = self.WINDOW_BY_SENSITIVITY.get(sensitivity, 1)
        min_strength = self.MIN_STRENGTH_BY_SENSITIVITY.get(sensitivity, 0.008)
        bars = series.bars
        raw_extremums: list[ExtremumPoint] = []

        for index in range(window, len(bars) - window):
            current_bar = bars[index]
            left_bars = bars[index - window : index]
            right_bars = bars[index + 1 : index + 1 + window]

            if all(current_bar.high >= bar.high for bar in left_bars + right_bars):
                strength = self._calculate_strength(current_bar.high, left_bars[-1].close, right_bars[0].close)
                if strength >= min_strength:
                    raw_extremums.append(
                        ExtremumPoint(
                            index=index,
                            timestamp=current_bar.close_time,
                            price=current_bar.high,
                            kind=ExtremumKind.HIGH,
                            strength=strength,
                            bar_distance_from_previous=0,
                        )
                    )

            if all(current_bar.low <= bar.low for bar in left_bars + right_bars):
                strength = self._calculate_strength(current_bar.low, left_bars[-1].close, right_bars[0].close)
                if strength >= min_strength:
                    raw_extremums.append(
                        ExtremumPoint(
                            index=index,
                            timestamp=current_bar.close_time,
                            price=current_bar.low,
                            kind=ExtremumKind.LOW,
                            strength=strength,
                            bar_distance_from_previous=0,
                        )
                    )

        cleaned = self._clean_extremums(raw_extremums)
        self._logger.info("Detected %s cleaned extremums for %s %s.", len(cleaned), series.symbol, series.timeframe)
        return cleaned

    @staticmethod
    def _calculate_strength(extreme_price: float, left_close: float, right_close: float) -> float:
        """Calculate the relative strength of an extremum candidate."""

        baseline = max(abs(left_close), abs(right_close), 1e-9)
        return max(abs(extreme_price - left_close), abs(extreme_price - right_close)) / baseline

    def _clean_extremums(self, raw_extremums: list[ExtremumPoint]) -> list[ExtremumPoint]:
        """Collapse consecutive same-type extremums into a stable alternating sequence."""

        raw_extremums.sort(key=lambda item: item.index)
        cleaned: list[ExtremumPoint] = []

        for candidate in raw_extremums:
            if not cleaned:
                candidate.bar_distance_from_previous = 0
                cleaned.append(candidate)
                continue

            previous = cleaned[-1]
            if candidate.kind == previous.kind:
                replacement = self._pick_stronger_extremum(previous, candidate)
                replacement.bar_distance_from_previous = previous.bar_distance_from_previous
                cleaned[-1] = replacement
                continue

            candidate.bar_distance_from_previous = candidate.index - previous.index
            cleaned.append(candidate)

        return cleaned

    @staticmethod
    def _pick_stronger_extremum(first: ExtremumPoint, second: ExtremumPoint) -> ExtremumPoint:
        """Keep the stronger or more extreme point when kinds collide consecutively."""

        if first.kind == ExtremumKind.HIGH:
            return first if first.price >= second.price else second
        return first if first.price <= second.price else second
