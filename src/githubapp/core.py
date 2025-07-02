"""FastAPI extension for rapid GitHub app development"""

import logging
import time
import hmac
import hashlib
import requests
import inspect
from fastapi import FastAPI, APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from ghapi.all import GhApi
from os import environ
import jwt


LOG = logging.getLogger(__name__)

STATUS_FUNC_CALLED = "HIT"
STATUS_NO_FUNC_CALLED = "MISS"


class GitHubAppError(Exception):
    def __init__(self, message="GitHub App error", status=None, data=None):
        self.message = message
        self.status = status
        self.data = data
        super().__init__(self.message)


class GitHubAppValidationError(Exception):
    def __init__(self, message="GitHub App validation error", status=None, data=None):
        self.message = message
        self.status = status
        self.data = data
        super().__init__(self.message)


class GitHubAppBadCredentials(Exception):
    def __init__(self, message="GitHub App bad credentials", status=None, data=None):
        self.message = message
        self.status = status
        self.data = data
        super().__init__(self.message)


class GithubUnauthorized(Exception):
    def __init__(self, message="GitHub unauthorized", status=None, data=None):
        self.message = message
        self.status = status
        self.data = data
        super().__init__(self.message)


class GithubAppUnkownObject(Exception):
    def __init__(self, message="GitHub object not found", status=None, data=None):
        self.message = message
        self.status = status
        self.data = data
        super().__init__(self.message)


class InstallationAuthorization:
    def __init__(self, token: str, expires_at: str = None):
        self.token = token
        self.expires_at = expires_at

    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        import time

        if isinstance(self.expires_at, str):
            # Handle ISO format or assume it's a timestamp
            return False  # Simplified for now
        return time.time() > self.expires_at


class GitHubApp:
    """The GitHubApp object provides the central interface for interacting GitHub hooks
    and creating GitHub app clients.

    GitHubApp object allows using the "on" decorator to make GitHub hooks to functions
    and provides authenticated ghapi clients for interacting with the GitHub API.

    Keyword Arguments:
        app {FastAPI object} -- App instance - created with FastAPI() (default: {None})
    """

    def __init__(
        self,
        app: FastAPI = None,
        *,
        github_app_id: int = None,
        github_app_key: bytes = None,
        github_app_secret: bytes = None,
        github_app_url: str = None,
        github_app_route: str = "/",
    ):
        self._hook_mappings = {}
        self._access_token = None
        self.base_url = github_app_url or "https://api.github.com"
        self.id = github_app_id
        self.key = github_app_key
        self.secret = github_app_secret
        self.router = APIRouter()
        if app is not None:
            self.init_app(app, route=github_app_route)

    @staticmethod
    def load_env(app):
        """
        Read env vars into app.config only if they’re not already set.
        Only raw private key via GITHUBAPP_PRIVATE_KEY is supported.
        """
        # App ID
        if "GITHUBAPP_ID" in environ and "GITHUBAPP_ID" not in app.config:
            app.config["GITHUBAPP_ID"] = int(environ["GITHUBAPP_ID"])

        # Raw private key only
        if (
            "GITHUBAPP_PRIVATE_KEY" in environ
            and "GITHUBAPP_PRIVATE_KEY" not in app.config
        ):
            app.config["GITHUBAPP_PRIVATE_KEY"] = environ["GITHUBAPP_PRIVATE_KEY"]

        # Webhook secret
        if (
            "GITHUBAPP_WEBHOOK_SECRET" in environ
            and "GITHUBAPP_WEBHOOK_SECRET" not in app.config
        ):
            app.config["GITHUBAPP_WEBHOOK_SECRET"] = environ["GITHUBAPP_WEBHOOK_SECRET"]

        # Webhook path
        if (
            "GITHUBAPP_WEBHOOK_PATH" in environ
            and "GITHUBAPP_WEBHOOK_PATH" not in app.config
        ):
            app.config["GITHUBAPP_WEBHOOK_PATH"] = environ["GITHUBAPP_WEBHOOK_PATH"]

    def init_app(self, app: FastAPI, *, route: str = "/"):
        """Initializes GitHubApp app by setting configuration variables.

        The GitHubApp instance is given the following configuration variables by calling on FastAPI's configuration:

        `GITHUBAPP_ID`:

            GitHub app ID as an int (required).
            Default: None

        `GITHUBAPP_PRIVATE_KEY`:

            Private key used to sign access token requests as bytes or utf-8 encoded string (required).
            Default: None

        `GITHUBAPP_WEBHOOK_SECRET`:

            Secret used to secure webhooks as bytes or utf-8 encoded string (required). set to `False` to disable
            verification (not recommended for production).
            Default: None

        `GITHUBAPP_URL`:

            URL of GitHub API (used for GitHub Enterprise) as a string.
            Default: None

        `GITHUBAPP_WEBHOOK_PATH`:

            Path used for GitHub hook requests as a string.
            Default: '/'
        """
        # Register router endpoint for GitHub webhook
        app.include_router(self.router)
        self.router.post(route)(self._handle_request)
        # copy config from FastAPI app
        # ensure app has config dict (for backward compatibility)
        if not hasattr(app, "config"):
            app.config = {}
        self.config = app.config

        # Set config values from constructor parameters if they were provided
        if self.id is not None:
            self.config["GITHUBAPP_ID"] = self.id
        if self.key is not None:
            self.config["GITHUBAPP_PRIVATE_KEY"] = self.key
        if self.secret is not None:
            self.config["GITHUBAPP_WEBHOOK_SECRET"] = self.secret

    @property
    def installation_token(self):
        return self._access_token

    def client(self, installation_id: int = None):
        """GitHub client authenticated as GitHub app installation"""
        if installation_id is None:
            installation_id = self.payload["installation"]["id"]
        token = self.get_access_token(installation_id).token
        return GhApi(token=token)

    def _create_jwt(self, expiration=60):
        """
        Creates a signed JWT, valid for 60 seconds by default.
        The expiration can be extended beyond this, to a maximum of 600 seconds.
        :param expiration: int
        :return string:
        """
        now = int(time.time())
        payload = {"iat": now, "exp": now + expiration, "iss": self.id}
        encrypted = jwt.encode(payload, key=self.key, algorithm="RS256")

        if isinstance(encrypted, bytes):
            encrypted = encrypted.decode("utf-8")
        return encrypted

    def get_access_token(self, installation_id, user_id=None):
        """
        Get an access token for the given installation id.
        POSTs https://api.github.com/app/installations/<installation_id>/access_tokens
        :param user_id: int
        :param installation_id: int
        :return: :class:`github.InstallationAuthorization.InstallationAuthorization`
        """
        body = {}
        if user_id:
            body = {"user_id": user_id}
        response = requests.post(
            f"{self.base_url}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._create_jwt()}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "FastAPI-GithubApp/Python",
            },
            json=body,
        )
        if response.status_code == 201:
            return InstallationAuthorization(
                token=response.json()["token"], expires_at=response.json()["expires_at"]
            )
        elif response.status_code == 403:
            raise GitHubAppBadCredentials(
                status=response.status_code, data=response.text
            )
        elif response.status_code == 404:
            raise GithubAppUnkownObject(status=response.status_code, data=response.text)
        raise Exception(status=response.status_code, data=response.text)

    def list_installations(self, per_page=30, page=1):
        """
        GETs https://api.github.com/app/installations
        :return: :obj: `list` of installations
        """
        params = {"page": page, "per_page": per_page}

        response = requests.get(
            f"{self.base_url}/app/installations",
            headers={
                "Authorization": f"Bearer {self._create_jwt()}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "FastAPI-GithubApp/python",
            },
            params=params,
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise GithubUnauthorized(status=response.status_code, data=response.text)
        elif response.status_code == 403:
            raise GitHubAppBadCredentials(
                status=response.status_code, data=response.text
            )
        elif response.status_code == 404:
            raise GithubAppUnkownObject(status=response.status_code, data=response.text)
        raise Exception(status=response.status_code, data=response.text)

    def on(self, event_action):
        """Decorator routes a GitHub hook to the wrapped function.

        Functions decorated as a hook recipient are registered as the function for the given GitHub event.

        @github_app.on('issues.opened')
        def cruel_closer():
            owner = github_app.payload['repository']['owner']['login']
            repo = github_app.payload['repository']['name']
            num = github_app.payload['issue']['id']
            issue = github_app.client.issue(owner, repo, num)
            issue.create_comment('Could not replicate.')
            issue.close()

        Arguments:
            event_action {str} -- Name of the event and optional action (separated by a period), e.g. 'issues.opened' or
                'pull_request'
        """

        def decorator(f):
            if event_action not in self._hook_mappings:
                self._hook_mappings[event_action] = [f]
            else:
                self._hook_mappings[event_action].append(f)

            # make sure the function can still be called normally (e.g. if a user wants to pass in their
            # own Context for whatever reason).
            return f

        return decorator

    async def _extract_payload(self, request: Request) -> dict:
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "ERROR", "description": "Invalid JSON payload."},
            )
        if "installation" not in payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "ERROR",
                    "description": "Missing installation in payload.",
                },
            )
        return payload

    async def _handle_request(self, request: Request):
        # validate HTTP Content-Type header
        content_type = request.headers.get("Content-Type", "")
        valid = content_type.startswith("application/json") or (
            content_type.startswith("application/") and content_type.endswith("+json")
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "ERROR",
                    "description": "Invalid HTTP Content-Type header for JSON body (must be application/json or application/*+json).",
                },
            )
        # signature verification
        secret = self.config.get("GITHUBAPP_WEBHOOK_SECRET", None)
        body_bytes = await request.body()
        if secret is not False and secret is not None:
            # Convert secret to bytes if it's a string
            if isinstance(secret, str):
                secret_bytes = secret.encode()
            else:
                secret_bytes = secret

            # verify sha256 signature if present, else sha1, else error
            sig256 = request.headers.get("X-Hub-Signature-256")
            sig1 = request.headers.get("X-Hub-Signature")
            if sig256:
                expected = (
                    "sha256="
                    + hmac.new(secret_bytes, body_bytes, hashlib.sha256).hexdigest()
                )
                if not hmac.compare_digest(sig256, expected):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            elif sig1:
                expected = (
                    "sha1="
                    + hmac.new(secret_bytes, body_bytes, hashlib.sha1).hexdigest()
                )
                if not hmac.compare_digest(sig1, expected):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            else:
                # missing signature header
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        # proceed to extract payload
        functions_to_call = []
        calls = {}

        # validate headers and payload
        payload = await self._extract_payload(request)
        self.payload = payload
        event = request.headers.get("X-GitHub-Event")
        action = payload.get("action")
        if not event:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "ERROR",
                    "description": "Missing X-GitHub-Event header.",
                },
            )

        # webhook verification can be added here if secret provided

        # determine functions to call
        if event in self._hook_mappings:
            functions_to_call += self._hook_mappings[event]

        if action:
            event_action = f"{event}.{action}"
            if event_action in self._hook_mappings:
                functions_to_call += self._hook_mappings[event_action]

        if functions_to_call:
            for function in functions_to_call:
                try:
                    result = await function() if inspect.iscoroutinefunction(function) else function()
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
                    )
                calls[function.__name__] = result
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "HIT", "calls": calls},
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK, content={"status": "MISS", "calls": {}}
        )