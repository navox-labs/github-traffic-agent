"""Skill: Analyze historical traffic data for trends and anomalies."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.schemas import Anomaly, TrendData

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    repo: str
    views_df: pd.DataFrame
    clones_df: pd.DataFrame
    trends: list[TrendData] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    top_referrers: list[dict[str, object]] = field(default_factory=list)
    top_paths: list[dict[str, object]] = field(default_factory=list)


def analyze(repo: str, data_dir: str) -> AnalysisResult:
    """Run analysis on accumulated historical data."""
    base = Path(data_dir) / "memory"

    views_df = _load_traffic(base / "views.json")
    clones_df = _load_traffic(base / "clones.json")

    result = AnalysisResult(repo=repo, views_df=views_df, clones_df=clones_df)

    if len(views_df) >= 7:
        result.trends = _compute_trends(views_df, clones_df)
        result.anomalies = _detect_anomalies(views_df, clones_df)

    result.top_referrers = _aggregate_snapshots(base / "referrers")
    result.top_paths = _aggregate_snapshots(base / "paths")

    logger.info(
        "Analysis complete: %d trends, %d anomalies",
        len(result.trends),
        len(result.anomalies),
    )
    return result


def _load_traffic(filepath: Path) -> pd.DataFrame:
    if not filepath.exists():
        return pd.DataFrame(columns=["date", "count", "uniques"])
    data = json.loads(filepath.read_text())
    if not data:
        return pd.DataFrame(columns=["date", "count", "uniques"])
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _compute_trends(views_df: pd.DataFrame, clones_df: pd.DataFrame) -> list[TrendData]:
    trends: list[TrendData] = []

    for period_name, days in [("7-day", 7), ("30-day", 30)]:
        if len(views_df) < days:
            continue

        recent_views = views_df.tail(days)
        recent_clones = clones_df.tail(days) if len(clones_df) >= days else clones_df

        prev_views = views_df.iloc[-2 * days : -days] if len(views_df) >= 2 * days else None
        prev_clones = clones_df.iloc[-2 * days : -days] if len(clones_df) >= 2 * days else None

        avg_views = float(recent_views["count"].mean())
        avg_clones = float(recent_clones["count"].mean()) if len(recent_clones) > 0 else 0.0

        views_growth = 0.0
        if prev_views is not None and len(prev_views) > 0:
            prev_avg = float(prev_views["count"].mean())
            if prev_avg > 0:
                views_growth = ((avg_views - prev_avg) / prev_avg) * 100

        clones_growth = 0.0
        if prev_clones is not None and len(prev_clones) > 0:
            prev_avg = float(prev_clones["count"].mean())
            if prev_avg > 0:
                clones_growth = ((avg_clones - prev_avg) / prev_avg) * 100

        trends.append(
            TrendData(
                period=period_name,
                avg_daily_views=round(avg_views, 1),
                avg_daily_clones=round(avg_clones, 1),
                views_growth_pct=round(views_growth, 1),
                clones_growth_pct=round(clones_growth, 1),
            )
        )

    return trends


def _detect_anomalies(views_df: pd.DataFrame, clones_df: pd.DataFrame) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    for metric_name, df in [("views", views_df), ("clones", clones_df)]:
        if len(df) < 14:
            continue

        values = df["count"].values.astype(float)
        mean = float(np.mean(values))
        std = float(np.std(values))

        if std == 0:
            continue

        for _, row in df.iterrows():
            val = float(row["count"])
            z_score = (val - mean) / std
            if abs(z_score) >= 2.0:
                anomalies.append(
                    Anomaly(
                        date=row["date"],
                        metric=metric_name,
                        value=val,
                        expected=round(mean, 1),
                        std_devs=round(abs(z_score), 2),
                        direction="spike" if z_score > 0 else "drop",
                    )
                )

    return anomalies


def _aggregate_snapshots(snapshot_dir: Path) -> list[dict[str, object]]:
    """Aggregate all daily snapshots to find top items overall."""
    if not snapshot_dir.exists():
        return []

    aggregated: dict[str, int] = {}
    for f in sorted(snapshot_dir.glob("*.json")):
        items = json.loads(f.read_text())
        for item in items:
            key = item.get("referrer") or item.get("path", "unknown")
            aggregated[key] = aggregated.get(key, 0) + item.get("count", 0)

    sorted_items = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    return [{"name": k, "total_count": v} for k, v in sorted_items[:10]]
