# Python-Specific Rules

## Formatting: Black + Ruff (non-negotiable)

```bash
black .          # Opinionated formatter — no style debates
ruff check .     # Linting (replaces flake8, isort, pylint)
ruff format .    # Faster alternative to black
```

Configure once, never argue about formatting again.

## Type Hints: Mandatory on Public Functions

```python
# ❌ No type hints — ambiguous interface
def search(query, limit=10):

# ✅ Full type hints — self-documenting interface
async def search(
    query: str,
    limit: int = 10,
    specialty: Optional[str] = None,
) -> list[dict[str, Any]]:
```

Run `mypy --strict` on all new modules. Existing modules: add types incrementally.

## Import Order (enforced by ruff)

```python
# Standard library
import os
import re
from typing import Optional

# Third-party
import httpx
from pydantic import BaseModel

# Internal
from noocyte.core.query_router import QueryRouter
from noocyte.utils.logging import get_logger
```

## Async: Required for I/O-Bound Work

Any function that calls: database, HTTP API, file system (at scale), message queue — must be `async`.

```python
# ❌ Blocks the event loop — kills concurrency for all other requests
def fetch_pubmed(query: str) -> list[dict]:
    return requests.get(pubmed_url).json()

# ✅ Yields control while waiting for I/O
async def fetch_pubmed(query: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(pubmed_url, timeout=10.0)
        return response.json()
```

## Environment Variables: Pydantic Settings Always

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    qdrant_url: str
    gemini_api_key: str
    ncbi_api_key: str
    
    class Config:
        env_file = ".env"

settings = Settings()  # Fails loudly at startup if any required var is missing
```

Never `os.environ.get("KEY")` without a default — it returns `None` silently.

## Logging: Module-Level, No Print

```python
import logging
log = logging.getLogger(__name__)  # Module-level — configure once at startup

log.debug("Processing %d chunks", len(chunks))  # Not f-string — lazy evaluation
log.info("Query processed", extra={"query_id": qid, "latency_ms": latency})
log.warning("Cohere timeout, falling back to Qdrant scores")
log.error("DOI validation failed for %s: %s", doi, error)
```

## Python Version Target: 3.11+

Use modern syntax:
```python
# 3.10+: Structural pattern matching
match query_type:
    case "drug_lookup": route_to_drug_db()
    case "guideline": route_to_qdrant()
    case _: route_to_pubmed()

# 3.10+: X | Y union type
def process(query: str | None) -> list[dict] | None: ...

# 3.11+: Exception groups for concurrent errors
try:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(search_qdrant(query))
        t2 = tg.create_task(search_pubmed(query))
except* httpx.TimeoutException as eg:
    log.warning("Some retrievals timed out: %s", eg.exceptions)
```
