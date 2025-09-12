# FastAPI-GitHubApp Examples

Practical examples demonstrating FastAPI-GitHubApp features through a consistent use case: automatically closing GitHub issues.

## Examples

### [01-basic-webhook](01-basic-webhook/)
**Issue Auto-Closer (Basic)** - Simple webhook handling that closes new issues automatically. Good starting point for understanding GitHub App basics.

### [02-configuration](02-configuration/) 
**Issue Auto-Closer (Configuration Demo)** - Same functionality using both environment variables and constructor parameters. Shows configuration approaches.

### [03-oauth2-integration](03-oauth2-integration/)
**Issue Auto-Closer (OAuth2)** - Adds OAuth2 user authentication, session management, and protected endpoints while maintaining issue auto-closing functionality.

### [04-advanced-features](04-advanced-features/)
**Issue Auto-Closer (Advanced)** - Demonstrates rate limiting, retry logic, error handling, and production-ready patterns with comprehensive API protection.

## Consistent Functionality

All examples implement the same core behavior:
- **Automatically close new issues** with a comment
- **Close reopened issues** with a comment  
- **Demonstrate the specific feature** while performing real actions

This approach shows how each feature works in practice rather than just returning data.

## Learning Progression

The examples are designed as a learning progression:

1. **01-basic-webhook** - Start here for GitHub App fundamentals
2. **02-configuration** - Learn different configuration approaches  
3. **03-oauth2-integration** - Add user authentication
4. **04-advanced-features** - Production-ready patterns and rate limiting

Each example builds on concepts from the previous ones while maintaining the same core functionality.

## Quick Start

1. Choose an example directory
2. Copy `.env.example` to `.env` 
3. Configure your GitHub App credentials
4. Run the example and test by creating issues

```bash
cd samples/01-basic-webhook
cp .env.example .env
# Edit .env with your credentials
python app.py
# Create an issue in your test repo to see it get closed
```

## Prerequisites

- GitHub App created at [GitHub Developer Settings](https://github.com/settings/developers)
- Repository permissions: **Issues (Write)**, Metadata (Read)
- Event subscriptions: **Issues**
- Private key and webhook secret generated

All examples use environment variables for configuration. See individual README files for specific setup instructions.
