# Basic GitHub App

Simple GitHub App that automatically closes issues when they're opened or reopened. Demonstrates basic webhook handling and GitHub API interaction.

## What it does

- Automatically closes new issues with a comment
- Closes reopened issues with a comment
- Provides status endpoints

## Setup

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in your GitHub App credentials in `.env`

3. Run the app:
   ```bash
   python app.py
   ```

4. The app will be available at http://localhost:5000

## GitHub App Configuration

When creating your GitHub App, set:

- **Webhook URL**: `http://your-domain.com/webhooks/github/`
- **Repository permissions**:
  - Issues: **Write** (to close issues and add comments)
  - Metadata: **Read**
- **Subscribe to events**:
  - Issues

## Testing

1. Install the GitHub App on a test repository
2. Create a new issue
3. Watch it get automatically closed with a comment
4. Try reopening the issue - it will be closed again

This demonstrates the core functionality of GitHub Apps: receiving webhooks and taking actions via the GitHub API.
