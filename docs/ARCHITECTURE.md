# Architecture

## Overview

GitHub Traffic Agent is a **skill-based autonomous agent** that runs as a Docker-based GitHub Action. It orchestrates a pipeline of specialized skills on two schedules:

- **Daily (3 AM UTC):** Collect > Validate > Store > Notify
- **Bi-weekly:** Analyze > Predict > Propose > Report > Notify

## Agent Skills

### Collect (`src/skills/collect.py`)
Calls GitHub REST API endpoints for views, clones, popular paths, and referrers. Uses `httpx` for async HTTP with automatic retry (exponential backoff, up to 3 attempts).

### Validate (`src/skills/validate.py`)
Runs three validation checks:
1. **Schema validation** -- Pydantic model parsing
2. **Completeness check** -- Verifies data points present, no negative values
3. **Continuity check** -- Compares with last stored data, flags gaps

Every run produces an audit log entry regardless of outcome.

### Store (`src/skills/store.py`)
Manages long-term data storage:
- Views/clones: append-merge into single JSON file, deduplicated by date
- Paths/referrers: daily snapshots as separate JSON files
- Commits all changes in a single git commit

### Notify (`src/skills/notify.py`)
Dispatches to configured channels (Email, Telegram, Slack). Each channel is independent -- one failing doesn't block others.

### Analyze (`src/skills/analyze.py`)
Statistical analysis on historical data:
- Daily/weekly/monthly trends with growth rates
- Anomaly detection (traffic exceeding 2 standard deviations)
- Top referrers and popular content aggregation

### Predict (`src/skills/predict.py`)
14-day traffic forecasting using:
- 7-day moving average
- Linear regression on 30-day window
- Blended prediction with confidence intervals

Requires minimum 30 days of historical data.

### Propose (`src/skills/propose.py`)
Rule-based engine generating actionable proposals:
- Traffic drops > 30% trigger content refresh suggestions
- Clone growth exceeding views triggers onboarding improvements
- Referrer spikes trigger community engagement proposals
- Proposals scored by confidence

### Report (`src/skills/report.py`)
Compiles Markdown reports with:
- Summary table (totals and daily averages)
- Trend analysis with growth rates
- Top referrers and popular content
- Anomaly alerts
- Predictions table
- Actionable proposals with confidence scores

## Self-Validation Pipeline

```
Collect
  > Schema Validation (Pydantic parse)
    > PASS > Completeness Check
      > PASS > Continuity Check
        > PASS > Store > Notify (success)
        > FAIL > Log gap warning > Store partial > Notify (warning)
      > FAIL > Log issue > Retry collect (up to 3x) > Notify (error)
    > FAIL > Log schema error > Retry collect (up to 3x) > Notify (error)
```

## Data Flow

```
GitHub API  -->  Collect  -->  Validate  -->  Store  -->  Git Commit
                                                            |
                                                         Notify
                                                            |
                              Analyze  <--  Historical Data
                                |
                             Predict
                                |
                             Propose
                                |
                              Report  -->  Git Commit  -->  Notify
```

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| HTTP Client | httpx | Async support, clean API |
| Data Models | Pydantic v2 | Validation + serialization |
| Data Analysis | pandas + numpy | Industry standard, performant |
| Notifications | smtplib + httpx | No external dependencies |
| Container | Python 3.12 slim | Small image, latest features |
| CI/CD | GitHub Actions | Zero cost, native integration |
