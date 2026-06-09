"""Slack notification sender via webhook."""

from __future__ import annotations

import logging

import httpx

from src.models.config import SlackConfig

logger = logging.getLogger(__name__)

LEVEL_EMOJI = {
    "success": ":white_check_mark:",
    "warning": ":warning:",
    "error": ":x:",
}


async def send_slack(
    config: SlackConfig, subject: str, body: str, level: str = "success"
) -> None:
    """Send a Slack message via incoming webhook."""
    emoji = LEVEL_EMOJI.get(level, "")
    text = f"{emoji} *{subject}*\n{body}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(config.webhook_url, json={"text": text})
        resp.raise_for_status()

    logger.info("Slack notification sent")
