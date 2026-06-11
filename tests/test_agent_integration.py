"""Integration test: full collect pipeline end-to-end."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import respx

from src.agent import run_collect
from src.models.config import AgentConfig, NotifyConfig
from tests.conftest import mock_traffic_api


@pytest.mark.asyncio
async def test_full_collect_pipeline(tmp_path):
    repo = "navox-labs/test-repo"
    data_dir = "traffic-data"

    config = AgentConfig(
        token="fake-token",
        data_repo="navox-labs/traffic-data",
        repos=[repo],
        data_dir=data_dir,
        mode="collect",
        notify=NotifyConfig(),
    )

    # Mock clone_data_repo to return a temp dir instead of actually cloning
    clone_path = str(tmp_path / "data-clone")
    Path(clone_path).mkdir()

    with respx.mock:
        mock_traffic_api(repo)

        with (
            patch("src.agent.clone_data_repo", return_value=clone_path),
            patch("src.utils.git.commit_and_push", return_value=True),
            patch("shutil.rmtree"),
        ):
            await run_collect(config)

    # Verify data files were created in the per-repo subdirectory
    memory = Path(clone_path) / data_dir / repo / "memory"
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
