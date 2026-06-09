"""Tests for the intelligence layer: Brief contract, caps, fallback, rendering, loop."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.models.schemas import (
    BRIEF_MAX_ACTION_WORDS,
    BRIEF_MAX_ACTIONS,
    BRIEF_MAX_HEADLINE_WORDS,
    Brief,
    Prediction,
    Proposal,
    TrendData,
)
from src.skills.analyze import AnalysisResult
from src.skills.format_brief import (
    format_brief,
    format_email_body,
    format_email_subject,
    format_slack,
    format_telegram,
)
from src.skills.intelligence import (
    MAX_DIGEST_WORDS,
    generate_brief,
    load_prior_actions,
    save_actions,
)

# --- Fixtures ---


@pytest.fixture
def sample_analysis() -> AnalysisResult:
    views_df = pd.DataFrame(
        [{"date": date(2026, 6, d), "count": 10 + d, "uniques": 5 + d} for d in range(1, 8)]
    )
    clones_df = pd.DataFrame(
        [{"date": date(2026, 6, d), "count": 3 + d, "uniques": 2} for d in range(1, 8)]
    )
    return AnalysisResult(
        repo="navox-labs/test-repo",
        views_df=views_df,
        clones_df=clones_df,
        trends=[
            TrendData(
                period="7-day",
                avg_daily_views=14.0,
                avg_daily_clones=6.0,
                views_growth_pct=38.0,
                clones_growth_pct=12.0,
            )
        ],
        anomalies=[],
        top_referrers=[{"name": "github.com", "total_count": 40}],
        top_paths=[{"name": "/repo", "total_count": 50}],
    )


@pytest.fixture
def sample_proposals() -> list[Proposal]:
    return [
        Proposal(
            title="Add a 30-sec quickstart to the README",
            description="Clones are growing fast, help new users get started.",
            confidence=0.8,
            trigger="clone_exceeds_views_7d",
        ),
        Proposal(
            title="Drop the HN thread link in release notes",
            description="HN is a top referrer.",
            confidence=0.7,
            trigger="referrer_spike_hn",
        ),
    ]


@pytest.fixture
def sample_predictions() -> list[Prediction]:
    return [
        Prediction(
            date=date(2026, 6, 10),
            metric="views",
            predicted=15.0,
            lower_bound=8.0,
            upper_bound=22.0,
        )
    ]


# --- Brief JSON contract ---


def test_brief_model_fields():
    brief = Brief(
        headline="Clones up 38% WoW",
        actions=["Add quickstart to README"],
        alert=False,
        verdict="growing",
    )
    data = brief.model_dump()
    assert "headline" in data
    assert "actions" in data
    assert "alert" in data
    assert "verdict" in data
    assert isinstance(data["actions"], list)


def test_brief_verdict_values():
    for v in ("growing", "flat", "declining"):
        brief = Brief(headline="test", verdict=v)
        assert brief.verdict == v


# --- Length-cap enforcement ---


def test_headline_word_cap():
    long_headline = " ".join(["word"] * 30)
    brief = Brief(headline=long_headline, verdict="flat")
    brief.enforce_caps()
    assert len(brief.headline.split()) <= BRIEF_MAX_HEADLINE_WORDS


def test_action_word_cap():
    long_action = " ".join(["word"] * 20)
    brief = Brief(headline="test", actions=[long_action], verdict="flat")
    brief.enforce_caps()
    assert len(brief.actions[0].split()) <= BRIEF_MAX_ACTION_WORDS


def test_max_two_actions():
    brief = Brief(
        headline="test",
        actions=["a", "b", "c", "d"],
        verdict="flat",
    )
    brief.enforce_caps()
    assert len(brief.actions) <= BRIEF_MAX_ACTIONS


def test_total_word_count():
    brief = Brief(
        headline="Views up 38 pct week over week",
        actions=["Add quickstart", "Post on HN"],
        verdict="growing",
        loop_comment="Prior tip tracked well",
        health_token="",
    )
    assert brief.total_words() == 16


def test_phone_notification_fits():
    """The entire digest must fit a phone notification: <= 60 words."""
    brief = Brief(
        headline="Clones up 38% WoW from 52 to 72 mostly HN",
        actions=[
            "Add a 30-sec quickstart to README",
            "Drop the HN link in release notes",
        ],
        verdict="growing",
        loop_comment="Prior onboarding tip saw clones rise 22 pct",
    )
    brief.enforce_caps()
    assert brief.total_words() <= MAX_DIGEST_WORDS


# --- Fallback from rules ---


def test_from_rules_fallback(sample_proposals: list[Proposal]):
    trends = [
        TrendData(
            period="7-day",
            avg_daily_views=14.0,
            avg_daily_clones=6.0,
            views_growth_pct=38.0,
            clones_growth_pct=12.0,
        )
    ]
    brief = Brief.from_rules(sample_proposals, trends)
    assert brief.verdict == "growing"
    assert len(brief.actions) <= 2
    assert len(brief.headline.split()) <= BRIEF_MAX_HEADLINE_WORDS


def test_from_rules_declining():
    trends = [
        TrendData(
            period="7-day",
            avg_daily_views=5.0,
            avg_daily_clones=2.0,
            views_growth_pct=-20.0,
            clones_growth_pct=-15.0,
        )
    ]
    brief = Brief.from_rules([], trends)
    assert brief.verdict == "declining"


def test_from_rules_no_trends():
    brief = Brief.from_rules([], None)
    assert brief.verdict == "flat"
    assert "Insufficient" in brief.headline


# --- LLM fallback on failure ---


def test_generate_brief_no_api_key(
    sample_analysis: AnalysisResult,
    sample_predictions: list[Prediction],
    sample_proposals: list[Proposal],
):
    """Without API key, should return rule-based fallback without crashing."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
        brief = generate_brief(
            analysis=sample_analysis,
            predictions=sample_predictions,
            proposals=sample_proposals,
        )
    assert isinstance(brief, Brief)
    assert brief.verdict in ("growing", "flat", "declining")
    assert len(brief.headline.split()) <= BRIEF_MAX_HEADLINE_WORDS


def test_generate_brief_llm_failure(
    sample_analysis: AnalysisResult,
    sample_predictions: list[Prediction],
    sample_proposals: list[Proposal],
):
    """On LLM failure, should fall back gracefully and signal degraded health."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=False):
        with patch("src.skills.intelligence._call_llm", return_value=None):
            brief = generate_brief(
                analysis=sample_analysis,
                predictions=sample_predictions,
                proposals=sample_proposals,
            )
    assert isinstance(brief, Brief)
    assert brief.verdict in ("growing", "flat", "declining")
    # Key was set but LLM failed — health_token should signal it
    assert "fallback" in brief.health_token.lower()


def test_generate_brief_invalid_json_from_llm(
    sample_analysis: AnalysisResult,
    sample_predictions: list[Prediction],
    sample_proposals: list[Proposal],
):
    """If LLM returns garbage JSON fields, fallback kicks in."""
    bad_response = {"headline": 12345, "verdict": "invalid_value", "actions": "not a list"}
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=False):
        with patch("src.skills.intelligence._call_llm", return_value=bad_response):
            brief = generate_brief(
                analysis=sample_analysis,
                predictions=sample_predictions,
                proposals=sample_proposals,
            )
    assert isinstance(brief, Brief)
    # Should have corrected the invalid verdict
    assert brief.verdict in ("growing", "flat", "declining")


def test_generate_brief_llm_success(
    sample_analysis: AnalysisResult,
    sample_predictions: list[Prediction],
    sample_proposals: list[Proposal],
):
    """Simulated successful LLM response."""
    good_response = {
        "headline": "Clones surged 38% WoW, driven by HN traffic",
        "actions": ["Add quickstart to README", "Link HN in release notes"],
        "alert": False,
        "verdict": "growing",
        "loop_comment": "",
    }
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=False):
        with patch("src.skills.intelligence._call_llm", return_value=good_response):
            brief = generate_brief(
                analysis=sample_analysis,
                predictions=sample_predictions,
                proposals=sample_proposals,
            )
    assert brief.headline == "Clones surged 38% WoW, driven by HN traffic"
    assert len(brief.actions) == 2
    assert brief.verdict == "growing"


# --- Rendering ---


def test_format_slack():
    brief = Brief(
        headline="clones +38% WoW (52 to 72), mostly from HN",
        actions=["Add a 30-sec quickstart to the README", "Drop the HN link in release notes"],
        alert=False,
        verdict="growing",
    )
    text = format_slack(brief, "navox/repo")
    assert "navox/repo" in text
    assert "clones" in text
    assert "\u2022" in text  # bullet


def test_format_telegram():
    brief = Brief(
        headline="clones +38% WoW",
        actions=["Add quickstart"],
        verdict="growing",
        loop_comment="Prior tip tracked well",
    )
    text = format_telegram(brief, "navox/repo")
    assert "*navox/repo*" in text
    assert "_Prior tip tracked well_" in text


def test_format_email():
    brief = Brief(
        headline="clones +38% WoW",
        actions=["Add quickstart"],
        verdict="growing",
    )
    subject = format_email_subject(brief, "navox/repo")
    body = format_email_body(brief, "navox/repo")
    assert "navox/repo" in subject
    assert "quickstart" in body


def test_format_brief_dispatcher():
    brief = Brief(headline="test", verdict="flat")
    for channel in ("slack", "telegram", "email_subject", "email_body"):
        result = format_brief(brief, channel, "test/repo")
        assert isinstance(result, str)
        assert len(result) > 0


# --- Loop evaluation (Step 3) ---


def test_save_and_load_actions(tmp_path):
    data_dir = str(tmp_path / "traffic-data")
    (tmp_path / "traffic-data" / "memory").mkdir(parents=True)

    brief = Brief(
        headline="test",
        actions=["Add quickstart", "Post on HN"],
        verdict="growing",
    )
    save_actions(brief, data_dir)
    loaded = load_prior_actions(data_dir)

    assert len(loaded) == 2
    assert loaded[0]["action"] == "Add quickstart"
    assert "date" in loaded[0]


def test_loop_comment_in_rendering():
    brief = Brief(
        headline="Views flat this week",
        actions=["Try posting on Reddit"],
        verdict="flat",
        loop_comment="Last tip (onboarding) led to clones +22%",
    )
    text = format_slack(brief, "navox/repo")
    assert "Last tip" in text
    assert "+22%" in text


# --- Health token (Step 4) ---


def test_health_token_healthy():
    brief = Brief(headline="test", verdict="flat", health_token="")
    text = format_slack(brief, "repo")
    # No health line when healthy
    lines = text.strip().split("\n")
    assert len(lines) == 1


def test_health_token_degraded():
    brief = Brief(
        headline="test",
        verdict="flat",
        health_token="last error: connection reset",
    )
    text = format_slack(brief, "repo")
    assert "connection reset" in text


# --- Notification fits phone screen ---


def test_all_renderings_fit_phone():
    """All channel renderings should be compact."""
    brief = Brief(
        headline="Clones up 38% WoW from HN traffic",
        actions=["Add quickstart to README", "Link HN in releases"],
        verdict="growing",
        loop_comment="Prior tip tracked",
        health_token="",
    )
    for channel in ("slack", "telegram"):
        text = format_brief(brief, channel, "navox/repo")
        # Should fit in ~280 chars (tweet length) as a rough phone-notification proxy
        assert len(text) < 500, f"{channel} rendering too long: {len(text)} chars"
