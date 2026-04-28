---
name: python-patterns
description: Use this skill whenever you write Python code and want to follow production-grade idioms — including async patterns, dataclass design, dependency injection, configuration management, retry logic, and structural anti-patterns to avoid. Trigger for: Python code review, architecture design, async Python, FastAPI, Pydantic, Python data pipelines, API clients, background workers. Widely applicable to any Python project.
---

# Python Patterns — Production-Grade Idioms

## Configuration Management

Always use Pydantic Settings. It validates at startup, gives clear error messages, and supports `.env` files without boilerplate.

```python
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from functools import lru_cache

class Settings(BaseSettings):
    # Required (no default — fails fast if missing)
    qdrant_url: str
    qdrant_api_key: str
    gemini_api_key: str
    
    # Optional with defaults
    qdrant_collection: str = "documents"
    max_retrieval_candidates: int = 50
    rerank_top_k: int = 5
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    log_level: str = "INFO"
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # QDRANT_URL matches qdrant_url


@lru_cache  # Singleton — create once, reuse
def get_settings() -> Settings:
    return Settings()
```

## Dependency Injection

Pass dependencies as parameters, don't import them as globals. This makes testing trivial.

```python
# ❌ Global dependency — impossible to mock in tests
from myapp.clients import qdrant_client, gemini_model

async def retrieve(query: str) -> list[dict]:
    return qdrant_client.search(query)

# ✅ Injected dependency — trivially mockable
async def retrieve(
    query: str,
    qdrant: QdrantClient,
    embedder: EmbeddingModel,
) -> list[dict]:
    vector = embedder.embed(query)
    return qdrant.search(collection="docs", query_vector=vector)

# In tests:
result = await retrieve("CDI treatment", mock_qdrant, mock_embedder)
```

## Dataclasses vs Pydantic vs TypedDict

| Use | When |
|-----|------|
| `@dataclass` | Simple data containers, no validation needed |
| `pydantic.BaseModel` | Input validation, serialisation, API schemas |
| `TypedDict` | Type hints for dicts you don't control (API responses) |
| `NamedTuple` | Immutable, lightweight, ordered tuples |

```python
# Configuration and validated input: Pydantic
class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(10, ge=1, le=100)
    specialty: Optional[str] = None

# Internal data transfer: dataclass
@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float
    pub_year: Optional[int] = None
    metadata: dict = field(default_factory=dict)

# External API response typing: TypedDict
class PubMedArticle(TypedDict):
    pmid: str
    title: str
    abstract: str
    authors: list[str]
```

## Retry with Exponential Backoff

Use `tenacity` — it's the standard. Never write your own retry loop.

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
import logging

log = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> dict:
    """Retries on transient network errors with exponential backoff."""
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()
```

## Async Patterns

```python
# ✅ Parallel execution where order doesn't matter
async def gather_evidence(query: str, clients: ClientBundle) -> list[dict]:
    results = await asyncio.gather(
        search_qdrant(clients.qdrant, query),
        search_pubmed(clients.ncbi, query),
        search_tavily(clients.tavily, query),
        return_exceptions=True,  # Don't cancel others if one fails
    )
    
    all_chunks = []
    for result in results:
        if isinstance(result, Exception):
            log.warning("Retrieval source failed: %s", result)
        else:
            all_chunks.extend(result)
    
    return all_chunks

# ✅ Sequential execution with proper async context managers
async def process_batch(items: list[str]) -> list[dict]:
    async with httpx.AsyncClient() as client:  # Single client, reused
        return [await process_one(client, item) for item in items]

# ✅ Async generator for streaming large datasets
async def stream_qdrant_collection(client: QdrantClient, collection: str):
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        for point in points:
            yield point
        if offset is None:
            break
```

## Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Structured JSON logging for GCP Cloud Logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        # Include extra fields passed via log.info("msg", extra={"query_id": "..."})
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                log_entry[key] = value
        return json.dumps(log_entry)

def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=getattr(logging, level), handlers=[handler])

# Usage
log = logging.getLogger(__name__)
log.info("Query processed", extra={"query_id": "abc123", "latency_ms": 342})
```

## Context Managers for Resources

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_qdrant_client(settings: Settings):
    """Manages Qdrant client lifecycle."""
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=30,
    )
    try:
        yield client
    finally:
        # Qdrant client doesn't need explicit close but pattern is correct
        pass

# Usage
async def main():
    async with get_qdrant_client(get_settings()) as qdrant:
        results = await search(qdrant, "CDI treatment")
```

## Anti-Patterns to Avoid

```python
# ❌ Mutable default arguments
def process(items=[]):  # Shared across calls — famous Python footgun
    items.append("x")
    return items

# ✅ Use None sentinel
def process(items=None):
    if items is None:
        items = []
    items.append("x")
    return items

# ❌ Star imports
from typing import *  # Pollutes namespace, hides where things come from

# ✅ Explicit imports
from typing import Optional, Union, Any

# ❌ Catching broad exceptions silently
try:
    do_something()
except Exception:
    pass  # The worst line in Python

# ✅ Specific exception, logged
try:
    do_something()
except SpecificError as e:
    log.error("Operation failed: %s", e)
    raise  # Re-raise to preserve stack trace

# ❌ String concatenation in loops
result = ""
for item in items:
    result += item  # O(n²) — creates new string each iteration

# ✅ join
result = "".join(items)
```
