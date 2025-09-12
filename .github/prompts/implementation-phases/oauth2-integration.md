# GitHub OAuth2 Integration: Design & Architecture

## Overview

Adding GitHub OAuth2 support to your FastAPI-GitHubApp library enables upstream projects to authenticate users via GitHub, creating a complete ecosystem that combines:

1. **GitHub App Webhooks** (existing) - Server-to-server automation
2. **GitHub OAuth2** (new) - User authentication and authorization
3. **Task Queues** (phases 1-4) - Async processing capabilities

## Architecture Integration

```mermaid
graph TB
    subgraph "FastAPI-GitHubApp Library"
        subgraph "Webhook System"
            WH[Webhook Handler]
            TA[Task Queue/Async]
        end
        
        subgraph "OAuth2 System"
            OA[OAuth2 Manager]
            SM[Session Manager]
            UA[User Auth]
        end
        
        subgraph "GitHub Integration"
            GHA[GitHub App API]
            GHO[GitHub OAuth API]
            GHAPI[ghapi client]
        end
    end
    
    subgraph "Upstream Project"
        UP[User's FastAPI App]
        DB[Database]
        UI[Frontend/UI]
    end
    
    UP --> WH
    UP --> OA
    UI --> OA
    WH --> TA
    OA --> SM
    SM --> UA
    WH --> GHA
    OA --> GHO
    GHA --> GHAPI
    GHO --> GHAPI
    UA --> DB
```

## Use Cases Enabled

### 1. **Pure GitHub App** (Current)
```python
# Webhook-only automation (existing functionality)
@github_app.on("issues.opened")
def close_issue():
    # Automated response to GitHub events
    pass
```

### 2. **OAuth2-Only Authentication**
```python
# User authentication for web applications
@app.get("/dashboard")
async def dashboard(user=Depends(github_app.get_current_user)):
    return {"user": user}
```

### 3. **Combined Webhook + OAuth2** (Powerful)
```python
# Webhook processing with user context
@github_app.on("pull_request.opened")
async def handle_pr():
    pr_author = github_app.payload["pull_request"]["user"]["login"]
    
    # Check if PR author is authenticated in your app
    user_session = await get_user_by_github_login(pr_author)
    
    if user_session:
        # Enhanced processing for authenticated users
        await notify_user(user_session, "Your PR is being reviewed!")
        await assign_reviewer_based_on_user_preferences(user_session)
    else:
        # Standard processing for external contributors
        await standard_pr_review_process()
```

## Real-World Example: Development Team Dashboard

```python
from fastapi import FastAPI, Depends
from githubapp import GitHubApp

app = FastAPI()

# Configure with both GitHub App and OAuth2
github_app = GitHubApp(
    app,
    # GitHub App for webhooks and automation
    github_app_id=os.getenv("GITHUB_APP_ID"),
    github_app_key=private_key.encode(),
    github_app_secret=webhook_secret.encode(),
    
    # OAuth2 for user authentication
    oauth_client_id=os.getenv("GITHUB_OAUTH_CLIENT_ID"),
    oauth_client_secret=os.getenv("GITHUB_OAUTH_CLIENT_SECRET"),
    oauth_redirect_uri="https://myapp.com/auth/github/callback",
    oauth_scopes=["user:email", "repo"]
)

# 1. User Management
@github_app.on_user_login
async def store_user(login_data):
    """Store user in database when they log in"""
    user = login_data["user"]
    await db.upsert_user({
        "github_id": user["id"],
        "login": user["login"],
        "name": user["name"],
        "email": user["email"],
        "avatar_url": user["avatar_url"]
    })

# 2. Protected Dashboard
@app.get("/dashboard")
async def dashboard(user=Depends(github_app.get_current_user)):
    """User dashboard showing their GitHub activity"""
    
    # Use user's OAuth token to fetch their data
    user_client = github_app.oauth_client(user["access_token"])
    
    # Get user's repositories, issues, PRs, etc.
    repos = user_client.repos.list_for_authenticated_user()
    issues = user_client.issues.list_for_authenticated_user()
    
    return {
        "user": user,
        "repositories": repos[:10],  # Latest 10 repos
        "issues": issues[:5],        # Latest 5 issues
        "stats": await get_user_stats(user["github_id"])
    }

# 3. Webhook Processing with User Context
@github_app.on("issues.opened", background=True)
async def handle_new_issue():
    """Enhanced issue processing with user awareness"""
    payload = github_app.payload
    issue = payload["issue"]
    repository = payload["repository"]
    
    # Check if issue author is a registered user
    author = await db.get_user_by_github_login(issue["user"]["login"])
    
    if author:
        # Enhanced processing for registered users
        await notify_user_via_app(author, f"Your issue #{issue['number']} was created")
        await track_user_activity(author, "issue_created", issue)
        
        # Use user's preferences for auto-assignment
        if author.auto_assign_enabled:
            await auto_assign_issue_based_on_user_prefs(issue, author)
    
    # Standard GitHub App processing
    await analyze_issue_with_ai(issue)
    await update_project_metrics(repository, issue)

# 4. Team Collaboration Features
@app.get("/team/{team_id}/activity")
async def team_activity(
    team_id: int,
    user=Depends(github_app.get_current_user)
):
    """Show team activity across repositories"""
    
    # Verify user has access to team
    team = await db.get_team(team_id)
    if not await user_can_access_team(user, team):
        raise HTTPException(status_code=403)
    
    # Get team's GitHub activity
    team_repos = await db.get_team_repositories(team_id)
    activity = []
    
    for repo in team_repos:
        # Use GitHub App client for installation-level access
        app_client = github_app.client(repo.installation_id)
        
        # Get recent events for this repo
        events = app_client.activity.list_repo_events(
            owner=repo.owner,
            repo=repo.name
        )
        activity.extend(events[:10])
    
    return {
        "team": team,
        "activity": sorted(activity, key=lambda x: x["created_at"], reverse=True)
    }

# 5. Webhook-Driven Notifications
@github_app.on("pull_request.review_requested")
async def notify_reviewer():
    """Notify users when they're requested to review a PR"""
    payload = github_app.payload
    pr = payload["pull_request"]
    requested_reviewer = payload["requested_reviewer"]
    
    # Find user in our system
    reviewer = await db.get_user_by_github_login(requested_reviewer["login"])
    
    if reviewer and reviewer.notifications_enabled:
        await send_notification(
            reviewer,
            f"You were requested to review PR #{pr['number']}: {pr['title']}",
            action_url=pr["html_url"]
        )
```

## Benefits for Upstream Projects

### 🎯 **Complete GitHub Integration**
- **Webhooks**: Automated responses to GitHub events
- **OAuth2**: User authentication and personalization
- **API Access**: Both app-level and user-level GitHub API access

### 🔐 **Unified Authentication**
- Single library handles both GitHub App and OAuth2 flows
- Consistent configuration and setup
- Built-in security best practices

### 🚀 **Enhanced User Experience**
- Personalized dashboards based on user's GitHub data
- Context-aware webhook processing
- User preferences and settings integration

### 📊 **Rich Analytics & Insights**
```python
# Example: User analytics with GitHub data
@app.get("/analytics")
async def user_analytics(user=Depends(github_app.get_current_user)):
    user_client = github_app.oauth_client(user["access_token"])
    
    # Combine user's GitHub data with app data
    github_stats = await get_github_user_stats(user_client)
    app_activity = await db.get_user_activity(user["github_id"])
    
    return {
        "github_contributions": github_stats["contributions"],
        "repositories_count": github_stats["repos"],
        "app_interactions": len(app_activity),
        "favorite_languages": github_stats["languages"]
    }
```

## Configuration Options

### Minimal Setup (OAuth2 Only)
```python
github_app = GitHubApp(
    app,
    oauth_client_id="your_oauth_client_id",
    oauth_client_secret="your_oauth_secret"
)
# Only OAuth2 routes are enabled
```

### Complete Setup (GitHub App + OAuth2)
```python
github_app = GitHubApp(
    app,
    # GitHub App (webhooks & automation)
    github_app_id=12345,
    github_app_key=private_key,
    github_app_secret=webhook_secret,
    
    # OAuth2 (user authentication)
    oauth_client_id="oauth_client_id",
    oauth_client_secret="oauth_secret",
    oauth_scopes=["user:email", "repo", "read:org"]
)
# Both webhook and OAuth2 functionality enabled
```

### Environment Variables
```bash
# GitHub App Configuration
GITHUBAPP_ID=12345
GITHUBAPP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
GITHUBAPP_WEBHOOK_SECRET="webhook_secret"

# OAuth2 Configuration
GITHUBAPP_OAUTH_CLIENT_ID="oauth_client_id"
GITHUBAPP_OAUTH_CLIENT_SECRET="oauth_client_secret"
GITHUBAPP_OAUTH_REDIRECT_URI="https://myapp.com/auth/github/callback"
GITHUBAPP_OAUTH_SCOPES="user:email,repo"
GITHUBAPP_OAUTH_SESSION_SECRET="session_secret_key"
```

## Compatibility & Safety

### ✅ **Backward Compatibility**
- Existing webhook-only setups continue working unchanged
- OAuth2 is completely optional - enabled only when credentials provided
- No breaking changes to existing API

### 🔒 **Security Isolation**
- OAuth2 uses separate credentials from GitHub App
- Different scopes and permissions for different use cases
- Session management isolated from webhook processing

### 🛡️ **No Conflicts with Existing Auth**
- OAuth2 implementation is self-contained
- Uses `GITHUBAPP_` prefixed configuration
- Can coexist with other authentication systems in upstream projects

## Migration Path

### For Existing Users
1. **No Changes Required**: Existing code continues working
2. **Optional OAuth2**: Add OAuth2 credentials to enable user auth
3. **Gradual Enhancement**: Add user features incrementally

### For New Users
1. **Start Simple**: Begin with OAuth2-only for user authentication
2. **Add Webhooks**: Add GitHub App credentials for automation
3. **Combine Features**: Leverage both systems for advanced workflows

This OAuth2 integration makes your library a complete GitHub integration solution, enabling upstream projects to build sophisticated applications that combine automated workflows with personalized user experiences.
