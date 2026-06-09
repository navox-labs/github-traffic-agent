"""Skill: Generate bi-weekly Markdown analysis report."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from src.models.schemas import Prediction, Proposal
from src.skills.analyze import AnalysisResult

logger = logging.getLogger(__name__)


def generate_report(
    repo: str,
    data_dir: str,
    analysis: AnalysisResult,
    predictions: list[Prediction],
    proposals: list[Proposal],
) -> str:
    """Generate a Markdown report and write it to the reports directory. Returns the file path."""
    reports_dir = Path(data_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    report_path = reports_dir / f"{today}-report.md"

    sections = [
        _header(repo, today),
        _summary(analysis),
        _trends_section(analysis),
        _referrers_section(analysis),
        _paths_section(analysis),
        _anomalies_section(analysis),
        _predictions_section(predictions),
        _proposals_section(proposals),
    ]

    content = "\n\n".join(s for s in sections if s)
    report_path.write_text(content)

    logger.info("Report written to %s", report_path)
    return str(report_path)


def _header(repo: str, today: str) -> str:
    return f"# Traffic Report: {repo}\n\n**Generated:** {today}"


def _summary(analysis: AnalysisResult) -> str:
    views_df = analysis.views_df
    clones_df = analysis.clones_df

    total_views = int(views_df["count"].sum()) if len(views_df) > 0 else 0
    total_clones = int(clones_df["count"].sum()) if len(clones_df) > 0 else 0
    total_unique_views = int(views_df["uniques"].sum()) if len(views_df) > 0 else 0
    total_unique_clones = int(clones_df["uniques"].sum()) if len(clones_df) > 0 else 0
    days = len(views_df)

    lines = [
        "## Summary",
        "",
        "| Metric | Total | Unique | Daily Avg |",
        "|--------|------:|-------:|----------:|",
        f"| Views  | {total_views:,} | {total_unique_views:,} | {total_views / max(days, 1):.1f} |",
        f"| Clones | {total_clones:,} | {total_unique_clones:,} "
        f"| {total_clones / max(days, 1):.1f} |",
        "",
        f"*Based on {days} days of data*",
    ]
    return "\n".join(lines)


def _trends_section(analysis: AnalysisResult) -> str:
    if not analysis.trends:
        return ""

    lines = [
        "## Trends",
        "",
        "| Period | Avg Views/Day | Avg Clones/Day | Views Growth | Clones Growth |",
        "|--------|-------------:|---------------:|-------------:|--------------:|",
    ]

    for t in analysis.trends:
        lines.append(
            f"| {t.period} | {t.avg_daily_views:.1f} | {t.avg_daily_clones:.1f} "
            f"| {t.views_growth_pct:+.1f}% | {t.clones_growth_pct:+.1f}% |"
        )

    return "\n".join(lines)


def _referrers_section(analysis: AnalysisResult) -> str:
    if not analysis.top_referrers:
        return ""

    lines = [
        "## Top Referrers",
        "",
        "| Source | Total Hits |",
        "|--------|----------:|",
    ]
    for ref in analysis.top_referrers[:10]:
        lines.append(f"| {ref['name']} | {ref['total_count']:,} |")

    return "\n".join(lines)


def _paths_section(analysis: AnalysisResult) -> str:
    if not analysis.top_paths:
        return ""

    lines = [
        "## Popular Content",
        "",
        "| Path | Total Hits |",
        "|------|----------:|",
    ]
    for p in analysis.top_paths[:10]:
        lines.append(f"| {p['name']} | {p['total_count']:,} |")

    return "\n".join(lines)


def _anomalies_section(analysis: AnalysisResult) -> str:
    if not analysis.anomalies:
        return ""

    lines = [
        "## Anomalies Detected",
        "",
        "| Date | Metric | Value | Expected | Deviation |",
        "|------|--------|------:|---------:|-----------|",
    ]
    for a in analysis.anomalies:
        lines.append(
            f"| {a.date} | {a.metric} | {a.value:.0f} | {a.expected:.0f} "
            f"| {a.std_devs:.1f} std devs ({a.direction}) |"
        )

    return "\n".join(lines)


def _predictions_section(predictions: list[Prediction]) -> str:
    if not predictions:
        return ""

    lines = [
        "## Predictions (Next 14 Days)",
        "",
        "| Date | Metric | Predicted | Range |",
        "|------|--------|----------:|------:|",
    ]

    for p in predictions:
        lines.append(
            f"| {p.date} | {p.metric} | {p.predicted:.0f} "
            f"| {p.lower_bound:.0f} - {p.upper_bound:.0f} |"
        )

    return "\n".join(lines)


def _proposals_section(proposals: list[Proposal]) -> str:
    if not proposals:
        return ""

    lines = ["## Proposals", ""]
    for i, p in enumerate(proposals, 1):
        confidence_bar = _confidence_bar(p.confidence)
        lines.extend([
            f"### {i}. {p.title}",
            "",
            f"**Confidence:** {confidence_bar} ({p.confidence:.0%})",
            "",
            p.description,
            "",
        ])

    return "\n".join(lines)


def _confidence_bar(confidence: float) -> str:
    filled = round(confidence * 10)
    return "[" + "#" * filled + "-" * (10 - filled) + "]"
