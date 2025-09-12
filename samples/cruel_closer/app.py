import os
from fastapi import FastAPI
from githubapp import GitHubApp

app = FastAPI()

# Build the GitHubApp object; constructor will auto-wire routes idempotently
def _env_bytes(name: str):
    val = os.getenv(name)
    return val.encode() if isinstance(val, str) else val

github_app = GitHubApp(
    app,
    github_app_id=int(os.getenv("GITHUBAPP_ID", "0")) or None,
    github_app_key=_env_bytes("GITHUBAPP_PRIVATE_KEY"),
    github_app_secret=_env_bytes("GITHUBAPP_WEBHOOK_SECRET"),
    github_app_route=os.getenv("GITHUBAPP_WEBHOOK_PATH", "/"),
)


@app.get("/health")
def index():
    return "Ok"


@github_app.on("issues.opened")
def cruel_closer():
    owner = github_app.payload["repository"]["owner"]["login"]
    repo = github_app.payload["repository"]["name"]
    num = github_app.payload["issue"]["number"]
    client = github_app.client()
    client.issues.create_comment(
        owner=owner, repo=repo, issue_number=num, body="Could not replicate."
    )
    client.issues.update(owner=owner, repo=repo, issue_number=num, state="closed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5005, reload=True)
