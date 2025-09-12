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
    return app, gh


def test_callback_missing_code_returns_400(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        resp = client.get("/auth/github/callback")
        assert resp.status_code == 400
        assert "Missing authorization code" in resp.text


def test_callback_invalid_state_returns_500(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        # No prior login; pass a bogus state
        resp = client.get("/auth/github/callback", params={"code": "abc", "state": "bogus"})
        # Current implementation raises, resulting in 500
        assert resp.status_code == 500


@respx.mock
def test_callback_token_exchange_http_error_returns_500(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        # First get a valid state via /login
        login = client.get("/auth/github/login")
        state = parse_qs(urlparse(login.json()["auth_url"]).query)["state"][0]

        # Mock GitHub token endpoint to return 400
        respx.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(400, json={"error": "bad_verification_code"})
        )

        resp = client.get("/auth/github/callback", params={"code": "abc", "state": state})
        assert resp.status_code == 500


@respx.mock
def test_callback_token_exchange_json_error_returns_500(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        login = client.get("/auth/github/login")
        state = parse_qs(urlparse(login.json()["auth_url"]).query)["state"][0]

        # Mock GitHub token endpoint to return 200 with error field
        respx.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={
                "error": "incorrect_client_credentials",
                "error_description": "Client authentication failed",
            })
        )

        resp = client.get("/auth/github/callback", params={"code": "abc", "state": state})
        assert resp.status_code == 500


def test_user_missing_token_returns_401(app_with_oauth):
    app, _ = app_with_oauth
    with TestClient(app) as client:
        resp = client.get("/auth/github/user")
        assert resp.status_code == 401
        assert "Missing session token" in resp.text
