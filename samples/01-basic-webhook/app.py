"""
Basic GitHub App webhook example.

Demonstrates simple webhook event handling for issues.opened and issues.reopened.
"""

from fastapi import FastAPI
from githubapp import GitHubApp

app = FastAPI()

# Initialize config for environment variable loading
app.config = {}
GitHubApp.load_env(app)

# Create GitHubApp instance
github_app = GitHubApp(app)


@app.get("/")
def home():
    """Status endpoint."""
    return {
        "app": "Basic GitHub App",
        "github_app_id": app.config.get("GITHUBAPP_ID"),
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

    # Add comment and close issue
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

    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
