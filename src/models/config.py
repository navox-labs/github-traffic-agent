"""Configuration model parsed from GitHub Action inputs."""

from __future__ import annotations

import json
import os

from pydantic import BaseModel


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    recipient: str


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


class SlackConfig(BaseModel):
    webhook_url: str


class NotifyConfig(BaseModel):
    email: EmailConfig | None = None
    telegram: TelegramConfig | None = None
    slack: SlackConfig | None = None

    @property
    def has_any(self) -> bool:
        return any([self.email, self.telegram, self.slack])


class AgentConfig(BaseModel):
    token: str
    repos: list[str]
    data_dir: str = "traffic-data/"
    branch: str = ""
    mode: str = "collect"
    notify: NotifyConfig = NotifyConfig()

    @classmethod
    def from_env(cls) -> AgentConfig:
        token = os.environ.get("INPUT_TOKEN", "")
        repos_str = os.environ.get("INPUT_REPOS", "")
        repos = [r.strip() for r in repos_str.split(",") if r.strip()] if repos_str else []

        if not repos:
            github_repo = os.environ.get("GITHUB_REPOSITORY", "")
            if github_repo:
                repos = [github_repo]

        notify = _parse_notify_config()

        return cls(
            token=token,
            repos=repos,
            data_dir=os.environ.get("INPUT_DATA_DIR", "traffic-data/"),
            branch=os.environ.get("INPUT_BRANCH", ""),
            mode=os.environ.get("INPUT_MODE", "collect"),
            notify=notify,
        )


def _parse_notify_config() -> NotifyConfig:
    email = None
    telegram = None
    slack = None

    email_str = os.environ.get("INPUT_NOTIFY_EMAIL", "")
    if email_str:
        email = EmailConfig(**json.loads(email_str))

    telegram_str = os.environ.get("INPUT_NOTIFY_TELEGRAM", "")
    if telegram_str and ":" in telegram_str:
        bot_token, chat_id = telegram_str.split(":", 1)
        telegram = TelegramConfig(bot_token=bot_token, chat_id=chat_id)

    slack_str = os.environ.get("INPUT_NOTIFY_SLACK", "")
    if slack_str:
        slack = SlackConfig(webhook_url=slack_str)

    return NotifyConfig(email=email, telegram=telegram, slack=slack)
