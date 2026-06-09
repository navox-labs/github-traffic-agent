"""Tests for the predict skill."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.skills.predict import predict


def _generate_traffic_data(days: int, base_count: int = 10) -> list[dict]:
    records = []
    start = date(2026, 4, 1)
    for i in range(days):
        d = start + timedelta(days=i)
        records.append({"date": str(d), "count": base_count + i, "uniques": (base_count + i) // 2})
    return records


def test_predict_with_sufficient_data(tmp_data_dir: str):
    base = Path(tmp_data_dir) / "memory"
    base.mkdir(parents=True, exist_ok=True)

    data = _generate_traffic_data(45)
    (base / "views.json").write_text(json.dumps(data))
    (base / "clones.json").write_text(json.dumps(data))

    predictions = predict("test/repo", tmp_data_dir)

    assert len(predictions) == 28  # 14 days x 2 metrics
    # Predictions should be positive
    assert all(p.predicted >= 0 for p in predictions)
    # Lower bound should be <= predicted <= upper bound
    assert all(p.lower_bound <= p.predicted <= p.upper_bound for p in predictions)


def test_predict_insufficient_data(tmp_data_dir: str):
    base = Path(tmp_data_dir) / "memory"
    base.mkdir(parents=True, exist_ok=True)

    data = _generate_traffic_data(15)  # Less than MIN_HISTORY_DAYS
    (base / "views.json").write_text(json.dumps(data))

    predictions = predict("test/repo", tmp_data_dir)
    assert len(predictions) == 0


def test_predict_no_data(tmp_data_dir: str):
    predictions = predict("test/repo", tmp_data_dir)
    assert len(predictions) == 0
