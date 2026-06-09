"""Pydantic models for GitHub Traffic API responses and stored data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# --- GitHub API Response Models ---


class TrafficCount(BaseModel):
    """A single day's traffic count from the GitHub API."""

    timestamp: datetime
    count: int
    uniques: int


class ViewsResponse(BaseModel):
    """Response from GET /repos/{owner}/{repo}/traffic/views."""

    count: int
    uniques: int
    views: list[TrafficCount]


class ClonesResponse(BaseModel):
    """Response from GET /repos/{owner}/{repo}/traffic/clones."""

    count: int
    uniques: int
    clones: list[TrafficCount]


class PopularPath(BaseModel):
    """A single popular path entry."""

    path: str
    title: str
    count: int
    uniques: int


class PopularReferrer(BaseModel):
    """A single popular referrer entry."""

    referrer: str
    count: int
    uniques: int


# --- Stored Data Models ---


class DailyTrafficRecord(BaseModel):
    """A single day's traffic record for long-term storage."""

    date: date
    count: int
    uniques: int


class PathsSnapshot(BaseModel):
    """Daily snapshot of popular paths."""

    date: date
    paths: list[PopularPath]


class ReferrersSnapshot(BaseModel):
    """Daily snapshot of popular referrers."""

    date: date
    referrers: list[PopularReferrer]


# --- Collected Data Bundle ---


class CollectedData(BaseModel):
    """All traffic data collected in a single run for one repo."""

    repo: str
    collected_at: datetime
    views: ViewsResponse
    clones: ClonesResponse
    paths: list[PopularPath]
    referrers: list[PopularReferrer]


# --- Audit Log ---


class AuditEntry(BaseModel):
    """A single entry in the audit log."""

    timestamp: datetime
    repo: str
    status: str = Field(description="success | warning | error")
    data_points: int = 0
    validation_results: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- Analysis Models ---


class TrendData(BaseModel):
    """Computed trend information."""

    period: str
    avg_daily_views: float
    avg_daily_clones: float
    views_growth_pct: float
    clones_growth_pct: float


class Anomaly(BaseModel):
    """A detected anomaly in traffic data."""

    date: date
    metric: str
    value: float
    expected: float
    std_devs: float
    direction: str = Field(description="spike | drop")


class Prediction(BaseModel):
    """A traffic prediction for a future date."""

    date: date
    metric: str
    predicted: float
    lower_bound: float
    upper_bound: float


class Proposal(BaseModel):
    """An actionable proposal based on analysis."""

    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    trigger: str
