import json
from urllib.parse import urlparse, parse_qs

import pytest
import respx
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from githubapp import GitHubApp


@pytest.fixture
def app_with_oauth():
    app = FastAPI()
    gh = GitHubApp(
        app,
        oauth_client_id="client-id",
        oauth_client_secret="client-secret",
        oauth_redirect_uri="http://localhost/callback",
        oauth_session_secret="test-session-secret",
    )
    # Return both for potential future assertions
    return app, gh


def test_oauth_login_returns_auth_url(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        resp = client.get("/auth/github/login")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    # Validate core params present
    url = data["auth_url"]
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs.get("client_id") == ["client-id"]
    assert "state" in qs and len(qs["state"][0]) > 0


@respx.mock
def test_oauth_callback_and_user(app_with_oauth):
    app, gh = app_with_oauth
    with TestClient(app) as client:
        # 1) Get state from login
        login = client.get("/auth/github/login")
        state = parse_qs(urlparse(login.json()["auth_url"]).query)["state"][0]

        # 2) Mock GitHub endpoints used by OAuth
        token_route = respx.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "token123",
                "token_type": "bearer",
                "scope": "user:email read:user",
            })
        )
        user_route = respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={
                "id": 42,
                "login": "octocat",
                "name": "The Octocat",
                "email": "octo@example.com",
                "avatar_url": "https://avatars.githubusercontent.com/u/42",
            })
        )
        emails_route = respx.get("https://api.github.com/user/emails").mock(
            return_value=httpx.Response(200, json=[{"email": "octo@example.com", "primary": True}])
        )

        # 3) Do callback
        cb = client.get("/auth/github/callback", params={"code": "abc", "state": state})
        assert cb.status_code == 200
        body = cb.json()
        assert body["user"]["login"] == "octocat"
        assert "session_token" in body

        # Ensure mocks were hit
        assert token_route.called
        assert user_route.called
        assert emails_route.called

        # 4) Use the session token to call /user
        token = body["session_token"]
        me = client.get("/auth/github/user", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        claims = me.json()
        assert claims["login"] == "octocat"
