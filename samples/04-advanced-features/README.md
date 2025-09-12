# Advanced Features

This example demonstrates advanced GitHub App features including rate limiting, retry logic, and error handling.

## Features

- Automatic rate limit handling with exponential backoff
- Configurable retry attempts and delays
- Multiple webhook event handling
- Rate limit status monitoring
- Issue auto-closing with rate protection

## Setup

### 1. GitHub App Configuration

Create a GitHub App with these settings:
- **Homepage URL**: `http://localhost:8000`
- **Webhook URL**: `http://localhost:8000/webhooks/github`

Required permissions:
- **Issues**: Write (to close issues and add comments)
- **Pull requests**: Write (to comment on PRs)
- **Repository administration**: Write (for repository setup)
- **Metadata**: Read

Subscribe to events:
- **Issues**
- **Pull requests**
- **Repository**

### 2. Environment Setup

Copy and configure the environment file:

```bash
cp .env.example .env
```

Update `.env` with your GitHub App credentials:

```env
GITHUBAPP_ID=your-app-id
GITHUBAPP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUBAPP_WEBHOOK_SECRET=your-webhook-secret
```

### 3. Run the Application

Choose one of the two examples:

**Full-featured example with rate limiting and monitoring:**
```bash
poetry run python app.py
```

**Simple rate limiting example:**
```bash
poetry run python simple.py
```

Visit [http://localhost:8000](http://localhost:8000) to access the application.

## Examples

### 1. `app.py` - Comprehensive Rate Limiting

Advanced rate limiting demonstration with:
- Automatic rate limit handling for all API calls
- Multiple webhook events (issues, pull requests, repository)
- Rate limit status monitoring endpoint
- Manual rate limiting for complex operations
- Error handling and recovery

### 2. `simple.py` - Basic Rate Limiting

Minimal rate limiting setup showing:
- Basic rate limit configuration
- Automatic retry on rate limits
- Issue closing with protection

## Rate Limiting Features

### Automatic Rate Limiting

The `@with_rate_limit_handling` decorator automatically protects API calls:

```python
@github_app.on("issues.opened")
@with_rate_limit_handling(github_app)
def close_issue():
    client = github_app.client()
    # All client calls are automatically protected
    client.issues.create_comment(...)
    client.issues.update(...)
```

### Manual Rate Limiting

For complex operations, use manual rate limiting:

```python
def complex_operation():
    client = github_app.client()
    # Multiple API calls here
    
# Wrap the entire function with rate limiting
github_app.retry_with_rate_limit(complex_operation)
```

### Configuration

Rate limiting is configured during GitHubApp initialization:

```python
github_app = GitHubApp(
    app,
    rate_limit_retries=3,      # Retry up to 3 times
    rate_limit_max_sleep=120   # Wait up to 2 minutes between retries
)
```

## Usage

### Rate Limit Monitoring

Check current rate limit status:

```bash
curl http://localhost:8000/rate-limit-status
```

Response includes:
- Current rate limits for core and search APIs
- Remaining requests
- Reset times
- Configuration settings

### Testing Rate Limits

To test rate limiting behavior:

1. Create multiple issues quickly in a repository where the app is installed
2. Monitor the logs to see retry behavior
3. Check the rate limit status endpoint

### Webhook Events

The app handles multiple events with rate limiting:

- **Issues opened/reopened**: Automatically closes with comments
- **Pull requests opened**: Adds comments and labels
- **Repository created**: Sets up initial configuration

## Advanced Usage

### Custom Rate Limiting

You can customize rate limiting behavior:

```python
# Different retry settings for different operations
@with_rate_limit_handling(github_app, max_retries=5, max_sleep=300)
def critical_operation():
    # This operation will retry up to 5 times with longer delays
    pass
```

### Error Handling

Rate limiting includes comprehensive error handling:

```python
try:
    client.issues.create_comment(...)
except RateLimitExceeded:
    # Automatically handled by decorator
    pass
except Exception as e:
    # Other errors still need manual handling
    print(f"Unexpected error: {e}")
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page with feature overview |
| `/health` | GET | Health check |
| `/rate-limit-status` | GET | Current rate limit status |
| `/webhooks/github` | POST | GitHub webhooks |

## Benefits

Rate limiting protection provides:

- **Reliability**: Automatic recovery from rate limit errors
- **Efficiency**: Exponential backoff prevents aggressive retrying
- **Monitoring**: Built-in rate limit status tracking
- **Flexibility**: Both automatic and manual rate limiting options
- **Scalability**: Handles high-volume webhook events gracefully

## Production Considerations

For production deployments:

1. Monitor rate limit usage regularly
2. Adjust retry settings based on your app's needs
3. Implement logging for rate limit events
4. Consider caching strategies to reduce API calls
5. Use webhook filtering to reduce unnecessary events
