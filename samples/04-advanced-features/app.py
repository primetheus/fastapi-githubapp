"""
Advanced GitHub App features demonstration.

Shows rate limiting, retry logic, and error handling with issue auto-closing.
"""

from fastapi import FastAPI
from githubapp import GitHubApp, with_rate_limit_handling

app = FastAPI()

# Initialize config for environment variable loading
app.config = {}
GitHubApp.load_env(app)

# Create GitHubApp instance with rate limiting configuration
github_app = GitHubApp(
    app,
    rate_limit_retries=3,  # Retry up to 3 times on rate limits
    rate_limit_max_sleep=120,  # Wait up to 2 minutes between retries
)


@app.get("/")
def home():
    """Status endpoint."""
    return {
        "app": "Advanced GitHub App Features",
        "github_app_id": app.config.get("GITHUBAPP_ID"),
        "features": [
            "Rate limiting protection",
            "Automatic retries",
            "Issue auto-closing",
            "Pull request handling",
        ],
        "status": "ready",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@github_app.on("issues.opened")
@with_rate_limit_handling(github_app)
def close_new_issue():
    """
    Automatically close newly opened issues with rate limit protection.

    The @with_rate_limit_handling decorator ensures all GitHub API calls
    will automatically handle rate limits with exponential backoff.
    """
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    issue_number = github_app.payload["issue"]["number"]

    # Get rate-limited client
    client = github_app.client()

    # These API calls will automatically retry on rate limits
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
    """Close reopened issues with rate limit protection."""
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


@github_app.on("pull_request.opened")
@with_rate_limit_handling(github_app)
def handle_pull_request():
    """
    Handle new pull requests with multiple API calls and rate limiting.

    Demonstrates rate limiting with multiple sequential API operations.
    """
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    pr_number = github_app.payload["pull_request"]["number"]
    pr_title = github_app.payload["pull_request"]["title"]

    client = github_app.client()

    # Multiple API calls that could hit rate limits
    client.issues.create_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,
        body=f"Thanks for the PR '{pr_title}'! All API calls are rate-limit protected.",
    )

    # Add labels (this could trigger rate limits with many PRs)
    try:
        client.issues.add_labels(
            owner=owner,
            repo=repo,
            issue_number=pr_number,
            labels=["needs-review", "auto-processed"],
        )
    except Exception:
        # Labels might not exist, that's ok
        pass


@github_app.on("repository.created")
def setup_new_repository():
    """
    Example of manual rate limiting for complex operations.

    Shows how to use manual rate limiting for custom logic.
    """
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]

    def setup_repo():
        """Setup function that will be wrapped with rate limiting."""
        client = github_app.client()

        # Create welcome issue
        client.issues.create(
            owner=owner,
            repo=repo,
            title="Welcome to your new repository!",
            body="This repository has been automatically configured with rate-limited operations.",
        )

        # Add initial labels
        labels_to_create = [
            {
                "name": "bug",
                "color": "d73a4a",
                "description": "Something isn't working",
            },
            {
                "name": "enhancement",
                "color": "a2eeef",
                "description": "New feature or request",
            },
            {
                "name": "needs-review",
                "color": "fbca04",
                "description": "Requires review",
            },
        ]

        for label in labels_to_create:
            try:
                client.issues.create_label(owner=owner, repo=repo, **label)
            except Exception:
                # Label might already exist
                pass

    # Use manual rate limiting for the entire setup process
    github_app.retry_with_rate_limit(setup_repo)


@app.get("/rate-limit-status")
def rate_limit_status():
    """
    Endpoint to check current rate limit status.

    Useful for monitoring and debugging rate limit issues.
    """
    try:
        client = github_app.client()

        # Make a lightweight API call to check rate limits
        rate_limit = client.rate_limit.get()

        return {
            "rate_limit": {
                "core": {
                    "limit": rate_limit.resources.core.limit,
                    "remaining": rate_limit.resources.core.remaining,
                    "reset": rate_limit.resources.core.reset,
                },
                "search": {
                    "limit": rate_limit.resources.search.limit,
                    "remaining": rate_limit.resources.search.remaining,
                    "reset": rate_limit.resources.search.reset,
                },
            },
            "configuration": {"retries": 3, "max_sleep": 120},
        }
    except Exception as e:
        return {"error": f"Could not fetch rate limit status: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
