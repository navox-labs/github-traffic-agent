"""Skill: Export stored traffic data to CSV for long-term archival."""

from __future__ import annotations

import csv
import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def export_csv(repo: str, data_dir: str) -> str:
    """Export all stored traffic data to a single CSV file. Returns the file path."""
    base = Path(data_dir) / "memory"
    exports_dir = Path(data_dir) / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    period_start = today - timedelta(days=14)
    csv_path = exports_dir / f"{period_start.isoformat()}_to_{today.isoformat()}-traffic.csv"

    views = _load_json(base / "views.json")
    clones = _load_json(base / "clones.json")

    # Build a date-keyed map merging views and clones
    by_date: dict[str, dict[str, object]] = {}
    for row in views:
        d = str(row["date"])
        by_date.setdefault(d, {"date": d})
        by_date[d]["views"] = row.get("count", 0)
        by_date[d]["unique_views"] = row.get("uniques", 0)

    for row in clones:
        d = str(row["date"])
        by_date.setdefault(d, {"date": d})
        by_date[d]["clones"] = row.get("count", 0)
        by_date[d]["unique_clones"] = row.get("uniques", 0)

    # Add referrer and path snapshot data for dates that have them
    for snapshot_dir, col_prefix, key_field in [
        (base / "referrers", "top_referrer", "referrer"),
        (base / "paths", "top_path", "path"),
    ]:
        if snapshot_dir.exists():
            for f in sorted(snapshot_dir.glob("*.json")):
                d = f.stem  # filename is YYYY-MM-DD
                items = _load_json(f)
                if items:
                    top = max(items, key=lambda x: int(str(x.get("count", 0))))
                    by_date.setdefault(d, {"date": d})
                    by_date[d][col_prefix] = top.get(key_field, "")
                    by_date[d][f"{col_prefix}_hits"] = top.get("count", 0)

    sorted_rows = sorted(by_date.values(), key=lambda r: str(r["date"]))

    fieldnames = [
        "date",
        "views",
        "unique_views",
        "clones",
        "unique_clones",
        "top_referrer",
        "top_referrer_hits",
        "top_path",
        "top_path_hits",
    ]

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_rows:
            # Fill missing columns with defaults
            for col in fieldnames:
                row.setdefault(col, 0 if col != "date" and "top_" not in col else "")
            writer.writerow(row)

    logger.info("CSV exported to %s (%d rows)", csv_path, len(sorted_rows))
    return str(csv_path)


def _load_json(filepath: Path) -> list[dict[str, object]]:
    if not filepath.exists():
        return []
    try:
        data: list[dict[str, object]] = json.loads(filepath.read_text())
        return data
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse %s", filepath)
        return []
