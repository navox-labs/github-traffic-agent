"""Email notification sender via SMTP."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

from src.models.config import EmailConfig

logger = logging.getLogger(__name__)


async def send_email(config: EmailConfig, subject: str, body: str) -> None:
    """Send an email notification via SMTP (runs in thread to avoid blocking)."""
    await asyncio.to_thread(_send_sync, config, subject, body)


def _send_sync(config: EmailConfig, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = config.username
    msg["To"] = config.recipient

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
        server.starttls()
        server.login(config.username, config.password)
        server.send_message(msg)

    logger.info("Email sent to %s", config.recipient)
