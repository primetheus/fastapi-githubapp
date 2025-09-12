# FastAPI-GithubApp

FastAPI extension for rapid Github app development in Python, in the spirit of [probot](https://probot.github.io/)

GitHub Apps help automate GitHub workflows. Examples include preventing merging of pull requests with "WIP" in the title or closing stale issues and pull requests.

## Getting Started

### Create GitHub App

Follow GitHub's docs on [creating a github app](https://developer.github.com/apps/building-github-apps/creating-a-github-app/).

> You can, in principle, register any type of payload to be sent to the app!

Once you do this, please note down the GitHub app Id, the GitHub app secret, and make sure to [create a private key](https://docs.github.com/en/developers/apps/authenticating-with-github-apps#generating-a-private-key) for it! These three elements are **required** to run your app.

#### Build the FastAPI App

The GithubApp package has a decorator, `@on`, that will allow you to register events, and actions, to specific functions.
For instance,

```python
@github_app.on('issues.opened')
def cruel_closer():
    #do stuff here
```

Will trigger whenever the app receives a Github payload with the `X-Github-Event` header set to `issues`, and an `action` field in the payload field containing `opened`

Following this logic, you can make your app react in a unique way for every combination of event and action. Refer to the Github documentation for all the details about events and the actions they support, as well as for sample payloads for each.
You can also have something like

```python
@github_app.on('issues')
def issue_tracker():
    #do stuff here
```

The above function will do `stuff here` for _every_ `issues` event received. This can be useful for specific workflows, to bring developers in early.

Inside the function, you can access the received request via the conveniently named `request` variable. You can access its payload by simply getting it: `request.payload`

You can find a complete example (containing this cruel_closer function), in the samples folder of this repo. It is a fully functioning FastAPI Github App.

#### Run it locally

For quick iteration, you can set up your environment as follows:

```bash
EXPORT GITHUBAPP_WEBHOOK_SECRET=False # this will circumvent request verification
```

This will make your FastAPI application run in debug mode. This means that, as you try sending payloads and tweak functions, fix issues, etc., as soon as you save the python code, the FastAPI application will reload itself and run the new code immediately.
Once that is in place, run your github app

```bash
uvicorn app:app --host 0.0.0.0 --port 5005 --reload --workers 1
```

Now, you can send requests! The port is 5005 by default but that can also be overridden. Check `uvicorn app:app --help` for more details. Anyway! Now, on to sending test payloads!

```bash
curl -H "X-GitHub-Event: <your_event>" -H "Content-Type: application/json" -X POST -d @./path/to/payload.json http://localhost:5005
```

#### Install your GitHub App

**Settings** > **Applications** > **Configure**

> If you were to install the cruel closer app, any repositories that you give the GitHub app access to will cruelly close all new issues, be careful.

#### Deploy your GitHub App

Bear in mind that you will need to run the app _somewhere_. It is possible, and fairly easy, to host the app in something like Kubernetes, or simply containerised, in a machine somewhere. You will need to be careful to expose the FastAPI app port to the outside world so the app can receive the payloads from Github. The deployed FastAPI app will need to be reachable from the same URL you set as the `webhook url`. However, this is getting a little bit into Docker/Kubernetes territory so we will not go too deep.

## Usage

### `GitHubApp` Instance Attributes

`payload`: In the context of a hook request, a Python dict representing the hook payload (raises a `RuntimeError`
outside a hook context).

`installation_token`: The token used to authenticate as the app installation. This can be used to call api's not supported by `GhApi` like [Github's GraphQL API](https://docs.github.com/en/graphql/reference)

### `GithubApp` Instance Methods

`client`: a [GhApi](https://ghapi.fast.ai/) client authenticated as the app installation (raises a `RuntimeError` inside a hook context without a valid request)

## Rate Limiting

FastAPI-GitHubApp provides automatic rate limiting functionality to handle GitHub's API rate limits gracefully. GitHub enforces rate limits on API requests, and exceeding these limits results in HTTP 429 or 403 responses.

### Automatic Rate Limiting

Use the `@with_rate_limit_handling` decorator to automatically handle rate limits for all GitHub API calls in your webhook handlers:

```python
from githubapp import GitHubApp, with_rate_limit_handling

github_app = GitHubApp(
    app,
    github_app_id=12345,
    github_app_key=private_key,
    github_app_secret=webhook_secret,
    rate_limit_retries=3,        # Retry up to 3 times (default: 2)
    rate_limit_max_sleep=120,    # Max wait time in seconds (default: 60)
)

@github_app.on("issues.opened")
@with_rate_limit_handling(github_app)
def handle_issue():
    client = github_app.get_client()
    
    # All these calls automatically handle rate limits
    client.issues.create_comment(owner="user", repo="repo", issue_number=1, body="Hello!")
    client.issues.update(owner="user", repo="repo", issue_number=1, state="closed")
```

### Manual Rate Limiting

For selective control, use the `retry_with_rate_limit` method:

```python
@github_app.on("repository.created")
def setup_repository():
    client = github_app.client()
    
    def create_initial_setup():
        client.issues.create(title="Welcome!", body="Thanks for creating this repo!")
        # More API calls...
    
    # Wrap specific functions with rate limiting
    github_app.retry_with_rate_limit(create_initial_setup)
```

### How It Works

The rate limiting implementation:

- Detects rate limit errors (HTTP 429 or 403 with `x-ratelimit-remaining: 0`)
- Respects GitHub's `Retry-After` headers when present
- Uses exponential backoff for secondary rate limits
- Follows GitHub's official rate limiting guidance
- Applies to both user API calls and internal operations (token refresh, installation listing)

### Configuration Options

Configure rate limiting behavior in the GitHubApp constructor:

- `rate_limit_retries`: Number of retry attempts after initial failure (default: 2)
- `rate_limit_max_sleep`: Maximum wait time between retries in seconds (default: 60)

Set `rate_limit_retries=0` to disable automatic retries.

## OAuth2 Integration

FastAPI-GitHubApp includes built-in OAuth2 support for user authentication and authorization. This allows your GitHub App to authenticate users and access repositories on their behalf.

### Setup

OAuth2 is enabled when you provide both `oauth_client_id` and `oauth_client_secret`. The `oauth_session_secret` is **required** for session management:

```python
from githubapp import GitHubApp

github_app = GitHubApp(
    app,
    github_app_id=12345,
    github_app_key=private_key,
    github_app_secret=webhook_secret,
    # OAuth2 configuration - all required for OAuth2 to work
    oauth_client_id="your_oauth_client_id",
    oauth_client_secret="your_oauth_client_secret", 
    oauth_session_secret="your-secret-key-for-jwt",  # Required!
    # Optional OAuth2 settings
    oauth_redirect_uri="http://localhost:8000/auth/github/callback",
    oauth_scopes=["user:email", "repo"],
    oauth_routes_prefix="/auth/github",  # Default: "/auth/github"
    enable_oauth=True,  # Default: True when client_id/secret provided
)
```

### OAuth2 Routes

When OAuth2 is configured, these routes are automatically mounted:

- `GET /auth/github/login` - Returns auth URL for GitHub OAuth flow
- `GET /auth/github/callback` - Handles OAuth callback and returns session token
- `POST /auth/github/logout` - Logout endpoint (stateless JWT)
- `GET /auth/github/user` - Get current authenticated user info

### Usage Examples

#### Login Flow

```python
# 1. Get authorization URL
# GET /auth/github/login?scopes=user:email,repo
# Returns: {"auth_url": "https://github.com/login/oauth/authorize?..."}

# 2. User authorizes and GitHub redirects to callback
# GET /auth/github/callback?code=abc123&state=xyz
# Returns: {"user": {...}, "session_token": "jwt_token"}
```

#### Protected Routes

```python
from fastapi import Depends

@app.get("/protected")
async def protected_route(current_user=Depends(github_app.get_current_user)):
    return {"user": current_user["login"], "message": "Access granted"}
```

#### Authentication Methods

The `get_current_user` dependency supports:

```python
# Bearer token in Authorization header
headers = {"Authorization": "Bearer jwt_token"}

# Session token in cookies  
cookies = {"session_token": "jwt_token"}
```

### Session Tokens

OAuth2 sessions use JWT tokens containing:

```python
{
    "sub": "12345",           # User ID
    "login": "username",      # GitHub username
    "iat": 1672531200,        # Issued at timestamp
    "exp": 1672617600,        # Expires at timestamp (default: 24h)
    "type": "session"         # Token type
}
```

### User Information

The authenticated user object includes:

```python
{
    "id": 12345,
    "login": "username", 
    "name": "User Name",
    "email": "user@example.com",
    "avatar_url": "https://avatars.githubusercontent.com/...",
    "emails": [...]          # Array of email objects if user:email scope
}
```

### Complete Example

```python
from fastapi import FastAPI, Depends
from githubapp import GitHubApp

app = FastAPI()

github_app = GitHubApp(
    app,
    github_app_id=12345,
    github_app_key=private_key,
    github_app_secret=webhook_secret,
    oauth_client_id="your_oauth_client_id",
    oauth_client_secret="your_oauth_client_secret",
    oauth_session_secret="your-jwt-secret",
    oauth_scopes=["user:email", "repo"],
)

@app.get("/")
async def home():
    return {"message": "Visit /auth/github/login to authenticate"}

@app.get("/dashboard") 
async def dashboard(current_user=Depends(github_app.get_current_user)):
    return {"user": current_user["login"], "id": current_user["sub"]}

# Webhook handlers work as usual
@github_app.on("push")
def handle_push():
    pass
```

### Important Notes

- OAuth2 routes are **only mounted** when `oauth_client_id`, `oauth_client_secret`, AND `oauth_session_secret` are all provided
- Session tokens are stateless JWTs - no server-side session storage
- Default token expiration is 24 hours
- The OAuth2 client uses async httpx and is automatically cleaned up

### Environment Variables

OAuth2 can be configured using environment variables instead of constructor parameters. Use `GitHubApp.load_env(app)` to load them:

```python
from fastapi import FastAPI
from githubapp import GitHubApp

app = FastAPI()
app.config = {}  # Required for environment variable loading

# Load environment variables into app.config
GitHubApp.load_env(app)

# Create GitHubApp - will use environment variables if constructor params not provided
github_app = GitHubApp(app)
```

Environment variables use the `GITHUBAPP_OAUTH_` prefix (see Configuration table below).

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITHUBAPP_ID` | :white_check_mark: | `None` | GitHub App ID as an integer |
| `GITHUBAPP_PRIVATE_KEY` | :white_check_mark: | `None` | Private key used to sign access token requests as bytes or utf-8 encoded string |
| `GITHUBAPP_WEBHOOK_SECRET` | :white_check_mark: | `False` | Secret used to secure webhooks as bytes or utf-8 encoded string. Set to `False` to disable verification. |
| `GITHUBAPP_WEBHOOK_PATH` | | `/webhooks/github/` | Path used for GitHub hook requests as a string. |
| `GITHUBAPP_URL` | | `None` | URL of GitHub instance (used for GitHub Enterprise Server) as a string |
| `GITHUBAPP_OAUTH_CLIENT_ID` | | `None` | OAuth2 client ID for user authentication |
| `GITHUBAPP_OAUTH_CLIENT_SECRET` | | `None` | OAuth2 client secret for user authentication |
| `GITHUBAPP_OAUTH_SESSION_SECRET` | | `None` | Secret key for JWT session token signing |
| `GITHUBAPP_OAUTH_REDIRECT_URI` | | `None` | OAuth2 redirect URI for callback handling |
| `GITHUBAPP_OAUTH_SCOPES` | | `user:email,read:user` | Comma-separated OAuth2 scopes |
| `GITHUBAPP_ENABLE_OAUTH` | | `True` | Enable/disable OAuth2 routes when fully configured |
| `GITHUBAPP_OAUTH_ROUTES_PREFIX` | | `/auth/github` | OAuth2 routes prefix |

You can find an example on how to init all these config variables in the [cruel_closer sample app](./samples/cruel_closer)

#### OAuth2 Example

The [oauth2_example](./samples/oauth2_example) demonstrates GitHub OAuth2 authentication with web interface, protected routes, and session management. It shows two approaches:

- **Environment-only configuration** (recommended): Load all settings from environment variables
- **Constructor parameters**: Pass OAuth2 settings explicitly to GitHubApp

#### Cruel Closer

The cruel-closer sample app will use information of the received payload (which is received every time an issue is opened), will find said issue and **close it** without regard.

### Inspiration
This was inspired by the following projects:
- https://github.com/ffalor/flask-githubapplication
- https://github.com/bradshjg/flask-githubapp
- https://github.com/probot/probot
