"""Skill: LLM-powered intelligence layer that reads analysis and emits a Brief."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from src.models.schemas import Brief, Prediction, Proposal
from src.skills.analyze import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a terse growth analyst. Return JSON only.
Given traffic data for a GitHub repo, produce a JSON object with exactly these fields:
- headline: the single most important change with the number (max 15 words)
- actions: array of 0-2 imperative items, each tied to a data point (max 12 words each)
- alert: boolean, true ONLY if it needs attention right now
- verdict: one of "growing", "flat", "declining"
- loop_comment: if prior_actions provided, one sentence on whether advice tracked
  (max 15 words). Otherwise empty string.

Be specific. Use numbers. No filler. No headers. No markdown. JSON only."""

MAX_DIGEST_WORDS = 60


def _build_user_prompt(
    analysis: AnalysisResult,
    predictions: list[Prediction],
    proposals: list[Proposal],
    product_context: dict[str, str],
    prior_actions: list[dict[str, str]] | None = None,
    health_status: str = "",
) -> str:
    """Build the user prompt from deterministic data."""
    parts: list[str] = []

    if product_context:
        parts.append(f"Repo: {product_context.get('repo', 'unknown')}")
        if product_context.get("description"):
            parts.append(f"What it does: {product_context['description']}")
        if product_context.get("audience"):
            parts.append(f"Audience: {product_context['audience']}")

    # Trends
    if analysis.trends:
        for t in analysis.trends:
            parts.append(
                f"Trend ({t.period}): views {t.views_growth_pct:+.1f}%, "
                f"clones {t.clones_growth_pct:+.1f}%, "
                f"avg {t.avg_daily_views:.0f} views/day, {t.avg_daily_clones:.0f} clones/day"
            )

    # Referrers
    if analysis.top_referrers:
        refs = ", ".join(
            f"{r['name']}({r['total_count']})" for r in analysis.top_referrers[:5]
        )
        parts.append(f"Top referrers: {refs}")

    # Anomalies
    if analysis.anomalies:
        for a in analysis.anomalies[:3]:
            parts.append(
                f"Anomaly: {a.metric} {a.direction} on {a.date} "
                f"({a.value:.0f} vs expected {a.expected:.0f})"
            )

    # Predictions summary
    if predictions:
        view_preds = [p for p in predictions if p.metric == "views"]
        if view_preds:
            avg_pred = sum(p.predicted for p in view_preds) / len(view_preds)
            parts.append(f"Predicted avg views next 14d: {avg_pred:.0f}/day")

    # Rule-based proposals
    if proposals:
        for p in proposals[:3]:
            parts.append(f"Proposal ({p.confidence:.0%}): {p.title}")

    # Prior actions for loop evaluation
    if prior_actions:
        parts.append("Prior actions from last report:")
        for pa in prior_actions[-3:]:
            parts.append(f"  - {pa.get('action', '')} (given {pa.get('date', '')})")

    if health_status:
        parts.append(f"Health: {health_status}")

    return "\n".join(parts)


DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _call_llm(
    system: str, user: str, api_key: str, model: str = DEFAULT_MODEL
) -> dict[str, object] | None:
    """Call the Anthropic API. Returns parsed JSON dict or None on failure."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        block = response.content[0]
        if not hasattr(block, "text"):
            logger.warning("LLM returned non-text block: %s", type(block).__name__)
            return None
        text: str = block.text.strip()
        # Handle potential markdown wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result: dict[str, object] = json.loads(text)
        return result
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None


def generate_brief(
    analysis: AnalysisResult,
    predictions: list[Prediction],
    proposals: list[Proposal],
    product_context: dict[str, str] | None = None,
    prior_actions: list[dict[str, str]] | None = None,
    health_status: str = "",
    data_dir: str = "",
    model: str = DEFAULT_MODEL,
) -> Brief:
    """Generate a Brief using the LLM, falling back to rules on any failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # Build fallback first so we always have something
    fallback = Brief.from_rules(proposals, analysis.trends or None)
    fallback.health_token = health_status or ""

    if not api_key:
        logger.info("No ANTHROPIC_API_KEY set, using rule-based brief")
        return fallback

    user_prompt = _build_user_prompt(
        analysis,
        predictions,
        proposals,
        product_context or {},
        prior_actions,
        health_status,
    )

    raw = _call_llm(SYSTEM_PROMPT, user_prompt, api_key, model)
    if raw is None:
        logger.warning("LLM call failed with key set — falling back to rules")
        fallback.health_token = "LLM call failed, using rule-based fallback"
        return fallback

    try:
        raw_actions = raw.get("actions", [])
        actions = list(raw_actions)[:2] if isinstance(raw_actions, list) else []
        brief = Brief(
            headline=str(raw.get("headline", fallback.headline)),
            actions=[str(a) for a in actions],
            alert=bool(raw.get("alert", False)),
            verdict=str(raw.get("verdict", fallback.verdict)),
            loop_comment=str(raw.get("loop_comment", "")),
            health_token=health_status or "",
        )
        brief.enforce_caps()

        # Validate verdict
        if brief.verdict not in ("growing", "flat", "declining"):
            brief.verdict = fallback.verdict

        # Enforce total word cap: trim loop_comment, then actions, then health
        if brief.total_words() > MAX_DIGEST_WORDS:
            brief.loop_comment = ""
        if brief.total_words() > MAX_DIGEST_WORDS:
            brief.actions = brief.actions[:1]
        if brief.total_words() > MAX_DIGEST_WORDS:
            brief.health_token = ""

        return brief
    except Exception as exc:
        logger.warning("Failed to parse LLM response into Brief: %s", exc)
        return fallback


# --- Action persistence for the feedback loop ---

_ACTIONS_FILE = "brief-actions.json"


def save_actions(brief: Brief, data_dir: str) -> None:
    """Persist the Brief's actions with a timestamp for the next run's loop eval."""
    from src.skills.store import _atomic_write

    actions_path = Path(data_dir) / "memory" / _ACTIONS_FILE

    existing: list[dict[str, str]] = []
    if actions_path.exists():
        try:
            existing = json.loads(actions_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    now = datetime.now(UTC).isoformat()
    for action in brief.actions:
        existing.append({"action": action, "date": now})

    # Keep only last 20 entries
    existing = existing[-20:]

    _atomic_write(actions_path, json.dumps(existing, indent=2))


def load_prior_actions(data_dir: str) -> list[dict[str, str]]:
    """Load prior actions for feedback loop evaluation."""
    actions_path = Path(data_dir) / "memory" / _ACTIONS_FILE
    if not actions_path.exists():
        return []
    try:
        result: list[dict[str, str]] = json.loads(actions_path.read_text())
        return result
    except (json.JSONDecodeError, OSError):
        return []
