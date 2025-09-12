"""
OAuth2 GitHub App integration example.

Demonstrates issue auto-closing with OAuth2 user authentication capabilities.
Shows how to add user login/logout and protected endpoints to a GitHub App.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from githubapp import GitHubApp

app = FastAPI()

# Initialize config for environment variable loading
app.config = {}
GitHubApp.load_env(app)

# Create GitHubApp instance with OAuth2 support
github_app = GitHubApp(app)


@app.get("/", response_class=HTMLResponse)
def home():
    """Home page with OAuth2 login option."""
    oauth_configured = github_app.oauth is not None

    if oauth_configured:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>OAuth2 GitHub App</title></head>
        <body>
            <h1>OAuth2 GitHub App Example</h1>
            <p>This app automatically closes issues and supports user authentication.</p>
            <ul>
                <li><a href="/auth/github/login">Login with GitHub</a></li>
                <li><a href="/profile">View Profile</a> (requires login)</li>
                <li><a href="/health">Health Check</a></li>
            </ul>
            <h3>Test the App</h3>
            <p>Create an issue in a repository where this app is installed to see it get automatically closed.</p>
        </body>
        </html>
        """
    else:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>OAuth2 GitHub App</title></head>
        <body>
            <h1>OAuth2 GitHub App Example</h1>
            <p><strong>OAuth2 not configured.</strong> Set the required environment variables:</p>
            <ul>
                <li>GITHUBAPP_OAUTH_CLIENT_ID</li>
                <li>GITHUBAPP_OAUTH_CLIENT_SECRET</li>
                <li>GITHUBAPP_OAUTH_SESSION_SECRET</li>
            </ul>
            <p>The app will still close issues automatically.</p>
        </body>
        </html>
        """


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "oauth_configured": github_app.oauth is not None,
        "github_app_id": app.config.get("GITHUBAPP_ID"),
    }


@app.get("/profile")
def profile(current_user=Depends(github_app.get_current_user)):
    """Protected profile endpoint requiring GitHub authentication."""
    return {
        "user": current_user.get("login"),
        "user_id": current_user.get("sub"),
        "name": current_user.get("name"),
        "email": current_user.get("email"),
        "avatar_url": current_user.get("avatar_url"),
    }


@github_app.on("issues.opened")
def close_new_issue():
    """Automatically close newly opened issues with OAuth2-aware comment."""
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    client = github_app.client()

    # Get current authenticated user if available
    try:
        # This would require the user's token, for demo we'll use a generic message
        comment = (
            f"You've got an issue? I've got a solution! Closing 😈 (OAuth2-enabled)"
        )
    except:
        comment = "You've got an issue? I've got a solution! Closing 😈"

    client.issues.create_comment(
        owner=owner, repo=repo, issue_number=issue_number, body=comment
    )

    client.issues.update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )


@github_app.on("issues.reopened")
def close_reopened_issue():
    """Close reopened issues with OAuth2-aware comment."""
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    client = github_app.client()

    # OAuth2-aware comment
    comment = "Nice try! Closing again. 😈 (OAuth2-enabled)"

    client.issues.create_comment(
        owner=owner, repo=repo, issue_number=issue_number, body=comment
    )

    client.issues.update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
