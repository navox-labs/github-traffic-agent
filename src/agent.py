"""Agent orchestrator — runs skill pipeline based on mode."""

from __future__ import annotations

import asyncio
import logging
import sys

from src.models.config import AgentConfig
from src.skills.collect import collect
from src.skills.notify import BriefNotification, NotificationMessage, notify
from src.skills.store import store_and_commit
from src.skills.validate import validate, write_audit_entry
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


def _write_failure_audit(repo: str, exc: Exception, data_dir: str) -> None:
    """Write an audit entry when collection fails, so failures leave a trace."""
    try:
        import json
        from datetime import UTC, datetime
        from pathlib import Path

        from src.models.schemas import AuditEntry
        from src.skills.store import _atomic_write

        audit_file = Path(data_dir) / "memory" / "audit-log.json"
        audit_file.parent.mkdir(parents=True, exist_ok=True)

        entries: list[dict] = []  # type: ignore[type-arg]
        if audit_file.exists():
            entries = json.loads(audit_file.read_text())

        entry = AuditEntry(
            timestamp=datetime.now(UTC),
            repo=repo,
            status="error",
            data_points=0,
            validation_results={},
            errors=[str(exc)],
        )
        entries.append(entry.model_dump(mode="json"))
        _atomic_write(audit_file, json.dumps(entries, indent=2, default=str))
    except Exception as audit_exc:
        logger.error("Failed to write failure audit entry: %s", audit_exc)


async def run_collect(config: AgentConfig) -> None:
    """Daily pipeline: Collect -> Validate -> Store -> Notify."""
    for repo in config.repos:
        logger.info("=== Processing %s ===", repo)
        try:
            # Collect
            data = await collect(config.token, repo)
            logger.info("Collected data for %s", repo)

            # Validate
            result = validate(data, config.data_dir)
            write_audit_entry(data, result, config.data_dir)

            if not result.ok:
                msg = NotificationMessage(
                    subject=f"Traffic Agent Error: {repo}",
                    body=f"Validation failed for {repo}.\nErrors: {result.errors}",
                    level="error",
                )
                await notify(config.notify, msg)
                continue

            # Store & commit
            store_and_commit(data, config.data_dir, config.branch)

            # Notify success
            views_total = sum(v.count for v in data.views.views)
            clones_total = sum(c.count for c in data.clones.clones)
            body = (
                f"Collected {views_total} views, {clones_total} clones for {repo}.\n"
                f"All validations passed."
            )
            if result.warnings:
                body += f"\nWarnings: {', '.join(result.warnings)}"

            msg = NotificationMessage(
                subject=f"Traffic Agent: {repo}",
                body=body,
                level="warning" if result.warnings else "success",
            )
            await notify(config.notify, msg)

        except Exception as exc:
            logger.exception("Failed to process %s: %s", repo, exc)

            # Write audit entry for failures so monitoring has no blind spots
            _write_failure_audit(repo, exc, config.data_dir)

            msg = NotificationMessage(
                subject=f"Traffic Agent Error: {repo}",
                body=f"Failed to collect traffic data for {repo}: {exc}",
                level="error",
            )
            await notify(config.notify, msg)


async def run_report(config: AgentConfig) -> None:
    """Bi-weekly pipeline: Analyze -> Predict -> Propose -> Intelligence -> Notify."""
    from src.skills.analyze import analyze
    from src.skills.export_csv import export_csv
    from src.skills.intelligence import generate_brief, load_prior_actions, save_actions
    from src.skills.predict import predict
    from src.skills.propose import propose
    from src.skills.report import generate_report
    from src.skills.validate import _get_health_status

    for repo in config.repos:
        logger.info("=== Generating report for %s ===", repo)
        try:
            analysis = analyze(repo, config.data_dir)
            predictions = predict(repo, config.data_dir)
            proposals = propose(analysis, predictions)

            # Generate long report as committed artifact
            report_path = generate_report(repo, config.data_dir, analysis, predictions, proposals)

            # Export CSV snapshot for long-term archival
            csv_path = export_csv(repo, config.data_dir)

            # Intelligence layer: LLM brief (or fallback)
            prior_actions = load_prior_actions(config.data_dir)
            health_status = _get_health_status(config.data_dir)
            product_context = config.product_context or {"repo": repo}
            if "repo" not in product_context:
                product_context["repo"] = repo

            brief = generate_brief(
                analysis=analysis,
                predictions=predictions,
                proposals=proposals,
                product_context=product_context,
                prior_actions=prior_actions,
                health_status=health_status,
                data_dir=config.data_dir,
                model=config.model,
            )

            # Persist actions for next run's feedback loop
            if brief.actions:
                save_actions(brief, config.data_dir)

            # Commit report + actions file (actions must persist across runs)
            from pathlib import Path

            from src.utils.git import commit_and_push

            commit_files = [report_path, csv_path]
            actions_file = str(
                Path(config.data_dir) / "memory" / "brief-actions.json"
            )
            if Path(actions_file).exists():
                commit_files.append(actions_file)
            commit_and_push(
                commit_files,
                f"traffic: bi-weekly report for {repo}",
                config.branch,
            )

            # Notify with the Brief — each channel renders natively
            level = "warning" if brief.alert else "success"
            await notify(
                config.notify,
                BriefNotification(brief=brief, repo=repo, level=level),
            )

        except Exception as exc:
            logger.exception("Failed to generate report for %s: %s", repo, exc)
            msg = NotificationMessage(
                subject=f"Traffic Report Error: {repo}",
                body=f"Failed to generate report for {repo}: {exc}",
                level="error",
            )
            await notify(config.notify, msg)


async def main() -> None:
    setup_logging()
    config = AgentConfig.from_env()

    if not config.token:
        logger.error("No token provided")
        sys.exit(1)
    if not config.repos:
        logger.error("No repos configured")
        sys.exit(1)

    logger.info("Starting GitHub Traffic Agent in '%s' mode for %s", config.mode, config.repos)

    if config.mode == "collect":
        await run_collect(config)
    elif config.mode == "report":
        await run_report(config)
    else:
        logger.error("Unknown mode: %s", config.mode)
        sys.exit(1)

    logger.info("Agent run complete")


if __name__ == "__main__":
    asyncio.run(main())
