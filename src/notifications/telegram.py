"""Telegram notification sender via Bot API."""

from __future__ import annotations

import logging

import httpx

from src.models.config import TelegramConfig

logger = logging.getLogger(__name__)


async def send_telegram(config: TelegramConfig, subject: str, body: str) -> None:
    """Send a Telegram message via Bot API."""
    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    text = f"*{subject}*\n\n{body}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            json={
                "chat_id": config.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
        )
        resp.raise_for_status()

    logger.info("Telegram message sent to chat %s", config.chat_id)
