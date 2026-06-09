"""Skill: Collect GitHub traffic data via REST API."""

from __future__ import annotations

import logging

import httpx

from src.models.schemas import (
    ClonesResponse,
    CollectedData,
    PopularPath,
    PopularReferrer,
    ViewsResponse,
)
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@with_retry(max_attempts=3, base_delay=2.0, exceptions=(httpx.HTTPStatusError, httpx.TransportError))
async def _fetch(client: httpx.AsyncClient, url: str) -> dict:  # type: ignore[type-arg]
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


async def collect(token: str, repo: str) -> CollectedData:
    """Collect all traffic data for a single repository."""
    logger.info("Collecting traffic data for %s", repo)
    base = f"{API_BASE}/repos/{repo}/traffic"

    async with httpx.AsyncClient(headers=_headers(token), timeout=30.0) as client:
        views_data = await _fetch(client, f"{base}/views")
        clones_data = await _fetch(client, f"{base}/clones")
        paths_data = await _fetch(client, f"{base}/popular/paths")
        referrers_data = await _fetch(client, f"{base}/popular/referrers")

    from datetime import datetime, timezone

    views = ViewsResponse(**views_data)
    clones = ClonesResponse(**clones_data)
    paths = [PopularPath(**p) for p in paths_data]
    referrers = [PopularReferrer(**r) for r in referrers_data]

    return CollectedData(
        repo=repo,
        collected_at=datetime.now(timezone.utc),
        views=views,
        clones=clones,
        paths=paths,
        referrers=referrers,
    )
