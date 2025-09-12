# Phase 1: Replace Synchronous HTTP with Async HTTP Client

## Objective
Replace all synchronous `requests` library calls with async `httpx` to eliminate blocking I/O operations and improve performance.

## Current Issues
- `requests.post()` and `requests.get()` calls block the event loop
- GitHub API calls are synchronous, creating bottlenecks
- Missing async HTTP capabilities limits scalability

## Implementation Tasks

### 1. Update Dependencies

- [ ] Add `httpx` as a main dependency in `pyproject.toml`
- [ ] Keep `requests` for backward compatibility during Phase 1
- [ ] Prepare optional extras structure for future phases

#### Updated pyproject.toml structure:

```toml
[tool.poetry.dependencies]
python = "^3.9"
fastapi = ">=0.95.0"
uvicorn = { version = ">=0.22.0", extras = ["standard"] }
ghapi = ">=1.0.0"
pyjwt = { version = ">=2.8.0", extras = ["crypto"] }
httpx = ">=0.24.0"  # New async HTTP client
requests = "*"      # Keep for Phase 1 compatibility

# Prepare optional extras for future phases (commented out for Phase 1)
# redis = { version = ">=4.0.0", optional = true }
# celery = { version = ">=5.2.0", optional = true }
# sqlalchemy = { version = ">=1.4.0", optional = true }

# [tool.poetry.extras]
# redis = ["redis"]
# celery = ["celery", "redis"]
# database = ["sqlalchemy"]
# all-queues = ["redis", "celery", "sqlalchemy"]
```

### 2. Refactor HTTP Client Usage

#### Files to Modify:
- `src/githubapp/core.py`

#### Specific Changes:

**A. Replace `get_access_token()` method:**
```python
# Current synchronous implementation uses requests.post()
# Replace with async httpx.AsyncClient.post()
```

**B. Replace `list_installations()` method:**
```python
# Current synchronous implementation uses requests.get()
# Replace with async httpx.AsyncClient.get()
```

### 3. Update Method Signatures
- [ ] Make `get_access_token()` async
- [ ] Make `list_installations()` async
- [ ] Update all callers to use `await`

### 4. Handle HTTP Client Lifecycle
- [ ] Create async context manager for httpx.AsyncClient
- [ ] Implement proper client session management
- [ ] Add connection pooling configuration

### 5. Error Handling Updates
- [ ] Update exception handling for httpx-specific errors
- [ ] Maintain compatibility with existing custom exceptions
- [ ] Add timeout configuration

### 6. Testing Updates
- [ ] Update tests to handle async methods
- [ ] Mock httpx instead of requests
- [ ] Add async test fixtures
- [ ] Test error scenarios with new HTTP client

## Implementation Guidelines

### Code Standards:
- Use `async with httpx.AsyncClient()` pattern
- Set appropriate timeouts (default: 30s for GitHub API)
- Maintain backward compatibility where possible
- Follow existing error handling patterns

### Configuration Options:
```python
# Add new config options:
GITHUBAPP_HTTP_TIMEOUT = 30  # seconds
GITHUBAPP_HTTP_RETRIES = 3   # retry attempts
```

### Example Implementation Pattern:
```python
async def get_access_token(self, installation_id, user_id=None):
    body = {}
    if user_id:
        body = {"user_id": user_id}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{self.base_url}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._create_jwt()}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "FastAPI-GithubApp/Python",
            },
            json=body,
        )
        # Handle response...
```

## Success Criteria
- [ ] All HTTP requests are non-blocking
- [ ] No performance regression
- [ ] All existing tests pass
- [ ] New async tests added
- [ ] Documentation updated
- [ ] Example app still works

## Testing Strategy
1. Unit tests for each async method
2. Integration tests with mocked HTTP responses
3. Performance tests comparing before/after
4. Test webhook handling under load

## Potential Challenges
- Ensuring proper async context throughout call chain
- Managing HTTP client lifecycle efficiently
- Maintaining error handling semantics
- Updating dependent code to handle async methods

## Next Phase Preview
Phase 2 will build on these async HTTP capabilities to implement background task support for webhook processing.
