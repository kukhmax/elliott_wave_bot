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

        if result.market_series is None:
            self._logger.info("Chart rendering skipped because market series is missing.")
            return None

        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo

            bars = result.market_series.bars
            tz_label = self._settings.chart_timezone
            if tz_label == "local":
                chart_tz = datetime.now().astimezone().tzinfo
                tz_label = str(chart_tz)
            else:
                chart_tz = ZoneInfo(tz_label)

            dates = [datetime.fromtimestamp(b.open_time / 1000.0, tz=chart_tz) for b in bars]
            x_values = mdates.date2num(dates)

            closes = [b.close for b in bars]
            opens = [b.open for b in bars]
            highs = [b.high for b in bars]
            lows = [b.low for b in bars]

            figure, axis = plt.subplots(figsize=(12, 6), dpi=140)
            axis.set_facecolor("#0F172A")
            figure.patch.set_facecolor("#0F172A")
            axis.tick_params(colors="#E2E8F0")
            for spine in axis.spines.values():
                spine.set_color("#475569")

            if len(x_values) > 1:
                width = (x_values[1] - x_values[0]) * 0.8
            else:
                width = 0.001

            up = [c >= o for c, o in zip(closes, opens)]
            down = [c < o for c, o in zip(closes, opens)]

            up_x = [x for x, u in zip(x_values, up) if u]
            up_opens = [o for o, u in zip(opens, up) if u]
            up_closes = [c for c, u in zip(closes, up) if u]
            up_highs = [h for h, u in zip(highs, up) if u]
            up_lows = [l for l, u in zip(lows, up) if u]

            if up_x:
                axis.vlines(up_x, up_lows, up_highs, color="#22C55E", linewidth=1)
                axis.bar(up_x, [c - o for c, o in zip(up_closes, up_opens)], bottom=up_opens, width=width, color="#22C55E", edgecolor="#22C55E")

            down_x = [x for x, d in zip(x_values, down) if d]
            down_opens = [o for o, d in zip(opens, down) if d]
            down_closes = [c for c, d in zip(closes, down) if d]
            down_highs = [h for h, d in zip(highs, down) if d]
            down_lows = [l for l, d in zip(lows, down) if d]

            if down_x:
                axis.vlines(down_x, down_lows, down_highs, color="#EF4444", linewidth=1)
                axis.bar(down_x, [o - c for c, o in zip(down_closes, down_opens)], bottom=down_closes, width=width, color="#EF4444", edgecolor="#EF4444")

            axis.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M", tz=chart_tz))
            figure.autofmt_xdate()

            candidate = result.best_candidate
            if candidate is not None:
                pivot_points = [
                    ("P0", candidate.points.p0),
                    ("P1", candidate.points.p1),
                    ("P2", candidate.points.p2),
                    ("P3", candidate.points.p3),
                    ("P4", candidate.points.p4),
                    ("P5", candidate.points.p5),
                ]
                wave_labels = ["1", "2", "3", "4", "5"]

                pivot_x_values = [x_values[point.index] for _, point in pivot_points]
                pivot_y_values = [point.price for _, point in pivot_points]
                axis.plot(pivot_x_values, pivot_y_values, color="#F59E0B", linewidth=2.4, marker="o", markersize=5)

                for label, point in pivot_points:
                    axis.annotate(
                        label,
                        (x_values[point.index], point.price),
                        textcoords="offset points",
                        xytext=(0, 10),
                        ha="center",
                        color="#F8FAFC",
                        fontsize=9,
                        fontweight="bold",
                    )

                for index, label in enumerate(wave_labels):
                    midpoint_x = (pivot_x_values[index] + pivot_x_values[index + 1]) / 2
                    midpoint_y = (pivot_y_values[index] + pivot_y_values[index + 1]) / 2
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
                file_name = f"{candidate.candidate_id}-{result.status}.png".replace("/", "_")
            else:
                title = f"{result.symbol} | {result.timeframe} | {result.status}"
                file_name = f"{result.symbol}-{result.timeframe}-{result.status}.png".replace("/", "_")
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
            axis.set_xlabel("Time", color="#CBD5E1")
            axis.set_ylabel("Price", color="#CBD5E1")
            figure.tight_layout()

            file_path = self._charts_directory / file_name
            figure.savefig(file_path, format="png")
            plt.close(figure)
            self._logger.info("Manual check chart rendered to %s.", file_path)
            return file_path
        except Exception as error:
            self._logger.error("Failed to render manual check chart: %s", error)
            return None
