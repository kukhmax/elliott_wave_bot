"""PNG chart rendering for manual checks and future notifications."""

from __future__ import annotations

from pathlib import Path

from elliott_bot.services.manual_check_service import ManualCheckResult
from elliott_bot.shared.config import AppSettings
from elliott_bot.shared.logging import get_logger


class ChartRenderingService:
    """Render wave-analysis results into PNG images for Telegram delivery."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._logger = get_logger(self.__class__.__name__)

    @property
    def _charts_directory(self) -> Path:
        """Return the storage-backed directory used for rendered chart files."""

        directory = self._settings.resolved_storage_path() / "rendered_charts"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def render_manual_check_chart(self, result: ManualCheckResult) -> Path | None:
        """Render a manual-check result into a PNG chart file when possible."""

        if result.best_candidate is None or result.market_series is None or result.status == "rejected":
            self._logger.info("Chart rendering skipped because candidate or series is missing.")
            return None

        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            closes = [bar.close for bar in result.market_series.bars]
            figure, axis = plt.subplots(figsize=(12, 6), dpi=140)
            axis.plot(range(len(closes)), closes, color="#3B82F6", linewidth=1.8)
            axis.set_facecolor("#0F172A")
            figure.patch.set_facecolor("#0F172A")
            axis.tick_params(colors="#E2E8F0")
            for spine in axis.spines.values():
                spine.set_color("#475569")

            candidate = result.best_candidate
            pivot_points = [
                ("P0", candidate.points.p0),
                ("P1", candidate.points.p1),
                ("P2", candidate.points.p2),
                ("P3", candidate.points.p3),
                ("P4", candidate.points.p4),
                ("P5", candidate.points.p5),
            ]
            wave_labels = ["1", "2", "3", "4", "5"]

            x_values = [point.index for _, point in pivot_points]
            y_values = [point.price for _, point in pivot_points]
            axis.plot(x_values, y_values, color="#F59E0B", linewidth=2.4, marker="o", markersize=5)

            for label, point in pivot_points:
                axis.annotate(
                    label,
                    (point.index, point.price),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                    color="#F8FAFC",
                    fontsize=9,
                    fontweight="bold",
                )

            for index, label in enumerate(wave_labels):
                midpoint_x = (x_values[index] + x_values[index + 1]) / 2
                midpoint_y = (y_values[index] + y_values[index + 1]) / 2
                axis.annotate(
                    label,
                    (midpoint_x, midpoint_y),
                    textcoords="offset points",
                    xytext=(0, -12),
                    ha="center",
                    color="#22C55E",
                    fontsize=10,
                    fontweight="bold",
                )

            title = (
                f"{result.symbol} | {result.timeframe} | {candidate.direction.value} | "
                f"{result.status}"
            )
            subtitle = result.validation_result.diagnostic_summary if result.validation_result is not None else result.summary
            axis.set_title(title, color="#F8FAFC", fontsize=13, pad=16)
            axis.text(
                0.01,
                0.02,
                subtitle,
                transform=axis.transAxes,
                fontsize=9,
                color="#CBD5E1",
                bbox={"facecolor": "#1E293B", "edgecolor": "#334155", "boxstyle": "round,pad=0.4"},
            )
            axis.set_xlabel("Bars", color="#CBD5E1")
            axis.set_ylabel("Price", color="#CBD5E1")
            figure.tight_layout()

            file_name = f"{candidate.candidate_id}-{result.status}.png".replace("/", "_")
            file_path = self._charts_directory / file_name
            figure.savefig(file_path, format="png")
            plt.close(figure)
            self._logger.info("Manual check chart rendered to %s.", file_path)
            return file_path
        except Exception as error:
            self._logger.error("Failed to render manual check chart: %s", error)
            return None
