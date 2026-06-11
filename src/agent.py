"""Agent orchestrator — runs skill pipeline based on mode."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys

from src.models.config import AgentConfig
from src.skills.collect import collect
from src.skills.notify import BriefNotification, NotificationMessage, notify
from src.skills.validate import validate, write_audit_entry
from src.utils.git import clone_data_repo
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


def _resolve_data_dir(config: AgentConfig, repo: str) -> str:
    """Resolve the data directory for a specific repo within the data repo clone."""
    # Sanitize repo name for use as directory (owner/repo -> owner/repo)
    return os.path.join(config.data_dir, repo)


def _setup_data_repo(config: AgentConfig) -> str:
    """Clone the data repo and return the clone path."""
    clone_path = clone_data_repo(config.data_repo, config.branch)
    # Override data_dir to be inside the cloned repo
    return clone_path


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
    clone_path = _setup_data_repo(config)

    try:
        for repo in config.repos:
            logger.info("=== Processing %s ===", repo)
            data_dir = os.path.join(clone_path, config.data_dir, repo)

            try:
                # Collect
                data = await collect(config.token, repo)
                logger.info("Collected data for %s", repo)

                # Validate
                result = validate(data, data_dir)
                write_audit_entry(data, result, data_dir)

                if not result.ok:
                    msg = NotificationMessage(
                        subject=f"Traffic Agent Error: {repo}",
                        body=f"Validation failed for {repo}.\nErrors: {result.errors}",
                        level="error",
                    )
                    await notify(config.notify, msg)
                    continue

                # Store (without commit — we commit once at the end)
                from src.skills.store import store

                store(data, data_dir, config.branch)

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
                _write_failure_audit(repo, exc, data_dir)

                msg = NotificationMessage(
                    subject=f"Traffic Agent Error: {repo}",
                    body=f"Failed to collect traffic data for {repo}: {exc}",
                    level="error",
                )
                await notify(config.notify, msg)

        # Commit and push all changes to data repo at once
        from src.utils.git import commit_and_push

        repos_str = ", ".join(config.repos)
        commit_and_push(
            ["."],
            f"traffic: collect data for {repos_str}",
            config.branch,
            cwd=clone_path,
        )
    finally:
        shutil.rmtree(clone_path, ignore_errors=True)


async def run_report(config: AgentConfig) -> None:
    """Bi-weekly pipeline: Analyze -> Predict -> Propose -> Intelligence -> Notify."""
    from src.skills.analyze import analyze
    from src.skills.export_csv import export_csv
    from src.skills.intelligence import generate_brief, load_prior_actions, save_actions
    from src.skills.predict import predict
    from src.skills.propose import propose
    from src.skills.report import generate_report
    from src.skills.validate import _get_health_status

    clone_path = _setup_data_repo(config)

    try:
        for repo in config.repos:
            logger.info("=== Generating report for %s ===", repo)
            data_dir = os.path.join(clone_path, config.data_dir, repo)

            try:
                analysis = analyze(repo, data_dir)
                predictions = predict(repo, data_dir)
                proposals = propose(analysis, predictions)

                # Generate long report as committed artifact
                generate_report(repo, data_dir, analysis, predictions, proposals)

                # Export CSV snapshot for long-term archival
                export_csv(repo, data_dir)

                # Intelligence layer: LLM brief (or fallback)
                prior_actions = load_prior_actions(data_dir)
                health_status = _get_health_status(data_dir)
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
                    data_dir=data_dir,
                    model=config.model,
                )

                # Persist actions for next run's feedback loop
                if brief.actions:
                    save_actions(brief, data_dir)

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

        # Commit and push all changes to data repo at once
        from src.utils.git import commit_and_push

        repos_str = ", ".join(config.repos)
        commit_and_push(
            ["."],
            f"traffic: bi-weekly report for {repos_str}",
            config.branch,
            cwd=clone_path,
        )
    finally:
        shutil.rmtree(clone_path, ignore_errors=True)


async def main() -> None:
    setup_logging()
    config = AgentConfig.from_env()

    if not config.token:
        logger.error("No token provided")
        sys.exit(1)
    if not config.data_repo:
        logger.error(
            "No data_repo provided. Set the data_repo input to a private repo "
            "(e.g. my-org/traffic-data) to keep your traffic data private."
        )
        sys.exit(1)
    if not config.repos:
        logger.error("No repos configured")
        sys.exit(1)

    logger.info(
        "Starting GitHub Traffic Agent in '%s' mode for %s (data repo: %s)",
        config.mode, config.repos, config.data_repo,
    )

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
