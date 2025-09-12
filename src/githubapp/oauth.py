"""OAuth2 manager for GitHub authentication (internal, gated by config).

This module provides a minimal GitHub OAuth2 flow implementation suitable for
library usage. Routes are mounted by the core GitHubApp only when explicitly
configured and enabled.
"""

from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import secrets
import time
import httpx


class GitHubOAuth2:
    """GitHub OAuth2 authentication manager.

    Uses a shared httpx.AsyncClient with explicit timeouts. Network calls are
    performed only when async methods are awaited.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        base_url: str = "https://github.com",
        api_url: str = "https://api.github.com",
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["user:email", "read:user"]
        self.base_url = base_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self._timeout = timeout or httpx.Timeout(10.0, connect=5.0)
        self._client: Optional[httpx.AsyncClient] = None
        # in-memory state to support CSRF protection in basic setups
        self._state_store: Dict[str, Dict[str, Any]] = {}

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def generate_auth_url(
        self,
        *,
        state: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        redirect_uri: Optional[str] = None,
        allow_signup: bool = True,
    ) -> str:
        """Generate GitHub OAuth authorization URL and record state."""
        if state is None:
            state = secrets.token_urlsafe(32)

        ru = redirect_uri or self.redirect_uri
        sc = scopes or self.scopes
        self._state_store[state] = {
            "ts": time.time(),
            "redirect_uri": ru,
            "scopes": sc,
        }

        params = {
            "client_id": self.client_id,
            "redirect_uri": ru,
            "scope": " ".join(sc),
            "state": state,
            "allow_signup": "true" if allow_signup else "false",
        }
        return f"{self.base_url}/login/oauth/authorize?{urlencode(params)}"

    async def exchange_code_for_token(
        self, code: str, state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Returns token data as a dict: { access_token, token_type, scope, ... }
        """
        if state is not None and state not in self._state_store:
            raise ValueError("Invalid OAuth2 state parameter")

        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/login/oauth/access_token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": (
                    (self._state_store.get(state, {})).get("redirect_uri")
                    if state
                    else self.redirect_uri
                ),
            },
            headers={"Accept": "application/json"},
        )
        if state:
            self._state_store.pop(state, None)

        if resp.status_code != 200:
            raise RuntimeError(f"OAuth2 token exchange failed ({resp.status_code})")

        data = resp.json()
        if "error" in data:
            raise RuntimeError(data.get("error_description") or data["error"])
        return data

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch authenticated user info; attempts to include emails if allowed."""
        client = self._get_client()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "FastAPI-GithubApp/OAuth2",
        }
        user_resp = await client.get(f"{self.api_url}/user", headers=headers)
        if user_resp.status_code != 200:
            raise RuntimeError("Failed to fetch user info")
        user = user_resp.json()

        emails: List[Dict[str, Any]] = []
        emails_resp = await client.get(f"{self.api_url}/user/emails", headers=headers)
        if emails_resp.status_code == 200:
            emails = emails_resp.json()

        return {
            "id": user.get("id"),
            "login": user.get("login"),
            "name": user.get("name"),
            "email": user.get("email"),
            "avatar_url": user.get("avatar_url"),
            "emails": emails,
        }
