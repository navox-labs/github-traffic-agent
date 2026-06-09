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


async def notify(config: NotifyConfig, message: NotificationMessage) -> None:
    """Send notification to all configured channels. Each channel is independent."""
    if not config.has_any:
        logger.info("No notification channels configured, skipping")
        return

    if config.email:
        try:
            from src.notifications.email import send_email

            await send_email(config.email, message.subject, message.body)
            logger.info("Email notification sent")
        except Exception as exc:
            logger.error("Email notification failed: %s", exc)

    if config.telegram:
        try:
            from src.notifications.telegram import send_telegram

            await send_telegram(config.telegram, message.subject, message.body)
            logger.info("Telegram notification sent")
        except Exception as exc:
            logger.error("Telegram notification failed: %s", exc)

    if config.slack:
        try:
            from src.notifications.slack import send_slack

            await send_slack(config.slack, message.subject, message.body, message.level)
            logger.info("Slack notification sent")
        except Exception as exc:
            logger.error("Slack notification failed: %s", exc)
