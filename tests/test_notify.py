"""Tests for the notify skill."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.config import NotifyConfig, SlackConfig, TelegramConfig
from src.skills.notify import NotificationMessage, notify


@pytest.mark.asyncio
async def test_notify_no_channels():
    config = NotifyConfig()
    msg = NotificationMessage(subject="Test", body="Body")
    # Should not raise
    await notify(config, msg)


@pytest.mark.asyncio
async def test_notify_telegram():
    config = NotifyConfig(
        telegram=TelegramConfig(bot_token="123:ABC", chat_id="456")
    )
    msg = NotificationMessage(subject="Test", body="Body")

    with patch("src.notifications.telegram.send_telegram", new_callable=AsyncMock) as mock_send:
        await notify(config, msg)
        mock_send.assert_called_once_with(config.telegram, "Test", "Body")


@pytest.mark.asyncio
async def test_notify_slack():
    config = NotifyConfig(
        slack=SlackConfig(webhook_url="https://hooks.slack.com/test")
    )
    msg = NotificationMessage(subject="Test", body="Body", level="warning")

    with patch("src.notifications.slack.send_slack", new_callable=AsyncMock) as mock_send:
        await notify(config, msg)
        mock_send.assert_called_once_with(config.slack, "Test", "Body", "warning")


@pytest.mark.asyncio
async def test_notify_channel_failure_doesnt_block_others():
    config = NotifyConfig(
        telegram=TelegramConfig(bot_token="123:ABC", chat_id="456"),
        slack=SlackConfig(webhook_url="https://hooks.slack.com/test"),
    )
    msg = NotificationMessage(subject="Test", body="Body")

    with (
        patch(
            "src.notifications.telegram.send_telegram",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ),
        patch("src.notifications.slack.send_slack", new_callable=AsyncMock) as mock_slack,
    ):
        await notify(config, msg)
        # Slack should still be called even though Telegram failed
        mock_slack.assert_called_once()
