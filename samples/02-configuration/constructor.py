"""
Configuration examples - Constructor Parameters (Alternative).

Demonstrates configuration using constructor parameters.
Less flexible than environment variables but useful in some scenarios.
"""

from fastapi import FastAPI
from githubapp import GitHubApp
import os


def _env_bytes(name: str):
    """Helper to convert environment variable to bytes if needed."""
    val = os.getenv(name)
    return val.encode() if isinstance(val, str) else val


app = FastAPI()

# Constructor Parameters approach
github_app = GitHubApp(
    app,
    github_app_id=int(os.getenv("GITHUBAPP_ID", "0")) or None,
    github_app_key=_env_bytes("GITHUBAPP_PRIVATE_KEY"),
    github_app_secret=_env_bytes("GITHUBAPP_WEBHOOK_SECRET"),
    github_app_route=os.getenv("GITHUBAPP_WEBHOOK_PATH", "/webhooks/github"),
)


@app.get("/")
def home():
    """Configuration status."""
    return {
        "app": "Configuration Examples - Constructor Parameters",
        "configuration_method": "constructor_parameters",
        "github_app_id": os.getenv("GITHUBAPP_ID"),
        "status": "ready",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@github_app.on("issues.opened")
def close_new_issue():
    """Automatically close newly opened issues."""
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    client = github_app.client()

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
def close_reopened_issue():
    """Close reopened issues."""
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
