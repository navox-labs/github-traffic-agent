"""Shared fixtures and mock API responses."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models.schemas import (
    ClonesResponse,
    CollectedData,
    PopularPath,
    PopularReferrer,
    TrafficCount,
    ViewsResponse,
)


MOCK_VIEWS_RESPONSE = {
    "count": 100,
    "uniques": 50,
    "views": [
        {"timestamp": "2026-05-26T00:00:00Z", "count": 10, "uniques": 5},
        {"timestamp": "2026-05-27T00:00:00Z", "count": 15, "uniques": 8},
        {"timestamp": "2026-05-28T00:00:00Z", "count": 12, "uniques": 6},
        {"timestamp": "2026-05-29T00:00:00Z", "count": 20, "uniques": 10},
        {"timestamp": "2026-05-30T00:00:00Z", "count": 8, "uniques": 4},
        {"timestamp": "2026-05-31T00:00:00Z", "count": 18, "uniques": 9},
        {"timestamp": "2026-06-01T00:00:00Z", "count": 17, "uniques": 8},
    ],
}

MOCK_CLONES_RESPONSE = {
    "count": 30,
    "uniques": 15,
    "clones": [
        {"timestamp": "2026-05-26T00:00:00Z", "count": 3, "uniques": 2},
        {"timestamp": "2026-05-27T00:00:00Z", "count": 5, "uniques": 3},
        {"timestamp": "2026-05-28T00:00:00Z", "count": 4, "uniques": 2},
        {"timestamp": "2026-05-29T00:00:00Z", "count": 6, "uniques": 3},
        {"timestamp": "2026-05-30T00:00:00Z", "count": 2, "uniques": 1},
        {"timestamp": "2026-05-31T00:00:00Z", "count": 5, "uniques": 2},
        {"timestamp": "2026-06-01T00:00:00Z", "count": 5, "uniques": 2},
    ],
}

MOCK_PATHS_RESPONSE = [
    {"path": "/navox-labs/repo", "title": "repo", "count": 50, "uniques": 30},
    {"path": "/navox-labs/repo/blob/main/README.md", "title": "README.md", "count": 20, "uniques": 15},
]

MOCK_REFERRERS_RESPONSE = [
    {"referrer": "github.com", "count": 40, "uniques": 20},
    {"referrer": "google.com", "count": 15, "uniques": 10},
]


@pytest.fixture
def mock_collected_data() -> CollectedData:
    return CollectedData(
        repo="navox-labs/test-repo",
        collected_at=datetime(2026, 6, 1, 3, 0, 0, tzinfo=timezone.utc),
        views=ViewsResponse(**MOCK_VIEWS_RESPONSE),
        clones=ClonesResponse(**MOCK_CLONES_RESPONSE),
        paths=[PopularPath(**p) for p in MOCK_PATHS_RESPONSE],
        referrers=[PopularReferrer(**r) for r in MOCK_REFERRERS_RESPONSE],
    )


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory structure."""
    memory_dir = tmp_path / "traffic-data" / "memory"
    memory_dir.mkdir(parents=True)
    return str(tmp_path / "traffic-data")
