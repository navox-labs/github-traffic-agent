"""Tests for the validate skill."""

from __future__ import annotations

import json
from pathlib import Path

from src.models.schemas import CollectedData
from src.skills.validate import validate, write_audit_entry


def test_validate_success(mock_collected_data: CollectedData, tmp_data_dir: str):
    result = validate(mock_collected_data, tmp_data_dir)
    assert result.ok
    assert result.passed["schema"] is True
    assert result.passed["completeness"] is True
    assert result.passed["continuity"] is True
    assert result.data_points == 14  # 7 views + 7 clones


def test_validate_continuity_with_existing_data(mock_collected_data: CollectedData, tmp_data_dir: str):
    # Write existing data with a date that creates a gap
    views_file = Path(tmp_data_dir) / "memory" / "views.json"
    views_file.write_text(json.dumps([
        {"date": "2026-05-10", "count": 5, "uniques": 3},
    ]))

    result = validate(mock_collected_data, tmp_data_dir)
    assert result.ok  # continuity passes but with warnings
    assert len(result.warnings) > 0
    assert "Gap" in result.warnings[0]


def test_validate_first_run(mock_collected_data: CollectedData, tmp_data_dir: str):
    result = validate(mock_collected_data, tmp_data_dir)
    assert result.ok
    assert result.passed["continuity"] is True


def test_write_audit_entry(mock_collected_data: CollectedData, tmp_data_dir: str):
    result = validate(mock_collected_data, tmp_data_dir)
    write_audit_entry(mock_collected_data, result, tmp_data_dir)

    audit_file = Path(tmp_data_dir) / "memory" / "audit-log.json"
    assert audit_file.exists()

    entries = json.loads(audit_file.read_text())
    assert len(entries) == 1
    assert entries[0]["status"] == "success"
    assert entries[0]["repo"] == "navox-labs/test-repo"
