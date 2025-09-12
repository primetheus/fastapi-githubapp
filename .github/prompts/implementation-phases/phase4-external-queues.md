# Phase 4: External Task Queue Integration & Observability

## Objective

Complete the async ecosystem by integrating optional external task queue systems (Redis, Celery, Database) and adding comprehensive monitoring, observability, and scaling capabilities for production deployments.

## Current State After Phase 3

- Async HTTP client implemented
- Background task system with in-memory queue
- Async GitHub client with full API coverage
- Basic task management and retry logic

## Implementation Tasks

### 1. External Task Queue Backends (Optional Dependencies)

⚠️ **IMPORTANT**: All external backends are **optional dependencies** to prevent conflicts with existing task queue systems in upstream projects.

#### Redis/RQ Integration (Optional Extra: `pip install fastapi-githubapp[redis]`)

```python
# src/githubapp/task_queues/redis_queue.py
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class RedisTaskQueue(TaskQueueBackend):
    """Redis-based task queue implementation with namespace isolation"""
    
    def __init__(self, redis_url: str = None, **config):
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis not installed. Install with: pip install fastapi-githubapp[redis]")
            
        # Use isolated Redis DB to avoid conflicts
        default_url = "redis://localhost:6379/15"  # High DB number
        self.redis_url = redis_url or os.getenv("GITHUBAPP_TASK_REDIS_URL", default_url)
        
        # Isolated connection pool
        self._pool = redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=config.get("max_connections", 5),
            decode_responses=True
        )
        self._redis = redis.Redis(connection_pool=self._pool)
        
        # Namespaced keys to prevent conflicts
        self.key_prefix = config.get("key_prefix", "githubapp:tasks:")
    
    def _make_key(self, key: str) -> str:
        """Add namespace prefix to avoid key conflicts"""
        return f"{self.key_prefix}{key}"
    
    async def enqueue(self, task: Task) -> str:
        """Enqueue task in Redis with namespaced keys"""
        task_key = self._make_key(task.id)
        # Implementation with isolated queues...
```

#### Celery Integration (Optional Extra: `pip install fastapi-githubapp[celery]`)

```python
# src/githubapp/task_queues/celery_queue.py
import uuid
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

class IsolatedCeleryTaskQueue(TaskQueueBackend):
    """Celery backend that doesn't interfere with existing Celery apps"""
    
    def __init__(self, broker_url: str, result_backend: str = None, **config):
        if not CELERY_AVAILABLE:
            raise RuntimeError("Celery not installed. Install with: pip install fastapi-githubapp[celery]")
        
        # Create ISOLATED Celery app with unique name
        app_name = f"githubapp_{uuid.uuid4().hex[:8]}"
        unique_queue = f"githubapp_tasks_{uuid.uuid4().hex[:8]}"
        
        self._app = Celery(
            app_name,
            broker=broker_url,
            backend=result_backend or broker_url,
            # Isolated configuration to prevent conflicts
            task_default_queue=unique_queue,
            include=[],  # Don't auto-discover upstream tasks
            task_routes={'githubapp.*': {'queue': unique_queue}}
        )
        
        # Non-intrusive configuration
        self._app.conf.update(
            worker_hijack_root_logger=False,  # Don't interfere with logging
            worker_log_format="[GITHUBAPP %(levelname)s] %(message)s",
            worker_state_db=None,  # Don't create conflicting state files
        )
```

#### Database-Backed Queue (Optional Extra: `pip install fastapi-githubapp[database]`)

```python
# src/githubapp/task_queues/database_queue.py
try:
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import create_async_engine
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

class DatabaseTaskQueue(TaskQueueBackend):
    """Database-backed task queue with isolated schema"""
    
    def __init__(self, database_url: str, **config):
        if not DATABASE_AVAILABLE:
            raise RuntimeError("SQLAlchemy not installed. Install with: pip install fastapi-githubapp[database]")
            
        # Use schema/table prefix to avoid conflicts
        self.table_prefix = config.get("table_prefix", "githubapp_")
        self.schema = config.get("schema", "githubapp_tasks")
        
        self._engine = create_async_engine(database_url)
    
    async def create_tables(self):
        """Create isolated task queue tables"""
        # Use prefixed table names like 'githubapp_tasks', 'githubapp_task_results'
        pass
```

### 2. Safe Task Queue Backend Factory

#### Dependency-Aware Queue Selection

```python
# src/githubapp/task_queues/__init__.py
from typing import Dict, Type, Optional
from .base import TaskQueueBackend
from .asyncio_queue import AsyncIOTaskQueue  # Always available

# Registry of available backends (populated based on installed dependencies)
_AVAILABLE_BACKENDS: Dict[str, Type[TaskQueueBackend]] = {
    "asyncio": AsyncIOTaskQueue,  # Built-in, no external dependencies
}

# Conditionally register optional backends
try:
    from .redis_queue import RedisTaskQueue
    _AVAILABLE_BACKENDS["redis"] = RedisTaskQueue
except ImportError:
    pass  # Redis backend not available

try:
    from .celery_queue import IsolatedCeleryTaskQueue
    _AVAILABLE_BACKENDS["celery"] = IsolatedCeleryTaskQueue
except ImportError:
    pass  # Celery backend not available

try:
    from .database_queue import DatabaseTaskQueue
    _AVAILABLE_BACKENDS["database"] = DatabaseTaskQueue
except ImportError:
    pass  # Database backend not available

class TaskQueueFactory:
    """Factory for creating task queue backends with safe fallbacks"""
    
    @staticmethod
    def create_queue(backend_type: str = "asyncio", **config) -> TaskQueueBackend:
        """Create appropriate task queue backend with graceful fallback"""
        
        if backend_type not in _AVAILABLE_BACKENDS:
            available = list(_AVAILABLE_BACKENDS.keys())
            error_msg = (
                f"Task queue backend '{backend_type}' not available. "
                f"Available backends: {available}. "
                f"To install: pip install fastapi-githubapp[{backend_type}]"
            )
            
            # Option 1: Fallback to asyncio with warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(error_msg)
            logger.warning("Falling back to 'asyncio' backend")
            backend_type = "asyncio"
            
            # Option 2: Alternatively, raise error for explicit handling
            # raise ValueError(error_msg)
        
        backend_class = _AVAILABLE_BACKENDS[backend_type]
        return backend_class(**config)
    
    @staticmethod
    def get_available_backends() -> list:
        """Get list of currently available backends"""
        return list(_AVAILABLE_BACKENDS.keys())

# Safe configuration-driven queue selection
def create_github_app_with_queue(app, backend_type: str = "asyncio", **queue_config):
    """Create GitHubApp with safe task queue backend selection"""
    
    # Namespace all configuration to prevent conflicts
    safe_config = {
        "redis_url": queue_config.get("redis_url") or os.getenv("GITHUBAPP_TASK_REDIS_URL"),
        "celery_broker": queue_config.get("celery_broker") or os.getenv("GITHUBAPP_TASK_CELERY_BROKER"),
        "database_url": queue_config.get("database_url") or os.getenv("GITHUBAPP_TASK_DB_URL"),
        # Add GITHUBAPP_ prefix to all config
        **{k: v for k, v in queue_config.items() if k.startswith("githubapp_")}
    }
    
    return GitHubApp(
        app,
        task_queue_backend=backend_type,
        task_queue_config=safe_config
    )
```

### 3. Advanced Task Management

#### Task Scheduling and Delayed Execution

```python
@github_app.on("schedule.daily")
async def daily_maintenance():
    """Scheduled daily maintenance task"""
    pass

# Schedule task for future execution
await github_app.schedule_task(
    daily_maintenance,
    delay=timedelta(hours=24),
    recurring=True
)

# Cron-like scheduling
@github_app.schedule("0 2 * * *")  # Daily at 2 AM
async def cleanup_old_data():
    """Clean up old data daily"""
    pass
```

#### Task Dependencies and Workflows

```python
@github_app.on("pull_request.opened", background=True)
async def pr_workflow():
    # Step 1: Run tests
    test_task = await github_app.enqueue_task(run_ci_tests)
    
    # Step 2: Code quality check (depends on tests)
    quality_task = await github_app.enqueue_task(
        run_quality_checks,
        depends_on=[test_task.id]
    )
    
    # Step 3: Security scan (parallel to quality check)
    security_task = await github_app.enqueue_task(
        run_security_scan,
        depends_on=[test_task.id]
    )
    
    # Step 4: Final approval (depends on both quality and security)
    await github_app.enqueue_task(
        approve_pr,
        depends_on=[quality_task.id, security_task.id]
    )
```

#### Bulk Operations and Batch Processing

```python
@github_app.on("repository.archived", background=True)
async def archive_repository_cleanup():
    """Clean up archived repository data in batches"""
    
    # Process in chunks to avoid memory issues
    async for batch in github_app.batch_processor(
        cleanup_archive_data,
        batch_size=100,
        max_concurrency=5
    ):
        await batch.execute()
```

### 4. Monitoring and Observability

#### Metrics Collection

```python
class TaskMetrics:
    """Collect and expose task execution metrics"""
    
    def __init__(self):
        self.task_counter = Counter()
        self.task_duration = Histogram()
        self.task_errors = Counter()
        self.queue_size = Gauge()
    
    def record_task_started(self, task_type: str):
        """Record task start"""
        self.task_counter.labels(task_type=task_type, status="started").inc()
    
    def record_task_completed(self, task_type: str, duration: float):
        """Record task completion"""
        self.task_counter.labels(task_type=task_type, status="completed").inc()
        self.task_duration.labels(task_type=task_type).observe(duration)
    
    def record_task_failed(self, task_type: str, error_type: str):
        """Record task failure"""
        self.task_counter.labels(task_type=task_type, status="failed").inc()
        self.task_errors.labels(task_type=task_type, error_type=error_type).inc()
```

#### Health Checks and Status Endpoints

```python
@app.get("/health/tasks")
async def task_queue_health():
    """Health check endpoint for task queue"""
    queue_stats = await github_app.task_manager.get_stats()
    return {
        "status": "healthy" if queue_stats.is_healthy else "unhealthy",
        "queue_size": queue_stats.pending_tasks,
        "active_workers": queue_stats.active_workers,
        "failed_tasks_24h": queue_stats.failed_tasks_count,
        "average_processing_time": queue_stats.avg_processing_time
    }

@app.get("/metrics/tasks")
async def task_metrics():
    """Prometheus-compatible metrics endpoint"""
    return github_app.task_manager.get_prometheus_metrics()
```

#### Distributed Tracing

```python
from opentelemetry import trace
from opentelemetry.ext.fastapi import FastAPIInstrumentor

# Instrument webhook processing with tracing
@github_app.on("issues.opened", background=True)
async def traced_issue_handler():
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("process_issue") as span:
        span.set_attribute("event.type", "issues.opened")
        span.set_attribute("repository", github_app.payload["repository"]["name"])
        
        # Process issue with full tracing
        await process_issue_with_tracing()
```

### 5. Scaling and Performance

#### Horizontal Scaling Support

```python
class DistributedTaskManager:
    """Task manager for distributed deployments"""
    
    def __init__(self, node_id: str, cluster_config: dict):
        self.node_id = node_id
        self.cluster_config = cluster_config
        self._coordinator = None
    
    async def join_cluster(self):
        """Join the worker cluster"""
        pass
    
    async def distribute_load(self):
        """Distribute tasks across cluster nodes"""
        pass
    
    async def handle_node_failure(self, failed_node: str):
        """Handle worker node failures"""
        pass
```

#### Auto-scaling Based on Queue Depth

```python
class AutoScaler:
    """Auto-scale workers based on queue metrics"""
    
    def __init__(self, min_workers: int, max_workers: int):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self._current_workers = min_workers
    
    async def scale_decision(self, queue_stats: QueueStats):
        """Decide whether to scale up or down"""
        if queue_stats.pending_tasks > self._current_workers * 10:
            await self.scale_up()
        elif queue_stats.pending_tasks < self._current_workers * 2:
            await self.scale_down()
    
    async def scale_up(self):
        """Add more workers"""
        if self._current_workers < self.max_workers:
            await self.add_worker()
            self._current_workers += 1
    
    async def scale_down(self):
        """Remove workers"""
        if self._current_workers > self.min_workers:
            await self.remove_worker()
            self._current_workers -= 1
```

### 6. Advanced Configuration (Conflict-Free)

#### Environment-Specific Configuration with Namespace Isolation

```python
# Production configuration - isolated from upstream project settings
GITHUBAPP_TASK_QUEUE_BACKEND = "redis"
GITHUBAPP_TASK_REDIS_URL = "redis://redis-cluster:6379/15"  # Isolated DB
GITHUBAPP_TASK_QUEUE_WORKERS = 16
GITHUBAPP_TASK_QUEUE_MEMORY_LIMIT = "2GB"
GITHUBAPP_TASK_QUEUE_PREFIX = "githubapp:prod:"  # Namespaced keys
GITHUBAPP_ENABLE_METRICS = True
GITHUBAPP_ENABLE_TRACING = True
GITHUBAPP_ENABLE_AUTO_SCALING = True

# Development configuration - safe defaults
GITHUBAPP_TASK_QUEUE_BACKEND = "asyncio"  # No external dependencies
GITHUBAPP_TASK_QUEUE_WORKERS = 2
GITHUBAPP_ENABLE_METRICS = False
GITHUBAPP_LOG_LEVEL = "DEBUG"

# Test configuration - deterministic behavior
GITHUBAPP_TASK_QUEUE_BACKEND = "memory"
GITHUBAPP_TASK_QUEUE_WORKERS = 1
GITHUBAPP_TASK_EXECUTION_MODE = "synchronous"  # For testing
```

#### Safe Installation Options

```bash
# Minimal installation (zero external dependencies)
pip install fastapi-githubapp

# Redis support only
pip install fastapi-githubapp[redis]

# Celery support (includes Redis)
pip install fastapi-githubapp[celery]

# Database queue support
pip install fastapi-githubapp[database]

# All backends (production-ready)
pip install fastapi-githubapp[all-queues]

# Development with all optional features
pip install fastapi-githubapp[all-queues,dev]
```

#### Graceful Degradation Configuration

```python
class GitHubApp:
    def __init__(self, app, task_queue_backend="asyncio", **config):
        """Initialize with safe fallback behavior"""
        
        try:
            # Attempt to create requested backend
            self.task_manager = TaskQueueFactory.create_queue(
                task_queue_backend, 
                **config.get("task_queue_config", {})
            )
            self._task_backend_type = task_queue_backend
            
        except (ImportError, ValueError) as e:
            # Log warning but don't fail - fallback to asyncio
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Could not initialize '{task_queue_backend}' backend: {e}. "
                f"Falling back to 'asyncio' backend. "
                f"To enable {task_queue_backend}: pip install fastapi-githubapp[{task_queue_backend}]"
            )
            
            # Safe fallback to built-in asyncio backend
            self.task_manager = TaskQueueFactory.create_queue("asyncio")
            self._task_backend_type = "asyncio"
    
    def get_backend_info(self) -> dict:
        """Get information about current backend for diagnostics"""
        available_backends = TaskQueueFactory.get_available_backends()
        return {
            "current_backend": self._task_backend_type,
            "available_backends": available_backends,
            "installed_extras": self._get_installed_extras(),
            "recommendations": self._get_backend_recommendations()
        }
    
    def _get_installed_extras(self) -> list:
        """Detect which optional extras are installed"""
        extras = []
        if "redis" in TaskQueueFactory.get_available_backends():
            extras.append("redis")
        if "celery" in TaskQueueFactory.get_available_backends():
            extras.append("celery")
        if "database" in TaskQueueFactory.get_available_backends():
            extras.append("database")
        return extras
```

### 7. Security and Reliability

#### Task Authentication and Authorization

```python
class SecureTaskExecutor:
    """Execute tasks with proper authentication context"""
    
    async def execute_with_context(self, task: Task, auth_context: AuthContext):
        """Execute task with preserved auth context"""
        # Validate task permissions
        if not await self.validate_task_permissions(task, auth_context):
            raise UnauthorizedTaskError()
        
        # Execute with limited permissions
        async with self.create_sandbox(auth_context) as sandbox:
            return await sandbox.execute(task)
```

#### Encrypted Task Payloads

```python
class EncryptedTaskQueue(TaskQueueBackend):
    """Task queue with encrypted payloads"""
    
    def __init__(self, base_queue: TaskQueueBackend, encryption_key: bytes):
        self.base_queue = base_queue
        self.cipher = Fernet(encryption_key)
    
    async def enqueue(self, task: Task) -> str:
        """Encrypt task payload before enqueuing"""
        encrypted_payload = self.cipher.encrypt(task.payload.encode())
        encrypted_task = task.copy(payload=encrypted_payload)
        return await self.base_queue.enqueue(encrypted_task)
```

### 8. Testing and Validation

#### Load Testing Framework

```python
class TaskQueueLoadTester:
    """Load testing framework for task queues"""
    
    async def simulate_webhook_load(
        self,
        events_per_second: int,
        duration_seconds: int,
        event_types: List[str]
    ):
        """Simulate high webhook load"""
        pass
    
    async def measure_performance(self) -> LoadTestResults:
        """Measure task queue performance under load"""
        pass
```

#### Integration Testing

```python
@pytest.mark.integration
async def test_full_workflow_with_redis():
    """Test complete workflow with Redis backend"""
    # Setup Redis test instance
    async with RedisTestContainer() as redis:
        github_app = GitHubApp(
            task_queue_backend="redis",
            task_queue_config={"redis_url": redis.url}
        )
        
        # Send webhook and verify background processing
        response = await test_client.post("/webhook", json=webhook_payload)
        assert response.status_code == 200
        
        # Wait for background task completion
        task_id = response.json()["task_id"]
        await wait_for_task_completion(task_id, timeout=30)
        
        # Verify task results
        result = await github_app.get_task_result(task_id)
        assert result.status == "completed"
```

## Migration and Deployment

### Production Deployment Checklist

- [ ] Choose appropriate task queue backend for scale
- [ ] Configure monitoring and alerting
- [ ] Set up distributed tracing
- [ ] Implement backup and recovery procedures
- [ ] Configure auto-scaling policies
- [ ] Set up security scanning for task payloads
- [ ] Implement circuit breakers for external services
- [ ] Configure rate limiting and throttling

### Monitoring Dashboard

```python
# Grafana dashboard configuration for task queues
DASHBOARD_METRICS = [
    "task_queue_size",
    "task_processing_rate",
    "task_failure_rate", 
    "worker_utilization",
    "average_task_duration",
    "queue_backend_health",
    "memory_usage",
    "error_rate_by_type"
]
```

## Success Criteria

- [ ] Multiple task queue backends supported and tested
- [ ] Production-ready monitoring and observability
- [ ] Horizontal scaling capabilities implemented
- [ ] Security features for sensitive task data
- [ ] Comprehensive performance testing completed
- [ ] Migration guides and deployment documentation
- [ ] Full integration test suite passing
- [ ] Performance benchmarks meeting targets
- [ ] Documentation and examples for all backends

## Performance Targets

- **Webhook Response Time**: < 200ms for immediate acknowledgment
- **Task Throughput**: > 1000 tasks/minute per worker
- **Queue Latency**: < 5 seconds from enqueue to execution start
- **Memory Usage**: < 100MB per worker process
- **Error Rate**: < 0.1% for task execution
- **Recovery Time**: < 30 seconds for worker restart

## Documentation Deliverables

1. **Task Queue Backend Comparison Guide**
2. **Production Deployment Guide**
3. **Monitoring and Alerting Setup**
4. **Performance Tuning Guide**
5. **Security Best Practices**
6. **Troubleshooting Guide**
7. **API Reference for All New Features**

This completes the four-phase implementation plan for adding native async support with task queue capabilities to your FastAPI-GitHubApp library while avoiding antipatterns and maintaining backward compatibility.
