# Setup Guide

## Prerequisites

- A GitHub repository you want to track
- A GitHub Personal Access Token (PAT) with `repo` scope

## Step 1: Create a Personal Access Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Give it a descriptive name like "Traffic Agent"
4. Select the `repo` scope (full control of private repositories)
5. Click "Generate token"
6. Copy the token -- you won't see it again

## Step 2: Add the Token as a Repository Secret

1. Go to your repository's Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Name: `TRAFFIC_TOKEN`
4. Value: paste your PAT
5. Click "Add secret"

## Step 3: Create the Workflow File

Create `.github/workflows/traffic.yml` in your repository with the content from the README quick start section.

## Step 4: (Optional) Configure Notifications

### Telegram
1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Add secret `TELEGRAM_CONFIG` with value `BOT_TOKEN:CHAT_ID`

### Slack
1. Create an [Incoming Webhook](https://api.slack.com/messaging/webhooks) for your workspace
2. Add secret `SLACK_WEBHOOK` with the webhook URL

### Email
1. Add secret `EMAIL_CONFIG` with a JSON string:
```json
{"smtp_host":"smtp.gmail.com","smtp_port":587,"username":"you@gmail.com","password":"app-password","recipient":"you@gmail.com"}
```

## Step 5: Verify

1. Go to Actions tab in your repository
2. Select the "GitHub Traffic Agent" workflow
3. Click "Run workflow" and select `collect` mode
4. Check that `traffic-data/` directory appears with data files

## Monitoring Multiple Repos

To track multiple repositories from a single workflow, use the `repos` input:

```yaml
with:
  token: ${{ secrets.TRAFFIC_TOKEN }}
  repos: 'owner/repo1,owner/repo2,owner/repo3'
```

Note: Your PAT must have access to all listed repositories.
