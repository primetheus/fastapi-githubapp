"""Minimal JWT session manager for OAuth2 (internal).

This module avoids any import-time side effects and provides helpers to create
and verify short-lived JWTs for user sessions.
"""

from typing import Any, Dict
from datetime import datetime, timedelta, timezone
import jwt


class SessionManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_session_token(
        self, user: Dict[str, Any], *, expires_in_seconds: int = 86400
    ) -> str:
        now = datetime.now(tz=timezone.utc)
        payload = {
            "sub": str(user.get("id")),
            "login": user.get("login"),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
            "type": "session",
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    def verify_session_token(self, token: str) -> Dict[str, Any]:
        data = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        if data.get("type") != "session":
            raise jwt.InvalidTokenError("Invalid token type")
        return data
