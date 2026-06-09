"""Agent orchestrator — runs skill pipeline based on mode."""

from __future__ import annotations

import asyncio
import logging
import sys

from src.models.config import AgentConfig
from src.skills.collect import collect
from src.skills.notify import notify, NotificationMessage
from src.skills.store import store, store_and_commit
from src.skills.validate import validate, write_audit_entry
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


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
            msg = NotificationMessage(
                subject=f"Traffic Agent Error: {repo}",
                body=f"Failed to collect traffic data for {repo}: {exc}",
                level="error",
            )
            await notify(config.notify, msg)


async def run_report(config: AgentConfig) -> None:
    """Bi-weekly pipeline: Analyze -> Predict -> Propose -> Report -> Notify."""
    from src.skills.analyze import analyze
    from src.skills.predict import predict
    from src.skills.propose import propose
    from src.skills.report import generate_report

    for repo in config.repos:
        logger.info("=== Generating report for %s ===", repo)
        try:
            analysis = analyze(repo, config.data_dir)
            predictions = predict(repo, config.data_dir)
            proposals = propose(analysis, predictions)
            report_path = generate_report(repo, config.data_dir, analysis, predictions, proposals)

            # Commit report
            from src.utils.git import commit_and_push

            commit_and_push(
                [report_path, str(report_path)],
                f"traffic: bi-weekly report for {repo}",
                config.branch,
            )

            msg = NotificationMessage(
                subject=f"Traffic Report: {repo}",
                body=f"Bi-weekly traffic report generated for {repo}.\nSee {report_path}",
                level="success",
            )
            await notify(config.notify, msg)

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
