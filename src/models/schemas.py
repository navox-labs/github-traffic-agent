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


BRIEF_MAX_HEADLINE_WORDS = 15
BRIEF_MAX_ACTION_WORDS = 12
BRIEF_MAX_ACTIONS = 2


class Brief(BaseModel):
    """The phone-notification-sized intelligence output."""

    headline: str = ""
    actions: list[str] = Field(default_factory=list)
    alert: bool = False
    verdict: str = Field(default="flat", description="growing | flat | declining")
    loop_comment: str = ""
    health_token: str = ""

    @classmethod
    def from_rules(cls, proposals: list[Proposal], trends: list[TrendData] | None = None) -> Brief:
        """Deterministic fallback: build a Brief from rule-based proposals."""
        if trends:
            vg = trends[0].views_growth_pct
            cg = trends[0].clones_growth_pct
            if vg > 5 or cg > 5:
                verdict = "growing"
            elif vg < -5 or cg < -5:
                verdict = "declining"
            else:
                verdict = "flat"
            headline = f"Views {vg:+.0f}%, clones {cg:+.0f}% over {trends[0].period}"
        else:
            verdict = "flat"
            headline = "Insufficient data for trend analysis"

        actions = [p.title for p in proposals[:2]]
        alert = any(p.confidence >= 0.8 for p in proposals[:2])

        brief = cls(headline=headline, actions=actions, alert=alert, verdict=verdict)
        brief.enforce_caps()
        return brief

    def enforce_caps(self) -> None:
        """Truncate fields that exceed word/count limits."""
        words = self.headline.split()
        if len(words) > BRIEF_MAX_HEADLINE_WORDS:
            self.headline = " ".join(words[:BRIEF_MAX_HEADLINE_WORDS])

        self.actions = self.actions[:BRIEF_MAX_ACTIONS]
        for i, action in enumerate(self.actions):
            words = action.split()
            if len(words) > BRIEF_MAX_ACTION_WORDS:
                self.actions[i] = " ".join(words[:BRIEF_MAX_ACTION_WORDS])

    def total_words(self) -> int:
        """Total word count for the digest."""
        count = len(self.headline.split())
        for a in self.actions:
            count += len(a.split())
        if self.loop_comment:
            count += len(self.loop_comment.split())
        if self.health_token:
            count += len(self.health_token.split())
        return count
