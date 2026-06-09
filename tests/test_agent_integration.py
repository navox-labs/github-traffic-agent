"""Integration test: full collect pipeline end-to-end."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from src.models.config import AgentConfig, NotifyConfig
from src.agent import run_collect
from tests.conftest import (
    MOCK_CLONES_RESPONSE,
    MOCK_PATHS_RESPONSE,
    MOCK_REFERRERS_RESPONSE,
    MOCK_VIEWS_RESPONSE,
)


@pytest.mark.asyncio
async def test_full_collect_pipeline(tmp_path):
    data_dir = str(tmp_path / "traffic-data")
    repo = "navox-labs/test-repo"
    base = f"https://api.github.com/repos/{repo}/traffic"

    config = AgentConfig(
        token="fake-token",
        repos=[repo],
        data_dir=data_dir,
        mode="collect",
        notify=NotifyConfig(),
    )

    with respx.mock:
        respx.get(f"{base}/views").mock(return_value=httpx.Response(200, json=MOCK_VIEWS_RESPONSE))
        respx.get(f"{base}/clones").mock(return_value=httpx.Response(200, json=MOCK_CLONES_RESPONSE))
        respx.get(f"{base}/popular/paths").mock(return_value=httpx.Response(200, json=MOCK_PATHS_RESPONSE))
        respx.get(f"{base}/popular/referrers").mock(return_value=httpx.Response(200, json=MOCK_REFERRERS_RESPONSE))

        with patch("src.skills.store.commit_and_push", return_value=True):
            await run_collect(config)

    # Verify data files were created
    memory = Path(data_dir) / "memory"
    assert (memory / "views.json").exists()
    assert (memory / "clones.json").exists()
    assert (memory / "audit-log.json").exists()

    views = json.loads((memory / "views.json").read_text())
    assert len(views) == 7

    audit = json.loads((memory / "audit-log.json").read_text())
    assert len(audit) == 1
    assert audit[0]["status"] == "success"

    # Verify paths/referrers snapshots
    paths_files = list((memory / "paths").glob("*.json"))
    assert len(paths_files) == 1
    referrers_files = list((memory / "referrers").glob("*.json"))
    assert len(referrers_files) == 1
