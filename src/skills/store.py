"""Skill: Store collected traffic data to JSON files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.models.schemas import CollectedData, DailyTrafficRecord
from src.utils.git import commit_and_push

logger = logging.getLogger(__name__)


def store(data: CollectedData, data_dir: str, branch: str = "") -> list[str]:
    """Store collected data, merging with existing records. Returns list of modified files."""
    base = Path(data_dir) / "memory"
    base.mkdir(parents=True, exist_ok=True)

    modified: list[str] = []

    # Store views
    views_file = base / "views.json"
    views_records = _merge_traffic(
        views_file,
        [
            DailyTrafficRecord(
                date=v.timestamp.date(), count=v.count, uniques=v.uniques
            )
            for v in data.views.views
        ],
    )
    views_file.write_text(json.dumps(views_records, indent=2, default=str))
    modified.append(str(views_file))

    # Store clones
    clones_file = base / "clones.json"
    clones_records = _merge_traffic(
        clones_file,
        [
            DailyTrafficRecord(
                date=c.timestamp.date(), count=c.count, uniques=c.uniques
            )
            for c in data.clones.clones
        ],
    )
    clones_file.write_text(json.dumps(clones_records, indent=2, default=str))
    modified.append(str(clones_file))

    # Store paths snapshot
    today_str = data.collected_at.strftime("%Y-%m-%d")
    paths_dir = base / "paths"
    paths_dir.mkdir(parents=True, exist_ok=True)
    paths_file = paths_dir / f"{today_str}.json"
    paths_file.write_text(
        json.dumps([p.model_dump() for p in data.paths], indent=2)
    )
    modified.append(str(paths_file))

    # Store referrers snapshot
    referrers_dir = base / "referrers"
    referrers_dir.mkdir(parents=True, exist_ok=True)
    referrers_file = referrers_dir / f"{today_str}.json"
    referrers_file.write_text(
        json.dumps([r.model_dump() for r in data.referrers], indent=2)
    )
    modified.append(str(referrers_file))

    logger.info(
        "Stored data for %s: %d views entries, %d clones entries",
        data.repo,
        len(data.views.views),
        len(data.clones.clones),
    )
    return modified


def store_and_commit(
    data: CollectedData, data_dir: str, branch: str = ""
) -> bool:
    """Store data and commit changes. Returns True if committed."""
    modified = store(data, data_dir, branch)

    # Also include audit log
    audit_file = str(Path(data_dir) / "memory" / "audit-log.json")
    if Path(audit_file).exists():
        modified.append(audit_file)

    today_str = data.collected_at.strftime("%Y-%m-%d")
    message = f"traffic: collect data for {data.repo} ({today_str})"

    return commit_and_push(modified, message, branch)


def _merge_traffic(
    filepath: Path, new_records: list[DailyTrafficRecord]
) -> list[dict[str, object]]:
    """Merge new records into existing file, deduplicating by date."""
    existing: list[dict[str, object]] = []
    if filepath.exists():
        existing = json.loads(filepath.read_text())

    # Build a map keyed by date string
    by_date: dict[str, dict[str, object]] = {}
    for record in existing:
        date_key = str(record["date"])
        by_date[date_key] = record

    # New records overwrite existing for same date (fresher data)
    for record in new_records:
        date_key = str(record.date)
        by_date[date_key] = record.model_dump(mode="json")

    # Sort by date
    sorted_records = sorted(by_date.values(), key=lambda r: str(r["date"]))
    return sorted_records
