# Configuration Examples

Demonstrates two different configuration approaches for FastAPI-GitHubApp with separate, clean examples.

## Configuration Methods

### Method 1: Environment Variables (Recommended) - `app.py`

The recommended approach using only environment variables:

```python
app.config = {}
GitHubApp.load_env(app)
github_app = GitHubApp(app)
```

**Advantages:**
- Clean, simple code
- No hardcoded values
- Easy to configure for different environments
- Follows 12-factor app principles

### Method 2: Constructor Parameters - `constructor.py`

Alternative approach using constructor parameters:

```python
github_app = GitHubApp(
    app,
    github_app_id=int(os.getenv("GITHUBAPP_ID")),
    github_app_key=os.getenv("GITHUBAPP_PRIVATE_KEY"),
    github_app_secret=os.getenv("GITHUBAPP_WEBHOOK_SECRET"),
    github_app_route=os.getenv("GITHUBAPP_WEBHOOK_PATH"),
)
```

**When to use:**
- Need explicit control over configuration
- Dynamic configuration scenarios
- Legacy code integration

## What Both Examples Do

Both examples implement identical functionality:
- **Issues opened**: Automatically close with "You've got an issue? I've got a solution! Closing 😈"
- **Issues reopened**: Close again with "Nice try! Closing again. 😈"

This demonstrates that both configuration methods work identically.

## Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Configure your GitHub App credentials in `.env`

3. Run either example:
   ```bash
   # Environment variables (recommended)
   python app.py
   
   # Constructor parameters  
   python constructor.py
   ```

## Testing

1. Install the GitHub App on a test repository
2. Create a new issue → App closes it automatically  
3. Reopen the issue → App closes it again

Both examples provide identical functionality, demonstrating that the configuration method doesn't affect the app's behavior.

## Files

- `app.py` - Environment variables approach (recommended)
- `constructor.py` - Constructor parameters approach
- `.env.example` - Environment variables template
- `README.md` - This documentation

## Recommendation

Use the environment variables approach (`app.py`) for production applications as it provides better security, flexibility, and follows best practices.
