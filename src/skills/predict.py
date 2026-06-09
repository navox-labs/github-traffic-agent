"""Skill: Forecast future traffic using simple statistical methods."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from src.models.schemas import Prediction

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 30


def predict(repo: str, data_dir: str) -> list[Prediction]:
    """Forecast next 14 days of views and clones."""
    base = Path(data_dir) / "memory"
    predictions: list[Prediction] = []

    for metric in ["views", "clones"]:
        filepath = base / f"{metric}.json"
        if not filepath.exists():
            continue

        data = json.loads(filepath.read_text())
        if len(data) < MIN_HISTORY_DAYS:
            logger.info(
                "Skipping %s prediction: only %d days (need %d)",
                metric,
                len(data),
                MIN_HISTORY_DAYS,
            )
            continue

        values = np.array([d["count"] for d in data], dtype=float)
        dates = [d["date"] for d in data]
        last_date = date.fromisoformat(str(dates[-1]))

        # 7-day moving average
        ma7 = float(np.mean(values[-7:]))

        # Linear regression on last 30 days
        recent = values[-30:]
        x = np.arange(len(recent), dtype=float)
        coeffs = np.polyfit(x, recent, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])

        # Historical variance for confidence intervals
        residuals = recent - (slope * x + intercept)
        std_err = float(np.std(residuals))

        for day_offset in range(1, 15):
            future_date = last_date + timedelta(days=day_offset)
            future_x = len(recent) - 1 + day_offset

            # Blend: average of MA and regression
            regression_pred = slope * future_x + intercept
            blended = (ma7 + regression_pred) / 2
            blended = max(0, blended)  # Can't have negative traffic

            predictions.append(
                Prediction(
                    date=future_date,
                    metric=metric,
                    predicted=round(blended, 1),
                    lower_bound=round(max(0, blended - 1.96 * std_err), 1),
                    upper_bound=round(blended + 1.96 * std_err, 1),
                )
            )

    logger.info("Generated %d predictions for %s", len(predictions), repo)
    return predictions
