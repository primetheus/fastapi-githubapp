"""
Simple rate limiting example.

Demonstrates basic rate limiting with environment-only configuration.
"""

from fastapi import FastAPI
from githubapp import GitHubApp, with_rate_limit_handling

app = FastAPI()

# Initialize config for environment variable loading
app.config = {}
GitHubApp.load_env(app)

# Create GitHubApp instance with rate limiting
github_app = GitHubApp(app, rate_limit_retries=3, rate_limit_max_sleep=60)


@app.get("/")
def home():
    """Status endpoint."""
    return {
        "app": "Rate Limiting Example",
        "status": "ready",
        "rate_limiting": "enabled",
    }


@github_app.on("issues.opened")
@with_rate_limit_handling(github_app)
def close_new_issue():
    """Close issues with automatic rate limiting."""
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    client = github_app.client()

    # These calls will automatically retry on rate limits
    client.issues.create_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body="You've got an issue? I've got a solution! Closing 😈",
    )

    client.issues.update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )


@github_app.on("issues.reopened")
@with_rate_limit_handling(github_app)
def close_reopened_issue():
    """Close reopened issues with rate limiting."""
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    client = github_app.client()

    client.issues.create_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body="Nice try! Closing again. 😈",
    )

    client.issues.update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
