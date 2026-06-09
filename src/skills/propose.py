"""Skill: Generate actionable proposals based on analysis and predictions."""

from __future__ import annotations

import logging

from src.models.schemas import Prediction, Proposal
from src.skills.analyze import AnalysisResult

logger = logging.getLogger(__name__)


def propose(analysis: AnalysisResult, predictions: list[Prediction]) -> list[Proposal]:
    """Generate rule-based proposals from analysis results and predictions."""
    proposals: list[Proposal] = []

    # Check trends for significant changes
    for trend in analysis.trends:
        if trend.views_growth_pct < -30:
            proposals.append(
                Proposal(
                    title="Address declining views",
                    description=(
                        f"Views have dropped {abs(trend.views_growth_pct):.0f}% over the "
                        f"{trend.period} period. Consider updating the README, publishing a "
                        "blog post, or sharing the project on relevant communities."
                    ),
                    confidence=min(0.9, 0.5 + abs(trend.views_growth_pct) / 200),
                    trigger=f"views_drop_{trend.period}",
                )
            )

        if trend.clones_growth_pct > trend.views_growth_pct + 20:
            proposals.append(
                Proposal(
                    title="Improve onboarding for new adopters",
                    description=(
                        f"Clone growth ({trend.clones_growth_pct:+.0f}%) significantly exceeds "
                        f"view growth ({trend.views_growth_pct:+.0f}%). Users are adopting the "
                        "project. Consider improving getting-started docs, adding examples, "
                        "or creating a quickstart guide."
                    ),
                    confidence=0.7,
                    trigger=f"clone_exceeds_views_{trend.period}",
                )
            )

        if trend.views_growth_pct < -10 and trend.clones_growth_pct < -10:
            proposals.append(
                Proposal(
                    title="Promote the repository",
                    description=(
                        "Both views and clones are declining. Consider promoting the repo on "
                        "Hacker News, Reddit, X/Twitter, relevant Discord servers, or dev.to."
                    ),
                    confidence=0.6,
                    trigger=f"sustained_decline_{trend.period}",
                )
            )

    # Check referrer spikes
    for ref in analysis.top_referrers[:3]:
        name = str(ref["name"])
        count = int(ref["total_count"])  # type: ignore[arg-type]
        if count > 50:
            proposals.append(
                Proposal(
                    title=f"Capitalize on traffic from {name}",
                    description=(
                        f"{name} is driving significant traffic ({count} hits). "
                        "Consider engaging with that community, contributing back, "
                        "or optimizing the content that attracted them."
                    ),
                    confidence=0.8,
                    trigger=f"referrer_spike_{name}",
                )
            )

    # Check anomalies
    for anomaly in analysis.anomalies:
        if anomaly.direction == "spike" and anomaly.std_devs >= 3:
            proposals.append(
                Proposal(
                    title=f"Investigate traffic spike on {anomaly.date}",
                    description=(
                        f"Unusual {anomaly.metric} spike ({anomaly.value:.0f} vs "
                        f"expected {anomaly.expected:.0f}, {anomaly.std_devs:.1f} std devs). "
                        "Check referrers for that day to identify the source and "
                        "consider how to sustain the momentum."
                    ),
                    confidence=0.75,
                    trigger=f"anomaly_spike_{anomaly.date}",
                )
            )

    # Sort by confidence descending
    proposals.sort(key=lambda p: p.confidence, reverse=True)

    logger.info("Generated %d proposals", len(proposals))
    return proposals
