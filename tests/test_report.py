"""Tests for the report skill."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.models.schemas import Prediction, Proposal, TrendData
from src.skills.analyze import AnalysisResult
from src.skills.report import generate_report


def test_generate_report(tmp_data_dir: str):
    views_data = [
        {"date": str(date(2026, 5, 25) + timedelta(days=i)), "count": 10 + i, "uniques": 5 + i}
        for i in range(7)
    ]
    views_df = pd.DataFrame(views_data)
    views_df["date"] = pd.to_datetime(views_df["date"]).dt.date

    clones_df = views_df.copy()

    analysis = AnalysisResult(
        repo="test/repo",
        views_df=views_df,
        clones_df=clones_df,
        trends=[
            TrendData(
                period="7-day",
                avg_daily_views=13.0,
                avg_daily_clones=13.0,
                views_growth_pct=10.5,
                clones_growth_pct=5.2,
            )
        ],
        top_referrers=[{"name": "github.com", "total_count": 50}],
        top_paths=[{"name": "/test/repo", "total_count": 30}],
    )

    predictions = [
        Prediction(
            date=date(2026, 6, 2),
            metric="views",
            predicted=15.0,
            lower_bound=10.0,
            upper_bound=20.0,
        )
    ]

    proposals = [
        Proposal(
            title="Update README",
            description="Consider refreshing the README.",
            confidence=0.8,
            trigger="test",
        )
    ]

    report_path = generate_report("test/repo", tmp_data_dir, analysis, predictions, proposals)

    assert Path(report_path).exists()
    content = Path(report_path).read_text()
    assert "# Traffic Report: test/repo" in content
    assert "## Summary" in content
    assert "## Trends" in content
    assert "## Top Referrers" in content
    assert "## Predictions" in content
    assert "## Proposals" in content
    assert "Update README" in content
