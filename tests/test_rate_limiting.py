import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from githubapp import GitHubApp, with_rate_limit_handling


class TestRateLimitHandling:
    """Test suite for rate limit handling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = GitHubApp(
            github_app_id=12345,
            github_app_key=b"fake-key-for-testing",
            github_app_secret=b"fake-secret",
            rate_limit_retries=2,
            rate_limit_max_sleep=5,
        )
        self.app.payload = {"installation": {"id": 123}}

    def test_decorator_wraps_client_calls(self):
        """Test that the decorator properly wraps GhApi client calls."""
        mock_ghapi = Mock()
        mock_ghapi.issues = Mock()
        mock_ghapi.issues.create_comment = Mock(return_value={"id": 456})

        with patch("githubapp.core.GhApi", return_value=mock_ghapi):
            with patch.object(self.app, "get_access_token") as mock_token:
                mock_token.return_value.token = "fake-token"

                @self.app.on("issues.opened")
                @with_rate_limit_handling(self.app)
                def handle_issue():
                    client = self.app.get_client()
                    return client.issues.create_comment(owner="test", repo="test")

                result = handle_issue()
                assert result["id"] == 456
                assert mock_ghapi.issues.create_comment.call_count == 1

    def test_decorator_preserves_function_behavior(self):
        """Test that decorated functions still work normally without rate limits."""
        mock_ghapi = Mock()
        mock_ghapi.pulls = Mock()
        mock_ghapi.pulls.create = Mock(return_value={"number": 123})

        with patch("githubapp.core.GhApi", return_value=mock_ghapi):
            with patch.object(self.app, "get_access_token") as mock_token:
                mock_token.return_value.token = "fake-token"

                @self.app.on("pull_request.opened")
                @with_rate_limit_handling(self.app)
                def handle_pr():
                    client = self.app.get_client()
                    return client.pulls.create(owner="test", repo="test", title="Test")

                result = handle_pr()
                assert result["number"] == 123
                mock_ghapi.pulls.create.assert_called_once_with(
                    owner="test", repo="test", title="Test"
                )

    def test_manual_retry_method_success(self):
        """Test the manual retry_with_rate_limit method with successful calls."""

        def success_func(arg1, arg2, kwarg1=None):
            return f"success: {arg1} {arg2} {kwarg1}"

        result = self.app.retry_with_rate_limit(
            success_func, "hello", "world", kwarg1="test"
        )
        assert result == "success: hello world test"

    def test_manual_retry_method_with_rate_limit(self):
        """Test the manual retry_with_rate_limit method with rate limit errors."""
        call_count = 0

        def rate_limit_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = Exception("Rate limited")
                error.code = 429
                error.headers = {"retry-after": "1"}
                raise error
            return "success after retry"

        with patch("time.sleep") as mock_sleep:
            result = self.app.retry_with_rate_limit(rate_limit_func)
            assert result == "success after retry"
            assert call_count == 2
            mock_sleep.assert_called_once_with(1)

    def test_manual_retry_method_non_rate_limit_error(self):
        """Test that non-rate-limit errors are not retried."""

        def error_func():
            raise ValueError("Not a rate limit error")

        with pytest.raises(ValueError, match="Not a rate limit error"):
            self.app.retry_with_rate_limit(error_func)

    def test_rate_limit_error_max_retries(self):
        """Test that rate limit errors respect max retries."""
        call_count = 0

        def always_rate_limited():
            nonlocal call_count
            call_count += 1
            error = Exception("Always rate limited")
            error.code = 429
            error.headers = {"retry-after": "1"}
            raise error

        with patch("time.sleep"):
            with pytest.raises(Exception) as exc_info:
                self.app.retry_with_rate_limit(always_rate_limited)

            # Should have tried 3 times total (initial + 2 retries)
            assert call_count == 3
            # Should raise GitHubRateLimitError
            assert "GitHubRateLimitError" in str(type(exc_info.value))

    def test_get_client_alias(self):
        """Test that get_client is a proper alias for client method."""
        mock_ghapi = Mock()

        with patch("githubapp.core.GhApi", return_value=mock_ghapi):
            with patch.object(self.app, "get_access_token") as mock_token:
                mock_token.return_value.token = "fake-token"

                client1 = self.app.client(123)
                client2 = self.app.get_client(123)

                # Both should return the same type of object
                assert type(client1) == type(client2)

    def test_decorator_restores_original_methods(self):
        """Test that the decorator properly restores original methods after execution."""
        original_client = self.app.client
        original_get_client = self.app.get_client

        mock_ghapi = Mock()
        mock_ghapi.repos = Mock()
        mock_ghapi.repos.get = Mock(return_value={"name": "test-repo"})

        with patch("githubapp.core.GhApi", return_value=mock_ghapi):
            with patch.object(self.app, "get_access_token") as mock_token:
                mock_token.return_value.token = "fake-token"

                @self.app.on("repository.created")
                @with_rate_limit_handling(self.app)
                def handle_repo():
                    client = self.app.get_client()
                    return client.repos.get(owner="test", repo="test")

                handle_repo()

                # Methods should be restored
                assert self.app.client == original_client
                assert self.app.get_client == original_get_client

    def test_rate_limit_detection_403_with_remaining_zero(self):
        """Test rate limit detection for 403 responses with x-ratelimit-remaining=0."""

        class MockResponse:
            def __init__(self, status_code, headers):
                self.status_code = status_code
                self.headers = headers

        # Test 403 with rate limit
        response_403_rate_limit = MockResponse(403, {"x-ratelimit-remaining": "0"})
        assert self.app._is_rate_limited(response_403_rate_limit)

        # Test 403 without rate limit (e.g., permission denied)
        response_403_permission = MockResponse(403, {"x-ratelimit-remaining": "100"})
        assert not self.app._is_rate_limited(response_403_permission)

        # Test 429 (always rate limit)
        response_429 = MockResponse(429, {})
        assert self.app._is_rate_limited(response_429)

    def test_retry_delay_calculation(self):
        """Test the retry delay calculation logic."""

        class MockResponse:
            def __init__(self, headers):
                self.headers = headers

        # Test with Retry-After header
        response_with_retry_after = MockResponse({"retry-after": "30"})
        delay = self.app._calculate_retry_delay(response_with_retry_after, 0)
        assert delay == 30

        # Test with x-ratelimit-reset header
        future_time = int(time.time()) + 45
        response_with_reset = MockResponse({"x-ratelimit-reset": str(future_time)})
        delay = self.app._calculate_retry_delay(response_with_reset, 0)
        assert 40 <= delay <= 50  # Should be around 45 seconds

        # Test exponential backoff fallback
        response_no_headers = MockResponse({})
        delay = self.app._calculate_retry_delay(response_no_headers, 1)
        assert delay == 5  # 60 * 2^1 = 120, but capped by rate_limit_max_sleep=5
