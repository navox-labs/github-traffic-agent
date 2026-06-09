# GitHub Traffic Agent

AI-powered agent that collects GitHub traffic data, reads it with Claude, and sends you a phone-sized brief you can act on -- solving the 14-day data retention limit.

[![CI](https://github.com/navox-labs/github-traffic-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/navox-labs/github-traffic-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What You Get

A notification that fits a phone lock screen:

```
📈 navox/repo: clones +38% WoW (52→72), mostly from HN.
• Add a 30-sec quickstart to the README.
• Drop the HN thread link in your next release notes.
Last tip (onboarding) → clones +22%. Keep going.
```

That's it. No dashboards, no walls of text. The agent collects data daily, and when you ask for a report, Claude reads everything and writes the one message that matters.

## The Story

As a solo founder who is also a builder, I can't live without my AI agents. I built my own team of agents to help me take my concepts from start to finish, while I handle my own marketing, posting, and blogging across many channels.

One of the most important signals that drives my product decisions is repo traffic. I build in public, open-source, and solo -- so monitoring traffic and paying attention to trends is a critical part of product development.

I use GitHub, and unfortunately GitHub only keeps and displays **2 weeks** of traffic data. I really wish I had built this agent earlier. I remember when my network repo approached **1,000 clones in a single day**, but I just didn't keep any record of it. Plus, I only discovered GitHub Insights traffic recently.

I didn't want this agent to just be a data collector. I wanted a proactive, fully experienced data scientist agent that collects, analyzes, predicts, and proposes -- and sends me a notification just in case I've got my hands busy somewhere else.

## How It Works

The data pipeline is deterministic and tested -- the LLM never writes, edits, or computes stored numbers. It only reads validated outputs and writes prose.

### Daily Pipeline (collect mode)
1. **Collect** -- Fetches views, clones, paths, and referrers from the GitHub API
2. **Validate** -- Checks schema, completeness, continuity; warns on zero-data or gaps
3. **Store** -- Merges with existing data, deduplicates by date, atomic writes
4. **Notify** -- Sends collection digest to configured channels

### Report Pipeline (report mode)
1. **Analyze** -- Computes 7-day and 30-day trends, detects anomalies (z-score)
2. **Predict** -- Forecasts next 14 days (moving average + linear regression blend)
3. **Propose** -- Generates rule-based recommendations from patterns
4. **Intelligence** -- Claude reads all of the above and writes a Brief (or falls back to rules)
5. **Report** -- Commits a full Markdown report as an artifact
6. **Notify** -- Sends the Brief to Slack, Telegram, and/or email (each rendered natively)

### The Feedback Loop
Each Brief's actions are persisted. Next report, the agent passes prior actions + traffic-since to Claude, which judges in one line whether the advice tracked. The agent grades its own advice.

## Quick Start

### Step 1: Create a GitHub PAT

Go to [GitHub Settings > Personal access tokens](https://github.com/settings/tokens) and create a token with `repo` scope. This is needed to read traffic data (GitHub requires push access).

Add it as a repository secret:
```bash
gh secret set TRAFFIC_TOKEN
```

### Step 2: (Optional) Add an Anthropic API Key

For AI-powered briefs, add your Anthropic API key. Without it, the agent still works -- it just uses rule-based summaries instead of Claude.

```bash
gh secret set ANTHROPIC_API_KEY
```

### Step 3: Add the Workflow

Create `.github/workflows/traffic.yml`:

```yaml
name: GitHub Traffic Agent
on:
  schedule:
    - cron: '0 3 * * *'       # Daily collection at 3 AM UTC
    - cron: '0 4 1,15 * *'    # Bi-weekly reports on 1st and 15th
  workflow_dispatch:
    inputs:
      mode:
        description: 'Run mode'
        default: 'collect'
        type: choice
        options: [collect, report]

jobs:
  traffic:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: navox-labs/github-traffic-agent@main
        with:
          token: ${{ secrets.TRAFFIC_TOKEN }}
          mode: ${{ github.event.schedule == '0 4 1,15 * *' && 'report' || github.event.inputs.mode || 'collect' }}
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Step 4: Run It

Trigger the first collection manually:
```bash
gh workflow run traffic.yml -f mode=collect
```

Once you have a few days of data, trigger a report:
```bash
gh workflow run traffic.yml -f mode=report
```

### Step 5: (Optional) Add Notifications

Add any combination of channels to your workflow:

```yaml
          notify_slack: ${{ secrets.SLACK_WEBHOOK }}
          notify_telegram: ${{ secrets.TELEGRAM_CONFIG }}   # bot_token:chat_id
          notify_email: ${{ secrets.EMAIL_CONFIG }}          # JSON string
```

### Step 6: (Optional) Add Product Context

Give Claude context about your repo for smarter briefs:

```yaml
          product_context: '{"description": "CLI tool for managing Docker containers", "audience": "DevOps engineers"}'
```

## Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `token` | Yes | -- | GitHub PAT with `repo` scope |
| `repos` | No | current repo | Comma-separated `owner/repo` list |
| `data_dir` | No | `traffic-data/` | Directory for data files |
| `branch` | No | default branch | Branch to commit data to |
| `mode` | No | `collect` | `collect` or `report` |
| `anthropic_api_key` | No | -- | Anthropic API key for AI briefs |
| `model` | No | `claude-sonnet-4-20250514` | Claude model ID |
| `product_context` | No | -- | JSON with `description` and `audience` |
| `notify_slack` | No | -- | Slack webhook URL |
| `notify_telegram` | No | -- | `bot_token:chat_id` format |
| `notify_email` | No | -- | SMTP config as JSON string |

## Data Structure

```
traffic-data/
  memory/
    views.json              # Historical daily views
    clones.json             # Historical daily clones
    paths/                  # Daily popular paths snapshots
    referrers/              # Daily popular referrers snapshots
    audit-log.json          # Run audit log
    brief-actions.json      # Persisted actions for feedback loop
  reports/
    YYYY-MM-DD-report.md    # Analysis reports (committed artifacts)
```

## Design Principles

- **Deterministic data spine.** The LLM never writes, edits, or computes stored numbers. Collection, merge/dedup, storage, and stats are deterministic and tested.
- **Output is short by contract.** Headline max 15 words, max 2 actions at 12 words each. Enforced in code, not by prompt hope.
- **LLM is non-fatal.** On API error or invalid JSON, falls back to a terse rule-based message. The agent never crashes or goes silent because the model failed. A health token surfaces when the LLM layer is degraded.
- **Each channel renders natively.** Slack gets plain text, Telegram gets markdown, email gets subject/body split.

## Development

```bash
# Install
pip install -e ".[dev]"

# Tests (61 tests)
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

MIT
