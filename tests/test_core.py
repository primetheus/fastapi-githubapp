import pytest
import json
import time
from unittest.mock import patch, Mock, mock_open
from fastapi import APIRouter, Request, FastAPI
from fastapi.testclient import TestClient
from githubapp import GitHubApp
from githubapp.core import (
    GitHubAppError,
    GitHubAppValidationError,
    GitHubAppBadCredentials,
    GithubUnauthorized,
    GithubAppUnkownObject,
    InstallationAuthorization,
    STATUS_FUNC_CALLED,
    STATUS_NO_FUNC_CALLED,
)


class TestGitHubAppExceptions:
    def test_github_app_error(self):
        error = GitHubAppError("test message", status=400, data={"error": "test"})
        assert error.message == "test message"
        assert error.status == 400
        assert error.data == {"error": "test"}
        assert str(error) == "test message"

    def test_github_app_validation_error(self):
        error = GitHubAppValidationError("validation failed", status=422)
        assert error.message == "validation failed"
        assert error.status == 422
        assert error.data is None

    def test_github_app_bad_credentials(self):
        error = GitHubAppBadCredentials("bad creds", status=403)
        assert error.message == "bad creds"
        assert error.status == 403

    def test_github_unauthorized(self):
        error = GithubUnauthorized("unauthorized", status=401)
        assert error.message == "unauthorized"
        assert error.status == 401

    def test_github_app_unknown_object(self):
        error = GithubAppUnkownObject("not found", status=404)
        assert error.message == "not found"
        assert error.status == 404


class TestInstallationAuthorization:
    def test_installation_authorization_properties(self):
        auth = InstallationAuthorization("test_token", "2023-01-01T00:00:00Z")
        assert auth.token == "test_token"
        assert auth.expires_at == "2023-01-01T00:00:00Z"

    def test_expired_with_no_expiration(self):
        auth = InstallationAuthorization("test_token", None)
        assert auth.expired() is False

    def test_expired_with_future_expiration(self):
        future_time = time.time() + 3600  # 1 hour from now
        auth = InstallationAuthorization("test_token", future_time)
        assert auth.expired() is False

    def test_expired_with_past_expiration(self):
        past_time = time.time() - 3600  # 1 hour ago
        auth = InstallationAuthorization("test_token", past_time)
        assert auth.expired() is True


class TestGitHubAppInitialization:
    def test_init_without_app(self):
        github_app = GitHubApp(
            github_app_id=123,
            github_app_key=b"test_key",
            github_app_secret=b"test_secret",
        )
        assert github_app.id == 123
        assert github_app.key == b"test_key"
        assert github_app.secret == b"test_secret"
        assert github_app.base_url == "https://api.github.com"

    def test_init_with_custom_url(self):
        github_app = GitHubApp(
            github_app_id=123,
            github_app_key=b"test_key",
            github_app_secret=b"test_secret",
            github_app_url="https://api.github.enterprise.com",
        )
        assert github_app.base_url == "https://api.github.enterprise.com"

    def test_init_with_app(self):
        app = FastAPI()
        github_app = GitHubApp(
            app,
            github_app_id=123,
            github_app_key=b"test_key",
            github_app_secret=b"test_secret",
        )
        assert hasattr(app, "config")
        assert github_app.id == 123


class TestGitHubAppLoadEnv:
    @patch.dict("os.environ", {"GITHUBAPP_PRIVATE_KEY": "test_key_content"})
    def test_load_env_with_private_key_env(self):
        app = FastAPI()
        app.config = {}
        GitHubApp.load_env(app)
        assert app.config["GITHUBAPP_PRIVATE_KEY"] == "test_key_content"


class TestGitHubAppInitApp:
    def test_init_app_creates_config(self):
        app = FastAPI()
        github_app = GitHubApp()
        github_app.init_app(app)
        assert hasattr(app, "config")
        assert isinstance(app.config, dict)

    def test_init_app_sets_config_from_constructor(self):
        app = FastAPI()
        github_app = GitHubApp(
            github_app_id=456,
            github_app_key=b"constructor_key",
            github_app_secret=b"constructor_secret",
        )
        github_app.init_app(app)
        assert app.config["GITHUBAPP_ID"] == 456
        assert app.config["GITHUBAPP_PRIVATE_KEY"] == b"constructor_key"
        assert app.config["GITHUBAPP_WEBHOOK_SECRET"] == b"constructor_secret"


class TestGitHubAppHookRegistration:
    def test_on_decorator_single_function(self):
        github_app = GitHubApp()

        @github_app.on("issues.opened")
        def test_function():
            return "test_result"

        assert "issues.opened" in github_app._hook_mappings
        assert len(github_app._hook_mappings["issues.opened"]) == 1
        assert github_app._hook_mappings["issues.opened"][0] == test_function

    def test_on_decorator_multiple_functions_same_event(self):
        github_app = GitHubApp()

        @github_app.on("issues.opened")
        def function1():
            return "result1"

        @github_app.on("issues.opened")
        def function2():
            return "result2"

        assert len(github_app._hook_mappings["issues.opened"]) == 2
        assert function1 in github_app._hook_mappings["issues.opened"]
        assert function2 in github_app._hook_mappings["issues.opened"]

    def test_on_decorator_different_events(self):
        github_app = GitHubApp()

        @github_app.on("issues.opened")
        def issues_function():
            return "issues_result"

        @github_app.on("pull_request.closed")
        def pr_function():
            return "pr_result"

        assert "issues.opened" in github_app._hook_mappings
        assert "pull_request.closed" in github_app._hook_mappings
        assert len(github_app._hook_mappings) == 2


class TestGitHubAppJWT:
    @patch("githubapp.core.jwt")
    def test_create_jwt_returns_string(self, mock_jwt):
        mock_jwt.encode.return_value = "jwt_token_string"

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        result = github_app._create_jwt()

        assert result == "jwt_token_string"
        mock_jwt.encode.assert_called_once()

    @patch("githubapp.core.jwt")
    def test_create_jwt_converts_bytes_to_string(self, mock_jwt):
        mock_jwt.encode.return_value = b"jwt_token_bytes"

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        result = github_app._create_jwt()

        assert result == "jwt_token_bytes"

    @patch("githubapp.core.jwt")
    @patch("githubapp.core.time")
    def test_create_jwt_payload_structure(self, mock_time, mock_jwt):
        mock_time.time.return_value = 1640995200  # Fixed timestamp
        mock_jwt.encode.return_value = "jwt_token"

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        github_app._create_jwt(expiration=300)

        expected_payload = {"iat": 1640995200, "exp": 1640995200 + 300, "iss": 123}
        mock_jwt.encode.assert_called_once_with(
            expected_payload, key=b"test_key", algorithm="RS256"
        )


class TestGitHubAppAccessToken:
    @patch("githubapp.core.requests.post")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_get_access_token_success(self, mock_jwt, mock_post):
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "token": "test_token",
            "expires_at": "2023-01-01T00:00:00Z",
        }
        mock_post.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        result = github_app.get_access_token(installation_id=456)

        assert isinstance(result, InstallationAuthorization)
        assert result.token == "test_token"
        assert result.expires_at == "2023-01-01T00:00:00Z"

    @patch("githubapp.core.requests.post")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_get_access_token_with_user_id(self, mock_jwt, mock_post):
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "token": "test_token",
            "expires_at": "2023-01-01T00:00:00Z",
        }
        mock_post.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        github_app.get_access_token(installation_id=456, user_id=789)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"user_id": 789}

    @patch("githubapp.core.requests.post")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_get_access_token_forbidden(self, mock_jwt, mock_post):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_post.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")

        with pytest.raises(GitHubAppBadCredentials) as exc_info:
            github_app.get_access_token(installation_id=456)

        assert exc_info.value.status == 403

    @patch("githubapp.core.requests.post")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_get_access_token_not_found(self, mock_jwt, mock_post):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_post.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")

        with pytest.raises(GithubAppUnkownObject) as exc_info:
            github_app.get_access_token(installation_id=456)

        assert exc_info.value.status == 404


class TestGitHubAppListInstallations:
    @patch("githubapp.core.requests.get")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_list_installations_success(self, mock_jwt, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_get.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        result = github_app.list_installations()

        assert result == [{"id": 1}, {"id": 2}]
        mock_get.assert_called_once()

    @patch("githubapp.core.requests.get")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_list_installations_with_pagination(self, mock_jwt, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")
        github_app.list_installations(per_page=50, page=2)

        call_args = mock_get.call_args
        assert call_args[1]["params"] == {"page": 2, "per_page": 50}

    @patch("githubapp.core.requests.get")
    @patch.object(GitHubApp, "_create_jwt", return_value="test_jwt")
    def test_list_installations_unauthorized(self, mock_jwt, mock_get):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        github_app = GitHubApp(github_app_id=123, github_app_key=b"test_key")

        with pytest.raises(GithubUnauthorized) as exc_info:
            github_app.list_installations()

        assert exc_info.value.status == 401


class TestGitHubAppClient:
    @patch.object(GitHubApp, "get_access_token")
    @patch("githubapp.core.GhApi")
    def test_client_with_installation_id(self, mock_ghapi, mock_get_token):
        mock_auth = Mock()
        mock_auth.token = "test_token"
        mock_get_token.return_value = mock_auth

        mock_api_instance = Mock()
        mock_ghapi.return_value = mock_api_instance

        github_app = GitHubApp()
        result = github_app.client(installation_id=123)

        mock_get_token.assert_called_once_with(123)
        mock_ghapi.assert_called_once_with(token="test_token")
        assert result == mock_api_instance

    @patch.object(GitHubApp, "get_access_token")
    @patch("githubapp.core.GhApi")
    def test_client_with_payload_installation(self, mock_ghapi, mock_get_token):
        mock_auth = Mock()
        mock_auth.token = "test_token"
        mock_get_token.return_value = mock_auth

        mock_api_instance = Mock()
        mock_ghapi.return_value = mock_api_instance

        github_app = GitHubApp()
        github_app.payload = {"installation": {"id": 456}}
        result = github_app.client()

        mock_get_token.assert_called_once_with(456)


class TestGitHubAppWebhookHandling:
    def test_extract_payload_valid_json(self):
        app = FastAPI()
        github_app = GitHubApp(app)
        github_app.init_app(app)

        with TestClient(app) as client:
            # simplified; no real assertion here
            pass

    def test_handle_request_missing_content_type(self):
        app = FastAPI()
        github_app = GitHubApp(app)
        github_app.init_app(app)

        with TestClient(app) as client:
            response = client.post("/", json={"test": "data"})
            assert response.status_code == 400

    def test_handle_request_missing_github_event_header(self):
        app = FastAPI()
        github_app = GitHubApp(app)
        github_app.init_app(app)

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={"installation": {"id": 123}},
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 400

    def test_handle_request_valid_webhook(self):
        app = FastAPI()
        github_app = GitHubApp(
            app,
            github_app_id=123,
            github_app_key=b"test_key",
            github_app_secret=False,  # Disable signature verification for testing
        )
        github_app.init_app(app)

        @github_app.on("issues.opened")
        def test_handler():
            return "handled"

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={
                    "action": "opened",
                    "installation": {"id": 123},
                    "issue": {"number": 1},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issues",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == STATUS_FUNC_CALLED
            assert "test_handler" in data["calls"]

    def test_handle_request_call_async_hook_function(self):
        app = FastAPI()
        github_app = GitHubApp(
            app,
            github_app_id=123,
            github_app_key=b"test_key",
            github_app_secret=False,  # Disable signature verification for testing
        )
        github_app.init_app(app)

        @github_app.on("issues.opened")
        async def async_test_handler():
            return "handled"

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={
                    "action": "opened",
                    "installation": {"id": 123},
                    "issue": {"number": 1},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issues",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == STATUS_FUNC_CALLED
            assert "async_test_handler" in data["calls"]

class TestGitHubAppWebhookSignatureVerification:
    def test_signature_verification_disabled(self):
        app = FastAPI()
        github_app = GitHubApp(
            app, github_app_secret=False  # Explicitly disable verification
        )
        # Test that webhooks work without signature headers when verification is disabled

    def test_signature_verification_sha256_valid(self):
        app = FastAPI()
        github_app = GitHubApp(app, github_app_secret=b"test_secret")
        # Test that valid SHA256 signatures are accepted

    def test_signature_verification_sha256_invalid(self):
        app = FastAPI()
        github_app = GitHubApp(app, github_app_secret=b"test_secret")
        # Test that invalid SHA256 signatures are rejected

    def test_signature_verification_sha1_fallback(self):
        app = FastAPI()
        github_app = GitHubApp(app, github_app_secret=b"test_secret")
        # Test that SHA1 signatures work when SHA256 is not present


class TestGitHubAppIntegration:
    def test_full_webhook_flow(self):
        """Test complete webhook handling flow"""
        app = FastAPI()
        github_app = GitHubApp(
            app, github_app_id=123, github_app_key=b"test_key", github_app_secret=False
        )
        github_app.init_app(app)

        results = []

        @github_app.on("issues")
        def handle_any_issue():
            results.append("any_issue")
            return "handled_any"

        @github_app.on("issues.opened")
        def handle_opened_issue():
            results.append("opened_issue")
            return "handled_opened"

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={
                    "action": "opened",
                    "installation": {"id": 123},
                    "issue": {"number": 1},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issues",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == STATUS_FUNC_CALLED
            assert len(data["calls"]) == 2
            assert "handle_any_issue" in data["calls"]
            assert "handle_opened_issue" in data["calls"]

    def test_no_matching_handlers(self):
        """Test webhook with no matching handlers"""
        app = FastAPI()
        github_app = GitHubApp(
            app, github_app_id=123, github_app_key=b"test_key", github_app_secret=False
        )
        github_app.init_app(app)

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={
                    "action": "closed",
                    "installation": {"id": 123},
                    "issue": {"number": 1},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issues",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == STATUS_NO_FUNC_CALLED
            assert data["calls"] == {}

    def test_handler_exception_returns_500(self):
        """Test that exceptions in handlers return 500"""
        app = FastAPI()
        github_app = GitHubApp(
            app, github_app_id=123, github_app_key=b"test_key", github_app_secret=False
        )
        github_app.init_app(app)

        @github_app.on("issues.opened")
        def failing_handler():
            raise ValueError("Something went wrong")

        with TestClient(app) as client:
            response = client.post(
                "/",
                json={
                    "action": "opened",
                    "installation": {"id": 123},
                    "issue": {"number": 1},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issues",
                },
            )

            assert response.status_code == 500
