"""FastAPI extension for rapid GitHub app development"""

import logging
import time
import hmac
import hashlib
import httpx
import inspect
from fastapi import FastAPI, APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from ghapi.all import GhApi
from os import environ
import jwt
from .oauth import GitHubOAuth2
from .session import SessionManager
from contextlib import asynccontextmanager


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
        # OAuth2 (optional)
        oauth_client_id: str = None,
        oauth_client_secret: str = None,
        oauth_redirect_uri: str = None,
        oauth_scopes: list = None,
        oauth_routes_prefix: str = "/auth/github",
        enable_oauth: bool = None,
        oauth_session_secret: str = None,
    ):
        self._hook_mappings = {}
        self._access_token = None
        self.base_url = github_app_url or "https://api.github.com"
        self.id = github_app_id
        self.key = github_app_key
        self.secret = github_app_secret
        self.router = APIRouter()
        self._initialized = False
        self._webhook_route = github_app_route or "/"
        # OAuth2 setup (gated)
        self.oauth = None
        self._enable_oauth = False
        self._oauth_routes_prefix = oauth_routes_prefix
        self._session_mgr = None
        if oauth_client_id and oauth_client_secret:
            self.oauth = GitHubOAuth2(
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                redirect_uri=oauth_redirect_uri,
                scopes=oauth_scopes,
            )
            self._enable_oauth = enable_oauth if enable_oauth is not None else True
            if oauth_session_secret:
                self._session_mgr = SessionManager(oauth_session_secret)

        if app is not None:
            # Auto-wire on construction; subsequent explicit init_app calls will no-op
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
        # Idempotent setup: avoid mounting more than once
        if self._initialized:
            LOG.debug("GitHubApp.init_app called more than once; ignoring subsequent call")
            return

        # Register router endpoint for GitHub webhook
        self._webhook_route = route or self._webhook_route or "/"
        self.router.post(self._webhook_route)(self._handle_request)
        app.include_router(self.router)
        # copy config from FastAPI app
        # ensure app has config dict (for backward compatibility)
        if not hasattr(app, "config"):
            app.config = {}
        self.config = app.config

        # Honor base URL from config (e.g., GitHub Enterprise), if provided
        cfg_url = self.config.get("GITHUBAPP_URL")
        if cfg_url:
            self.base_url = cfg_url

        # Set config values from constructor parameters if they were provided
        if self.id is not None:
            self.config["GITHUBAPP_ID"] = self.id
        if self.key is not None:
            self.config["GITHUBAPP_PRIVATE_KEY"] = self.key
        if self.secret is not None:
            self.config["GITHUBAPP_WEBHOOK_SECRET"] = self.secret

        # Mount OAuth2 routes only if enabled and fully configured (session secret)
        if self._enable_oauth and self.oauth and self._session_mgr:
            self._setup_oauth_routes(app)

        self._initialized = True

    def _setup_oauth_routes(self, app: FastAPI):
        prefix = self._oauth_routes_prefix or "/auth/github"
        router = APIRouter()

        @router.get("/login")
        async def oauth_login(redirect_to: str = None, scopes: str = None):
            scope_list = scopes.split(",") if scopes else None
            url = self.oauth.generate_auth_url(scopes=scope_list)
            return JSONResponse({"auth_url": url})

        @router.get("/callback")
        async def oauth_callback(code: str = None, state: str = None, error: str = None):
            if error:
                raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
            if not code:
                raise HTTPException(status_code=400, detail="Missing authorization code")
            try:
                token = await self.oauth.exchange_code_for_token(code, state)
                user = await self.oauth.get_user_info(token["access_token"])
            except ValueError as ve:
                # For now, surface as 500 to match existing expectations
                raise HTTPException(status_code=500, detail=str(ve))
            except Exception as ex:
                # Surface upstream failures as 500 in this phase
                raise HTTPException(status_code=500, detail=str(ex))
            session_token = self._session_mgr.create_session_token(user)
            return JSONResponse({"user": user, "session_token": session_token})

        @router.post("/logout")
        async def oauth_logout():
            # Stateless JWTs: clients drop the token; server may add blacklist if desired.
            return {"status": "logged_out"}

        @router.get("/user")
        async def oauth_user(current=Depends(self.get_current_user)):
            return current

        app.include_router(router, prefix=prefix, tags=["oauth2"])
        # Ensure OAuth2 http client is closed via lifespan (no deprecated on_event)
        self._install_lifespan_cleanup(app)

    def _install_lifespan_cleanup(self, app: FastAPI):
        """Install a lifespan context that closes shared resources on shutdown.

        This chains any existing lifespan_context defined on the app's router
        to avoid clobbering user-defined lifespan behavior.
        """
        existing_lifespan = getattr(app.router, "lifespan_context", None)

        @asynccontextmanager
        async def lifespan(ap: FastAPI):
            if callable(existing_lifespan):
                # Chain existing lifespan
                async with existing_lifespan(ap) as state:
                    try:
                        yield state
                    finally:
                        if self.oauth and hasattr(self.oauth, "aclose"):
                            await self.oauth.aclose()
            else:
                try:
                    yield
                finally:
                    if self.oauth and hasattr(self.oauth, "aclose"):
                        await self.oauth.aclose()

        app.router.lifespan_context = lifespan

    def get_current_user(self, request: Request):
        if not self._session_mgr:
            raise HTTPException(status_code=401, detail="OAuth2 not configured")
        # Bearer token support
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
        if not token:
            token = request.cookies.get("session_token")
        if not token:
            raise HTTPException(status_code=401, detail="Missing session token")
        try:
            return self._session_mgr.verify_session_token(token)
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))

    @property
    def installation_token(self):
        return self._access_token

    def client(self, installation_id: int = None):
        """GitHub client authenticated as GitHub app installation"""
        if installation_id is None:
            try:
                installation_id = self.payload["installation"]["id"]
            except Exception:
                raise GitHubAppError(
                    message="Missing installation id; provide installation_id or call within a webhook context",
                    status=400,
                )
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
        body = {"user_id": user_id} if user_id else {}
        response = httpx.post(
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
        raise GitHubAppError(
            message="Failed to create installation access token",
            status=response.status_code,
            data=response.text,
        )

    def list_installations(self, per_page=30, page=1):
        """
        GETs https://api.github.com/app/installations
        :return: :obj: `list` of installations
        """
        params = {"page": page, "per_page": per_page}

        response = httpx.get(
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
        raise GitHubAppError(
            message="Failed to list installations",
            status=response.status_code,
            data=response.text,
        )

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
            import asyncio

            for function in functions_to_call:
                try:
                    if inspect.iscoroutinefunction(function):
                        result = await function()
                    else:
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(None, function)
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