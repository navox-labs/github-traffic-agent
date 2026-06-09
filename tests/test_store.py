"""Tests for the store skill."""

from __future__ import annotations

import json
from pathlib import Path

from src.models.schemas import CollectedData
from src.skills.store import store


def test_store_creates_files(mock_collected_data: CollectedData, tmp_data_dir: str):
    modified = store(mock_collected_data, tmp_data_dir)

    assert len(modified) == 4  # views, clones, paths snapshot, referrers snapshot

    views_file = Path(tmp_data_dir) / "memory" / "views.json"
    assert views_file.exists()
    views = json.loads(views_file.read_text())
    assert len(views) == 7

    clones_file = Path(tmp_data_dir) / "memory" / "clones.json"
    assert clones_file.exists()
    clones = json.loads(clones_file.read_text())
    assert len(clones) == 7


def test_store_merges_deduplicates(mock_collected_data: CollectedData, tmp_data_dir: str):
    # Store once
    store(mock_collected_data, tmp_data_dir)

    # Store again (same data)
    store(mock_collected_data, tmp_data_dir)

    views_file = Path(tmp_data_dir) / "memory" / "views.json"
    views = json.loads(views_file.read_text())
    assert len(views) == 7  # No duplicates


def test_store_merges_new_data(mock_collected_data: CollectedData, tmp_data_dir: str):
    # Write existing data
    views_file = Path(tmp_data_dir) / "memory" / "views.json"
    views_file.write_text(json.dumps([
        {"date": "2026-05-20", "count": 5, "uniques": 3},
    ]))

    store(mock_collected_data, tmp_data_dir)

    views = json.loads(views_file.read_text())
    assert len(views) == 8  # 1 existing + 7 new


def test_store_paths_snapshot(mock_collected_data: CollectedData, tmp_data_dir: str):
    store(mock_collected_data, tmp_data_dir)

    paths_dir = Path(tmp_data_dir) / "memory" / "paths"
    snapshots = list(paths_dir.glob("*.json"))
    assert len(snapshots) == 1

    data = json.loads(snapshots[0].read_text())
    assert len(data) == 2
    assert data[0]["path"] == "/navox-labs/repo"
