"""Skill: Dispatch notifications to configured channels."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.models.config import NotifyConfig

logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    subject: str
    body: str
    level: str = "success"  # success | warning | error


@dataclass
class BriefNotification:
    """A Brief-aware notification that renders per channel."""

    brief: object  # Brief, but avoid circular import
    repo: str
    level: str = "success"


async def notify(
    config: NotifyConfig,
    message: NotificationMessage | BriefNotification,
) -> None:
    """Send notification to all configured channels. Each channel is independent."""
    if not config.has_any:
        logger.info("No notification channels configured, skipping")
        return

    # Resolve per-channel content
    if isinstance(message, BriefNotification):
        from src.models.schemas import Brief
        from src.skills.format_brief import (
            format_email_body,
            format_email_subject,
            format_slack,
            format_telegram,
        )

        brief: Brief = message.brief  # type: ignore[assignment]
        repo = message.repo
        level = message.level

        slack_text = format_slack(brief, repo)
        telegram_text = format_telegram(brief, repo)
        email_subj = format_email_subject(brief, repo)
        email_body = format_email_body(brief, repo)
    else:
        level = message.level
        slack_text = f"*{message.subject}*\n{message.body}"
        telegram_text = f"*{message.subject}*\n\n{message.body}"
        email_subj = message.subject
        email_body = message.body

    if config.email:
        try:
            from src.notifications.email import send_email

            await send_email(config.email, email_subj, email_body)
            logger.info("Email notification sent")
        except Exception as exc:
            logger.error("Email notification failed: %s", exc)

    if config.telegram:
        try:
            from src.notifications.telegram import send_telegram

            await send_telegram(config.telegram, telegram_text)
            logger.info("Telegram notification sent")
        except Exception as exc:
            logger.error("Telegram notification failed: %s", exc)

    if config.slack:
        try:
            from src.notifications.slack import send_slack

            await send_slack(config.slack, slack_text, level)
            logger.info("Slack notification sent")
        except Exception as exc:
            logger.error("Slack notification failed: %s", exc)
