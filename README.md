# GitHub Traffic Agent

Autonomous agent that collects, validates, stores, and analyzes GitHub repository traffic data -- solving the 14-day data retention limit.

[![CI](https://github.com/navox-labs/github-traffic-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/navox-labs/github-traffic-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Why?

GitHub only keeps traffic data (views, clones, popular paths, referrers) for **14 days**. After that, it's gone forever. This agent runs as a GitHub Action on a daily schedule, automatically preserving your traffic data and generating analysis reports.

## Features

- **Daily collection** of views, clones, popular paths, and referrers
- **Self-validating pipeline** with schema, completeness, and continuity checks
- **Long-term storage** as JSON files committed to your repo
- **Bi-weekly analysis reports** with trends, anomaly detection, and predictions
- **Actionable proposals** based on traffic patterns
- **Multi-channel notifications** via Email, Telegram, and/or Slack
- **100% free** -- runs on GitHub Actions, no external services needed

## Quick Start

### 1. Create a Personal Access Token

Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens) and create a token with `repo` scope.

Add it as a repository secret named `TRAFFIC_TOKEN`.

### 2. Add the Workflow

Create `.github/workflows/traffic.yml`:

```yaml
name: GitHub Traffic Agent
on:
  schedule:
    - cron: '0 3 * * *'       # Daily at 3 AM UTC
    - cron: '0 4 1,15 * *'    # Bi-weekly reports
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
      - uses: navox-labs/github-traffic-agent@v1
        with:
          token: ${{ secrets.TRAFFIC_TOKEN }}
          mode: ${{ github.event.schedule == '0 4 1,15 * *' && 'report' || github.event.inputs.mode || 'collect' }}
```

### 3. (Optional) Add Notifications

```yaml
          notify_telegram: ${{ secrets.TELEGRAM_CONFIG }}   # bot_token:chat_id
          notify_slack: ${{ secrets.SLACK_WEBHOOK }}         # Webhook URL
          notify_email: ${{ secrets.EMAIL_CONFIG }}          # JSON string
```

## Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `token` | Yes | -- | GitHub PAT with `repo` scope |
| `repos` | No | current repo | Comma-separated `owner/repo` list |
| `data_dir` | No | `traffic-data/` | Directory for data files |
| `branch` | No | default branch | Branch to commit data to |
| `mode` | No | `collect` | `collect` (daily) or `report` (bi-weekly) |
| `notify_email` | No | -- | SMTP config as JSON string |
| `notify_telegram` | No | -- | `bot_token:chat_id` format |
| `notify_slack` | No | -- | Slack webhook URL |

## Data Structure

```
traffic-data/
  memory/
    views.json          # Historical daily views
    clones.json         # Historical daily clones
    paths/              # Daily popular paths snapshots
    referrers/          # Daily popular referrers snapshots
    audit-log.json      # Run audit log
  reports/
    YYYY-MM-DD-report.md  # Bi-weekly analysis reports
```

## How It Works

### Daily Pipeline (collect mode)
1. **Collect** -- Fetches traffic data from GitHub API
2. **Validate** -- Checks schema, completeness, and continuity
3. **Store** -- Merges with existing data, deduplicates, commits
4. **Notify** -- Sends digest to configured channels

### Bi-weekly Pipeline (report mode)
1. **Analyze** -- Computes trends, detects anomalies
2. **Predict** -- Forecasts next 14 days
3. **Propose** -- Generates actionable recommendations
4. **Report** -- Writes Markdown report
5. **Notify** -- Sends summary with link to report

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

MIT
