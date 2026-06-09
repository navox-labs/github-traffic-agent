"""Tests for the propose skill."""

from __future__ import annotations

import pandas as pd

from src.models.schemas import Prediction, TrendData
from src.skills.analyze import AnalysisResult
from src.skills.propose import propose


def _make_analysis(
    views_growth: float = 0.0,
    clones_growth: float = 0.0,
    referrers: list[dict] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        repo="test/repo",
        views_df=pd.DataFrame(columns=["date", "count", "uniques"]),
        clones_df=pd.DataFrame(columns=["date", "count", "uniques"]),
        trends=[
            TrendData(
                period="7-day",
                avg_daily_views=10.0,
                avg_daily_clones=5.0,
                views_growth_pct=views_growth,
                clones_growth_pct=clones_growth,
            )
        ],
        top_referrers=referrers or [],
    )


def test_propose_views_drop():
    analysis = _make_analysis(views_growth=-40.0)
    proposals = propose(analysis, [])

    titles = [p.title for p in proposals]
    assert any("declining views" in t.lower() for t in titles)


def test_propose_clones_exceed_views():
    analysis = _make_analysis(views_growth=5.0, clones_growth=30.0)
    proposals = propose(analysis, [])

    titles = [p.title for p in proposals]
    assert any("onboarding" in t.lower() for t in titles)


def test_propose_referrer_spike():
    analysis = _make_analysis(
        referrers=[{"name": "hackernews.com", "total_count": 100}]
    )
    proposals = propose(analysis, [])

    titles = [p.title for p in proposals]
    assert any("hackernews" in t.lower() for t in titles)


def test_propose_no_issues():
    analysis = _make_analysis(views_growth=5.0, clones_growth=3.0)
    proposals = propose(analysis, [])
    assert len(proposals) == 0
