"""Tests for the CSV export skill."""

import csv
import json
from pathlib import Path

from src.skills.export_csv import export_csv


def _setup_data(tmp_path: Path) -> str:
    """Create minimal traffic data fixtures."""
    memory = tmp_path / "memory"
    memory.mkdir()

    views = [
        {"date": "2026-06-09", "count": 39, "uniques": 1},
        {"date": "2026-06-10", "count": 3, "uniques": 1},
    ]
    (memory / "views.json").write_text(json.dumps(views))

    clones = [
        {"date": "2026-06-09", "count": 233, "uniques": 87},
        {"date": "2026-06-10", "count": 32, "uniques": 20},
    ]
    (memory / "clones.json").write_text(json.dumps(clones))

    referrers_dir = memory / "referrers"
    referrers_dir.mkdir()
    (referrers_dir / "2026-06-09.json").write_text(
        json.dumps([{"referrer": "github.com", "count": 21, "uniques": 1}])
    )

    paths_dir = memory / "paths"
    paths_dir.mkdir()
    path_entry = {
        "path": "/navox-labs/github-traffic-agent",
        "title": "Overview",
        "count": 25,
        "uniques": 1,
    }
    (paths_dir / "2026-06-09.json").write_text(json.dumps([path_entry]))

    return str(tmp_path)


def test_export_csv_creates_file(tmp_path: Path) -> None:
    data_dir = _setup_data(tmp_path)
    result = export_csv("navox-labs/github-traffic-agent", data_dir)
    assert Path(result).exists()
    assert result.endswith("-traffic.csv")
    assert "_to_" in Path(result).name


def test_export_csv_has_correct_headers(tmp_path: Path) -> None:
    data_dir = _setup_data(tmp_path)
    result = export_csv("navox-labs/github-traffic-agent", data_dir)
    with open(result) as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames or []) == {
            "date", "views", "unique_views", "clones", "unique_clones",
            "top_referrer", "top_referrer_hits", "top_path", "top_path_hits",
        }


def test_export_csv_row_count(tmp_path: Path) -> None:
    data_dir = _setup_data(tmp_path)
    result = export_csv("navox-labs/github-traffic-agent", data_dir)
    with open(result) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


def test_export_csv_data_values(tmp_path: Path) -> None:
    data_dir = _setup_data(tmp_path)
    result = export_csv("navox-labs/github-traffic-agent", data_dir)
    with open(result) as f:
        rows = list(csv.DictReader(f))
    row_0609 = next(r for r in rows if r["date"] == "2026-06-09")
    assert row_0609["views"] == "39"
    assert row_0609["clones"] == "233"
    assert row_0609["top_referrer"] == "github.com"
    assert row_0609["top_path"] == "/navox-labs/github-traffic-agent"


def test_export_csv_handles_missing_data(tmp_path: Path) -> None:
    """Export works even with no stored data."""
    memory = tmp_path / "memory"
    memory.mkdir()
    result = export_csv("test/repo", str(tmp_path))
    assert Path(result).exists()
    with open(result) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0
