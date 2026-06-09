"""Skill: Validate collected traffic data."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from src.models.schemas import AuditEntry, CollectedData, DailyTrafficRecord

logger = logging.getLogger(__name__)


class ValidationResult:
    def __init__(self) -> None:
        self.passed: dict[str, bool] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []

    @property
    def ok(self) -> bool:
        return all(self.passed.values()) and not self.errors

    @property
    def data_points(self) -> int:
        return self._data_points

    @data_points.setter
    def data_points(self, value: int) -> None:
        self._data_points = value


def validate(data: CollectedData, data_dir: str) -> ValidationResult:
    """Run all validation checks on collected data."""
    result = ValidationResult()
    result._data_points = 0

    # Schema validation (already done by Pydantic parsing in collect)
    result.passed["schema"] = True
    logger.info("Schema validation passed")

    # Completeness check
    _check_completeness(data, result)

    # Continuity check
    _check_continuity(data, data_dir, result)

    return result


def _check_completeness(data: CollectedData, result: ValidationResult) -> None:
    views_count = len(data.views.views)
    clones_count = len(data.clones.clones)
    result._data_points = views_count + clones_count

    has_views = views_count > 0
    has_clones = clones_count > 0

    # Check for null values in views
    for v in data.views.views:
        if v.count < 0 or v.uniques < 0:
            result.errors.append(f"Negative values in views for {v.timestamp}")
            result.passed["completeness"] = False
            return

    for c in data.clones.clones:
        if c.count < 0 or c.uniques < 0:
            result.errors.append(f"Negative values in clones for {c.timestamp}")
            result.passed["completeness"] = False
            return

    if not has_views and not has_clones:
        result.warnings.append("No views or clones data returned (repo may have zero traffic)")

    result.passed["completeness"] = True
    logger.info("Completeness check passed: %d views, %d clones entries", views_count, clones_count)


def _check_continuity(data: CollectedData, data_dir: str, result: ValidationResult) -> None:
    views_file = Path(data_dir) / "memory" / "views.json"
    if not views_file.exists():
        result.passed["continuity"] = True
        logger.info("Continuity check: no previous data, first run")
        return

    try:
        existing = json.loads(views_file.read_text())
        if not existing:
            result.passed["continuity"] = True
            return

        records = [DailyTrafficRecord(**r) for r in existing]
        last_stored = max(r.date for r in records)
        today = date.today()

        if data.views.views:
            earliest_new = min(v.timestamp.date() for v in data.views.views)
            gap_days = (earliest_new - last_stored).days
            if gap_days > 1:
                result.warnings.append(
                    f"Gap of {gap_days - 1} day(s) between last stored date "
                    f"({last_stored}) and earliest new date ({earliest_new})"
                )
        else:
            gap_days = (today - last_stored).days
            if gap_days > 14:
                result.warnings.append(
                    f"No new views data and last stored date was {gap_days} days ago. "
                    "Data may have been lost."
                )

        result.passed["continuity"] = True
        if result.warnings:
            logger.warning("Continuity check passed with warnings: %s", result.warnings)
        else:
            logger.info("Continuity check passed, no gaps")

    except Exception as exc:
        result.errors.append(f"Continuity check failed: {exc}")
        result.passed["continuity"] = False


def write_audit_entry(
    data: CollectedData,
    validation: ValidationResult,
    data_dir: str,
) -> None:
    """Write an audit log entry for this run."""
    audit_file = Path(data_dir) / "memory" / "audit-log.json"
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []  # type: ignore[type-arg]
    if audit_file.exists():
        entries = json.loads(audit_file.read_text())

    status = "success" if validation.ok else ("warning" if validation.warnings else "error")

    entry = AuditEntry(
        timestamp=datetime.now(UTC),
        repo=data.repo,
        status=status,
        data_points=validation.data_points,
        validation_results=validation.passed,
        errors=validation.errors,
        warnings=validation.warnings,
    )
    entries.append(entry.model_dump(mode="json"))
    audit_file.write_text(json.dumps(entries, indent=2, default=str))
    logger.info("Audit entry written: %s", status)
