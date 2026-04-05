"""Manual check workflow that ties market data and early wave analysis together."""

from __future__ import annotations

from dataclasses import dataclass

from elliott_bot.domain.models import MarketDataError, WaveAnalysisResult, WaveCandidate
from elliott_bot.services.extremum_detection_service import ExtremumDetectionService
from elliott_bot.services.market_data_service import MarketDataService
from elliott_bot.services.series_preparation_service import SeriesPreparationService
from elliott_bot.services.wave_analysis_service import WaveAnalysisService
from elliott_bot.shared.config import AppSettings
from elliott_bot.shared.logging import get_logger


@dataclass(slots=True)
class ManualCheckResult:
    """Represents the outcome of a manual pair analysis request."""

    symbol: str
    timeframe: str
    status: str
    summary: str
    best_candidate: WaveCandidate | None = None
    analysis_result: WaveAnalysisResult | None = None
    error: MarketDataError | None = None


class ManualCheckService:
    """Run a manual analysis flow for a single pair and timeframe."""

    def __init__(
        self,
        settings: AppSettings,
        market_data_service: MarketDataService,
        series_preparation_service: SeriesPreparationService,
        extremum_detection_service: ExtremumDetectionService,
        wave_analysis_service: WaveAnalysisService,
    ) -> None:
        self._settings = settings
        self._market_data_service = market_data_service
        self._series_preparation_service = series_preparation_service
        self._extremum_detection_service = extremum_detection_service
        self._wave_analysis_service = wave_analysis_service
        self._logger = get_logger(self.__class__.__name__)

    async def run(self, symbol: str, timeframe: str) -> ManualCheckResult:
        """Load market data, detect extremums and return the best early wave candidate."""

        series, error = await self._market_data_service.load_market_series(
            symbol=symbol,
            timeframe=timeframe,
            limit=self._settings.default_history_depth,
        )
        if error is not None or series is None:
            message = error.message if error is not None else "Не удалось загрузить свечи."
            return ManualCheckResult(
                symbol=symbol,
                timeframe=timeframe,
                status="rejected",
                summary=message,
                error=error,
            )

        prepared_series, preparation_error = self._series_preparation_service.prepare(series)
        if preparation_error is not None or prepared_series is None:
            return ManualCheckResult(
                symbol=symbol,
                timeframe=timeframe,
                status="rejected",
                summary=preparation_error.message,
                error=preparation_error,
            )

        extremums = self._extremum_detection_service.detect(
            prepared_series,
            sensitivity=self._settings.extremum_sensitivity,
        )
        analysis_result = self._wave_analysis_service.analyze(prepared_series, extremums)

        if not analysis_result.has_candidates:
            self._logger.info("Manual check found no valid candidates for %s %s.", symbol, timeframe)
            rejected_reason = analysis_result.rejected_windows[0]["reason"] if analysis_result.rejected_windows else "no_candidates"
            return ManualCheckResult(
                symbol=symbol,
                timeframe=timeframe,
                status="rejected",
                summary=f"Не найдено валидных структур. Причина: {rejected_reason}.",
                analysis_result=analysis_result,
            )

        best_candidate = analysis_result.candidates[0]
        self._logger.info("Manual check found a candidate for %s %s.", symbol, timeframe)
        return ManualCheckResult(
            symbol=symbol,
            timeframe=timeframe,
            status="probable",
            summary="Найдена ранняя 5-волновая структура после базовой структурной фильтрации.",
            best_candidate=best_candidate,
            analysis_result=analysis_result,
        )
