"""Tests for the notify skill."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.config import NotifyConfig, SlackConfig, TelegramConfig
from src.models.schemas import Brief
from src.skills.notify import BriefNotification, NotificationMessage, notify


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
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert args[0][0] == config.telegram
        assert "Test" in args[0][1]


@pytest.mark.asyncio
async def test_notify_slack():
    config = NotifyConfig(
        slack=SlackConfig(webhook_url="https://hooks.slack.com/test")
    )
    msg = NotificationMessage(subject="Test", body="Body", level="warning")

    with patch("src.notifications.slack.send_slack", new_callable=AsyncMock) as mock_send:
        await notify(config, msg)
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert args[0][0] == config.slack
        assert "warning" in args[0][2] or args[0][2] == "warning"


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


@pytest.mark.asyncio
async def test_notify_brief_renders_per_channel():
    """BriefNotification should render differently for each channel."""
    config = NotifyConfig(
        telegram=TelegramConfig(bot_token="123:ABC", chat_id="456"),
        slack=SlackConfig(webhook_url="https://hooks.slack.com/test"),
    )
    brief = Brief(
        headline="clones +38% WoW",
        actions=["Add quickstart"],
        verdict="growing",
    )
    bn = BriefNotification(brief=brief, repo="test/repo", level="success")

    with (
        patch(
            "src.notifications.telegram.send_telegram", new_callable=AsyncMock
        ) as mock_tg,
        patch(
            "src.notifications.slack.send_slack", new_callable=AsyncMock
        ) as mock_slack,
    ):
        await notify(config, bn)

        # Telegram should get markdown bold
        tg_text = mock_tg.call_args[0][1]
        assert "*test/repo*" in tg_text

        # Slack should get plain text (no markdown bold)
        slack_text = mock_slack.call_args[0][1]
        assert "test/repo" in slack_text
        assert "*test/repo*" not in slack_text
