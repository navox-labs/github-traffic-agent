"""Tests for the collect skill."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.skills.collect import collect
from tests.conftest import (
    MOCK_CLONES_RESPONSE,
    MOCK_PATHS_RESPONSE,
    MOCK_REFERRERS_RESPONSE,
    MOCK_VIEWS_RESPONSE,
    mock_traffic_api,
)


@pytest.mark.asyncio
async def test_collect_success():
    repo = "navox-labs/test-repo"

    with respx.mock:
        mock_traffic_api(repo)
        data = await collect("fake-token", repo)

    assert data.repo == repo
    assert len(data.views.views) == 7
    assert len(data.clones.clones) == 7
    assert len(data.paths) == 2
    assert len(data.referrers) == 2
    assert data.views.count == 100
    assert data.clones.count == 30


@pytest.mark.asyncio
async def test_collect_api_error_retries():
    repo = "navox-labs/test-repo"
    base = f"https://api.github.com/repos/{repo}/traffic"

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return httpx.Response(500, json={"message": "Error"})
        return httpx.Response(200, json=MOCK_VIEWS_RESPONSE)

    with respx.mock:
        respx.get(f"{base}/views").mock(side_effect=side_effect)
        respx.get(f"{base}/clones").mock(
            return_value=httpx.Response(200, json=MOCK_CLONES_RESPONSE)
        )
        respx.get(f"{base}/popular/paths").mock(
            return_value=httpx.Response(200, json=MOCK_PATHS_RESPONSE)
        )
        respx.get(f"{base}/popular/referrers").mock(
            return_value=httpx.Response(
                200, json=MOCK_REFERRERS_RESPONSE
            )
        )

        data = await collect("fake-token", repo)

    assert data.views.count == 100
    assert call_count == 3
