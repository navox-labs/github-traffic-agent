"""Tests for the analyze skill."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.skills.analyze import analyze


def _generate_traffic_data(days: int, base_count: int = 10) -> list[dict]:
    """Generate synthetic traffic data."""
    records = []
    start = date(2026, 5, 1)
    for i in range(days):
        d = start + timedelta(days=i)
        count = base_count + (i % 5)  # Small variation
        records.append({"date": str(d), "count": count, "uniques": count // 2})
    return records


def test_analyze_with_sufficient_data(tmp_data_dir: str):
    base = Path(tmp_data_dir) / "memory"
    base.mkdir(parents=True, exist_ok=True)

    data = _generate_traffic_data(30)
    (base / "views.json").write_text(json.dumps(data))
    (base / "clones.json").write_text(json.dumps(data))

    result = analyze("test/repo", tmp_data_dir)

    assert result.repo == "test/repo"
    assert len(result.views_df) == 30
    assert len(result.trends) >= 1  # At least 7-day trend


def test_analyze_with_anomaly(tmp_data_dir: str):
    base = Path(tmp_data_dir) / "memory"
    base.mkdir(parents=True, exist_ok=True)

    data = _generate_traffic_data(30, base_count=10)
    # Inject a spike
    data[15]["count"] = 100

    (base / "views.json").write_text(json.dumps(data))
    (base / "clones.json").write_text(json.dumps(data))

    result = analyze("test/repo", tmp_data_dir)
    view_anomalies = [a for a in result.anomalies if a.metric == "views"]
    assert len(view_anomalies) >= 1
    assert view_anomalies[0].direction == "spike"


def test_analyze_empty_data(tmp_data_dir: str):
    result = analyze("test/repo", tmp_data_dir)
    assert len(result.views_df) == 0
    assert len(result.trends) == 0
    assert len(result.anomalies) == 0
