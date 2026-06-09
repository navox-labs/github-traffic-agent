"""Render a Brief for different notification channels."""

from __future__ import annotations

from src.models.schemas import Brief

VERDICT_EMOJI = {
    "growing": "\U0001f4c8",   # chart increasing
    "declining": "\U0001f4c9", # chart decreasing
    "flat": "\u2796",          # minus
}


def _verdict_icon(verdict: str) -> str:
    return VERDICT_EMOJI.get(verdict, "")


def _body_lines(brief: Brief, repo: str) -> list[str]:
    """Common body lines shared across channels."""
    icon = _verdict_icon(brief.verdict)
    lines = [f"{icon} {repo}: {brief.headline}"]

    for action in brief.actions:
        lines.append(f"\u2022 {action}")

    if brief.loop_comment:
        lines.append(brief.loop_comment)

    if brief.health_token:
        lines.append(brief.health_token)

    return lines


def format_slack(brief: Brief, repo: str) -> str:
    """Single Slack block: plain text, no headers, no tables."""
    return "\n".join(_body_lines(brief, repo))


def format_telegram(brief: Brief, repo: str) -> str:
    """Short Markdown for Telegram."""
    icon = _verdict_icon(brief.verdict)
    lines = [f"{icon} *{repo}*: {brief.headline}"]

    for action in brief.actions:
        lines.append(f"\u2022 {action}")

    if brief.loop_comment:
        lines.append(f"_{brief.loop_comment}_")

    if brief.health_token:
        lines.append(brief.health_token)

    return "\n".join(lines)


def format_email_subject(brief: Brief, repo: str) -> str:
    """Email subject = headline."""
    icon = _verdict_icon(brief.verdict)
    return f"{icon} {repo}: {brief.headline}"


def format_email_body(brief: Brief, repo: str) -> str:
    """Email body = actions + loop comment."""
    lines: list[str] = []
    for action in brief.actions:
        lines.append(f"- {action}")
    if brief.loop_comment:
        lines.append(f"\n{brief.loop_comment}")
    if brief.health_token:
        lines.append(f"\n{brief.health_token}")
    return "\n".join(lines) if lines else "No actions needed."


def format_brief(brief: Brief, channel: str, repo: str = "") -> str:
    """Unified dispatcher for channel rendering."""
    if channel == "slack":
        return format_slack(brief, repo)
    elif channel == "telegram":
        return format_telegram(brief, repo)
    elif channel == "email_subject":
        return format_email_subject(brief, repo)
    elif channel == "email_body":
        return format_email_body(brief, repo)
    else:
        return format_slack(brief, repo)
