---
name: api-design
description: >-
  Use this skill when designing or reviewing REST APIs — including endpoint naming, request/response schemas, error formats, pagination, versioning, status codes, and authentication patterns. Also trigger for: FastAPI design, webhook design, API documentation, OpenAPI/Swagger, rate limit headers, idempotency. Applies to any language or framework.
---

# API Design — Production REST Patterns

Good API design is invisible — consumers don't notice it because everything just works. Bad API design creates support tickets, client bugs, and migration pain that lasts years.

## The Prime Directive

**Design for the caller, not the implementer.** The implementation can change. The public API cannot (without breaking callers). Every design decision must be evaluated from the caller's perspective.

---

## URL Design

### Resource Naming
```
# ❌ Verbs in URLs — actions belong in HTTP methods
GET /api/getQuery
POST /api/createQuery
POST /api/deleteQuery

# ✅ Nouns for resources, HTTP methods for actions
GET    /api/queries              # List queries
POST   /api/queries              # Create query
GET    /api/queries/{id}         # Get specific query
PATCH  /api/queries/{id}         # Update specific query
DELETE /api/queries/{id}         # Delete specific query

# ✅ Nested resources for ownership
GET /api/doctors/{id}/queries    # All queries for a specific doctor
GET /api/queries/{id}/citations  # Citations for a specific query response
```

### Versioning
```
# ✅ Version in URL path (most common, most explicit)
GET /api/v1/queries
GET /api/v2/queries

# ✅ Alternative: version in header
Accept: application/vnd.noocyte.v2+json

# Rule: Never break v1 without a deprecation period and migration guide
# Rule: Keep at most 2 major versions active simultaneously
```

---

## Request Design

### Validation with Pydantic (FastAPI)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from enum import Enum

class Specialty(str, Enum):
    cardiology = "cardiology"
    oncology = "oncology"
    nephrology = "nephrology"
    general = "general"

class QueryRequest(BaseModel):
    query: str = Field(
        ...,  # Required
        min_length=5,
        max_length=500,
        description="The clinical question to search evidence for",
        example="What is the first-line treatment for CDI in adults?",
    )
    specialty: Optional[Specialty] = Field(
        None,
        description="Route to specialty-specific sources",
    )
    max_results: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of evidence chunks to return",
    )
    
    @validator("query")
    def query_must_not_be_only_whitespace(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be only whitespace")
        return v.strip()

    class Config:
        # Reject extra fields — prevents silent field name typos
        extra = "forbid"
```

---

## Response Design

### Consistent Success Envelope

All responses use the same shape so clients can be generic:

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Optional[dict] = None  # Pagination, query info, etc.

class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail

class ErrorDetail(BaseModel):
    code: str           # Machine-readable: "RATE_LIMIT_EXCEEDED"
    message: str        # Human-readable: "You've exceeded 60 queries per hour"
    field: Optional[str] = None  # For validation errors: "query"
    docs: Optional[str] = None   # Link to documentation

# Usage
@app.post("/api/v1/queries")
async def create_query(request: QueryRequest) -> ApiResponse[QueryResponse]:
    result = await process_query(request)
    return ApiResponse(data=result, meta={"latency_ms": result.latency_ms})
```

### Status Codes — Use Them Correctly

```
200 OK            — GET, PATCH success; resource returned
201 Created       — POST success; new resource created
204 No Content    — DELETE success; nothing to return
400 Bad Request   — Client validation error (missing field, wrong type)
401 Unauthorized  — No/invalid auth token
403 Forbidden     — Valid auth, but not allowed to access this resource
404 Not Found     — Resource doesn't exist
409 Conflict      — Duplicate resource (idempotency key already used)
422 Unprocessable — Request is valid JSON/schema but semantically invalid
429 Too Many      — Rate limit exceeded; include Retry-After header
500 Server Error  — Internal error (log it, don't expose details)
503 Unavailable   — Dependency down; include Retry-After if known
```

### Error Response Examples

```python
# 400 Validation Error
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Query must be between 5 and 500 characters",
        "field": "query"
    }
}

# 429 Rate Limit
{
    "success": false,
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "You have exceeded 60 queries per hour",
        "docs": "https://docs.noocyte.ai/rate-limits"
    }
}
# Also include headers:
# Retry-After: 1847  (seconds until reset)
# X-RateLimit-Limit: 60
# X-RateLimit-Remaining: 0
# X-RateLimit-Reset: 1735689600

# 500 Internal Error
{
    "success": false,
    "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred. Request ID: req_abc123",
        "request_id": "req_abc123"  # For support tickets
    }
}
# Never expose: stack traces, internal paths, database schema, SQL queries
```

---

## Pagination

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    next_cursor: Optional[str] = None  # Cursor-based pagination for large datasets

# Cursor-based pagination (preferred for large, frequently updated datasets)
# Why: Offset pagination breaks when items are added/removed between pages
@app.get("/api/v1/queries")
async def list_queries(
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    doctor_id: str = Depends(get_current_doctor),
) -> PaginatedResponse[QuerySummary]:
    results = await db.query_after_cursor(
        owner_id=doctor_id,
        cursor=cursor,
        limit=limit + 1,  # Fetch one extra to know if there's a next page
    )
    
    has_more = len(results) > limit
    items = results[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more else None
    
    return PaginatedResponse(
        items=items,
        total=await db.count_queries(owner_id=doctor_id),
        page_size=limit,
        next_cursor=next_cursor,
    )
```

---

## Webhook Design

```python
# Webhook delivery best practices:

# 1. Idempotency: include a unique event ID so receivers can deduplicate
{
    "event_id": "evt_01HQXYZ",      # Unique, stable across retries
    "event_type": "query.completed",
    "created_at": "2025-01-15T10:30:00Z",
    "data": { ... }
}

# 2. Sign the payload so receivers can verify authenticity
X-Noocyte-Signature: sha256=abc123...

# 3. Retry with exponential backoff on non-2xx responses
# 4. Include event ordering if consumers need to process in sequence
# 5. Document the retry schedule and delivery guarantees
```

---

## FastAPI Complete Example

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import time

app = FastAPI(
    title="Noocyte API",
    version="1.0.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.noocyte.ai"],  # Not "*" in production
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to every response for support tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.post(
    "/api/v1/queries",
    response_model=ApiResponse[QueryResponse],
    status_code=200,
    summary="Submit a clinical evidence query",
    response_description="Evidence-based answer with citations",
)
async def submit_query(
    request: QueryRequest,
    doctor: Doctor = Depends(get_current_doctor),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    allowed, reason = await rate_limiter.check(doctor.phone_hash)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    result = await process_query(request, doctor)
    return ApiResponse(data=result)
```
