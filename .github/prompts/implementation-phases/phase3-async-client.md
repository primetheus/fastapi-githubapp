# Phase 3: Async GitHub Client Integration

## Objective

Create native async GitHub client methods that seamlessly integrate with the background task system, providing non-blocking GitHub API operations and improved performance for GitHub App interactions.

## Current Issues

- `GhApi` client is synchronous and blocks the event loop
- No async version of GitHub API interactions
- Client instantiation happens synchronously
- Missing async context manager support for GitHub operations

## Implementation Tasks

### 1. Async GitHub Client Wrapper

#### Create AsyncGitHubClient Class

```python
class AsyncGitHubClient:
    """Async wrapper around GitHub API operations"""
    
    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.token = token
        self.base_url = base_url
        self._client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        pass
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass
```

#### Core Async Methods

- [ ] Implement async repository operations
- [ ] Add async issue management methods
- [ ] Create async pull request operations
- [ ] Build async webhook management functions
- [ ] Add async installation management

### 2. Enhanced GitHubApp Client Methods

#### Replace Synchronous Client Access

```python
class GitHubApp:
    async def async_client(self, installation_id: int = None) -> AsyncGitHubClient:
        """Get async GitHub client for installation"""
        if installation_id is None:
            installation_id = self.payload["installation"]["id"]
        
        token_info = await self.get_access_token(installation_id)
        return AsyncGitHubClient(token=token_info.token, base_url=self.base_url)
    
    def client(self, installation_id: int = None):
        """Backward compatible sync client (deprecated)"""
        # Keep for backward compatibility
        pass
```

#### Client Factory Pattern

- [ ] Implement client pooling for performance
- [ ] Add client lifecycle management
- [ ] Create installation-specific client caching
- [ ] Add automatic token refresh handling

### 3. Common GitHub Operations

#### Repository Operations

```python
class AsyncGitHubClient:
    async def get_repository(self, owner: str, repo: str):
        """Get repository information"""
        pass
    
    async def create_repository(self, name: str, **kwargs):
        """Create new repository"""
        pass
    
    async def update_repository(self, owner: str, repo: str, **kwargs):
        """Update repository settings"""
        pass
```

#### Issue Management

```python
async def get_issue(self, owner: str, repo: str, issue_number: int):
    """Get issue details"""
    pass

async def create_issue(self, owner: str, repo: str, title: str, body: str = None, **kwargs):
    """Create new issue"""
    pass

async def update_issue(self, owner: str, repo: str, issue_number: int, **kwargs):
    """Update issue"""
    pass

async def close_issue(self, owner: str, repo: str, issue_number: int):
    """Close an issue"""
    pass

async def add_issue_comment(self, owner: str, repo: str, issue_number: int, body: str):
    """Add comment to issue"""
    pass
```

#### Pull Request Operations

```python
async def get_pull_request(self, owner: str, repo: str, pull_number: int):
    """Get pull request details"""
    pass

async def create_pull_request(self, owner: str, repo: str, title: str, head: str, base: str, **kwargs):
    """Create new pull request"""
    pass

async def merge_pull_request(self, owner: str, repo: str, pull_number: int, **kwargs):
    """Merge pull request"""
    pass

async def add_pr_review(self, owner: str, repo: str, pull_number: int, event: str, body: str = None):
    """Add pull request review"""
    pass
```

### 4. Error Handling and Resilience

#### Async-Aware Error Handling

```python
class AsyncGitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message)

class AsyncGitHubRateLimitError(AsyncGitHubAPIError):
    def __init__(self, reset_time: int, **kwargs):
        self.reset_time = reset_time
        super().__init__(**kwargs)
```

#### Retry and Rate Limiting

- [ ] Implement async retry logic with exponential backoff
- [ ] Add rate limit detection and automatic waiting
- [ ] Create circuit breaker pattern for API failures
- [ ] Add request caching for frequently accessed data

### 5. Integration with Background Tasks

#### Task-Aware Client Usage

```python
@github_app.on("issues.opened", background=True)
async def process_issue_async():
    async with github_app.async_client() as client:
        # All operations are async and non-blocking
        issue = await client.get_issue(
            owner=github_app.payload["repository"]["owner"]["login"],
            repo=github_app.payload["repository"]["name"],
            issue_number=github_app.payload["issue"]["number"]
        )
        
        # Perform analysis
        analysis_result = await analyze_issue_content(issue)
        
        # Add comment based on analysis
        if analysis_result.needs_attention:
            await client.add_issue_comment(
                owner=github_app.payload["repository"]["owner"]["login"],
                repo=github_app.payload["repository"]["name"],
                issue_number=github_app.payload["issue"]["number"],
                body=f"Analysis result: {analysis_result.summary}"
            )
```

#### Batch Operations Support

- [ ] Implement async batch API calls
- [ ] Add concurrent operation management
- [ ] Create bulk update capabilities
- [ ] Add progress tracking for long operations

### 6. GraphQL Support

#### Async GraphQL Client

```python
async def execute_graphql(self, query: str, variables: dict = None):
    """Execute GraphQL query against GitHub API"""
    pass

async def get_repository_details_graphql(self, owner: str, repo: str):
    """Get detailed repository info via GraphQL"""
    query = """
    query($owner: String!, $repo: String!) {
        repository(owner: $owner, name: $repo) {
            id
            name
            description
            # ... other fields
        }
    }
    """
    return await self.execute_graphql(query, {"owner": owner, "repo": repo})
```

### 7. Performance Optimizations

#### Connection Pooling

- [ ] Implement HTTP connection pooling
- [ ] Add keep-alive support for persistent connections
- [ ] Create connection limit management
- [ ] Add connection health monitoring

#### Caching Strategy

- [ ] Implement response caching for read operations
- [ ] Add ETag-based conditional requests
- [ ] Create intelligent cache invalidation
- [ ] Add cache statistics and monitoring

### 8. Testing and Validation

#### Async Client Testing

```python
# Test framework for async client operations
@pytest.mark.asyncio
async def test_async_issue_creation():
    async with github_app.async_client() as client:
        issue = await client.create_issue(
            owner="test-org",
            repo="test-repo",
            title="Test Issue",
            body="This is a test issue"
        )
        assert issue.title == "Test Issue"

# Mock async GitHub API responses
@pytest.fixture
async def mock_github_client():
    with respx.mock:
        respx.post("https://api.github.com/repos/test-org/test-repo/issues").mock(
            return_value=httpx.Response(201, json={"title": "Test Issue"})
        )
        yield
```

#### Performance Testing

- [ ] Benchmark async vs sync client performance
- [ ] Test concurrent API call handling
- [ ] Measure memory usage improvements
- [ ] Validate rate limit handling efficiency

## Configuration Options

```python
# New async client configuration
GITHUBAPP_CLIENT_POOL_SIZE = 10           # HTTP connection pool size
GITHUBAPP_CLIENT_TIMEOUT = 30             # Request timeout in seconds
GITHUBAPP_CLIENT_CACHE_TTL = 300          # Cache TTL in seconds
GITHUBAPP_CLIENT_RETRY_ATTEMPTS = 3       # Retry attempts for failed requests
GITHUBAPP_CLIENT_RETRY_BACKOFF = 2        # Backoff multiplier for retries
GITHUBAPP_CLIENT_ENABLE_CACHE = True      # Enable response caching
```

## Migration Strategy

### Gradual Migration Path

1. **Phase 3a**: Introduce async client alongside existing sync client
2. **Phase 3b**: Update documentation and examples to use async client
3. **Phase 3c**: Add deprecation warnings to sync client methods
4. **Phase 3d**: Migrate internal usage to async client

### Example Migration

```python
# Old synchronous pattern
@github_app.on("issues.opened")
def handle_issue():
    client = github_app.client()
    issue = client.issues.get(owner, repo, issue_number)
    # Process issue...

# New async pattern
@github_app.on("issues.opened", background=True)
async def handle_issue():
    async with github_app.async_client() as client:
        issue = await client.get_issue(owner, repo, issue_number)
        # Process issue asynchronously...
```

## Success Criteria

- [ ] All GitHub API operations available in async form
- [ ] No blocking calls in async client methods
- [ ] Proper error handling and retry logic
- [ ] Rate limiting handled automatically
- [ ] Performance improvement over sync client
- [ ] Backward compatibility maintained
- [ ] Comprehensive test coverage
- [ ] Documentation and examples updated

## Error Scenarios and Handling

1. **Rate Limit Exceeded**: Automatically wait for reset time
2. **Network Timeouts**: Retry with exponential backoff
3. **API Errors**: Provide detailed error information
4. **Token Expiration**: Automatic token refresh
5. **Connection Failures**: Circuit breaker pattern

## Next Phase Preview

Phase 4 will integrate optional external task queue systems (Redis, Celery) and add advanced monitoring and observability features to complete the async ecosystem.
