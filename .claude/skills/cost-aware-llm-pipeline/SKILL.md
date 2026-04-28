---
name: cost-aware-llm-pipeline
description: Use this skill when building or optimizing LLM pipelines where cost matters — including model selection by query complexity, token count optimization, prompt compression, response caching, budget tracking per query, and cost projection. Also trigger for: Gemini pricing, LLM routing logic, context window management, prompt engineering for cost reduction, token budgeting, cost-per-query calculation. Applies to any project using LLM APIs at scale.
---

# Cost-Aware LLM Pipeline

LLM API costs are the primary variable expense in AI products at scale. A 1,000 DAU system that doesn't manage costs correctly can easily spend $5,000/month on what should be a $150/month operation.

## Pricing Reference (April 2026)

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Best For |
|-------|----------------------|------------------------|----------|
| Gemini 2.5 Flash | $0.30 | $2.50 | Most queries — fast, cheap, accurate |
| Gemini 2.5 Pro | $1.25 | $10.00 | Complex multi-study synthesis |
| Claude Sonnet 4.5 | $3.00 | $15.00 | Highest accuracy tasks |
| GPT-4o | $2.50 | $10.00 | Alternative to Pro |
| GPT-4o-mini | $0.15 | $0.60 | Simple classification |

**Key insight:** Gemini 2.5 Flash costs 1/4 of Pro for ~90% of the accuracy. Route 95% of queries to Flash.

---

## Query Complexity Routing

```python
from enum import Enum
from dataclasses import dataclass

class QueryComplexity(str, Enum):
    SIMPLE = "simple"       # Drug lookup, single-source answer
    STANDARD = "standard"   # Single condition, multi-source
    COMPLEX = "complex"     # Comparative, multi-trial synthesis

@dataclass
class ModelConfig:
    model_name: str
    max_input_tokens: int
    cost_per_1m_input: float
    cost_per_1m_output: float

MODEL_CONFIGS = {
    QueryComplexity.SIMPLE: ModelConfig(
        model_name="gemini-2.0-flash-lite",  # Even cheaper for simple
        max_input_tokens=32_000,
        cost_per_1m_input=0.075,
        cost_per_1m_output=0.30,
    ),
    QueryComplexity.STANDARD: ModelConfig(
        model_name="gemini-2.5-flash",
        max_input_tokens=1_000_000,
        cost_per_1m_input=0.30,
        cost_per_1m_output=2.50,
    ),
    QueryComplexity.COMPLEX: ModelConfig(
        model_name="gemini-2.5-pro",
        max_input_tokens=1_000_000,
        cost_per_1m_input=1.25,
        cost_per_1m_output=10.00,
    ),
}

def classify_complexity(query: str, num_sources: int) -> QueryComplexity:
    """
    Route to cheapest model that can handle the query.
    """
    # Comparative questions need Pro
    comparative_signals = [
        "vs", "versus", "compare", "difference between",
        "better than", "prefer", "choose between",
    ]
    if any(s in query.lower() for s in comparative_signals) and num_sources > 5:
        return QueryComplexity.COMPLEX
    
    # Simple lookups need Flash Lite
    simple_signals = [
        "what is", "dose of", "side effects of", "generic name",
        "brand name", "price of",
    ]
    if any(s in query.lower() for s in simple_signals):
        return QueryComplexity.SIMPLE
    
    return QueryComplexity.STANDARD
```

---

## Token Budget Management

```python
import tiktoken

# Approximate token counts for different content
TOKEN_ESTIMATES = {
    "system_prompt": 400,     # Fixed cost per query
    "per_chunk_512_tokens": 512,
    "overhead_per_query": 100,
    "target_response_tokens": 800,
}

def calculate_context_tokens(
    system_prompt: str,
    chunks: list[str],
    query: str,
) -> int:
    """Estimate token count before calling LLM."""
    # tiktoken for OpenAI models; rough estimate for Gemini (1 token ≈ 4 chars)
    total_chars = len(system_prompt) + len(query) + sum(len(c) for c in chunks)
    return total_chars // 4  # Rough approximation


def select_chunks_within_budget(
    chunks: list[dict],
    max_input_tokens: int,
    system_prompt_tokens: int,
    query_tokens: int,
    target_response_tokens: int = 800,
) -> list[dict]:
    """
    Select as many top-ranked chunks as fit within the token budget.
    Never truncate a chunk — drop the whole chunk if it doesn't fit.
    """
    available = max_input_tokens - system_prompt_tokens - query_tokens - target_response_tokens - 200  # buffer
    
    selected = []
    used = 0
    
    for chunk in chunks:
        chunk_tokens = len(chunk["content"]) // 4
        if used + chunk_tokens <= available:
            selected.append(chunk)
            used += chunk_tokens
        # Don't break — skip this chunk but try smaller ones
    
    return selected[:10]  # Cap at 10 chunks regardless
```

---

## Response Caching

```python
import hashlib
import json
import redis.asyncio as redis

class LLMResponseCache:
    """
    Cache LLM responses with 12-hour TTL.
    Medical evidence doesn't change hourly — reuse expensive generations.
    """
    
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 43200):
        self.redis = redis_client
        self.ttl = ttl_seconds
    
    def _cache_key(self, query: str, context_hash: str) -> str:
        """
        Key is based on BOTH the query and the retrieved context.
        Same query with different chunks = different response = different cache entry.
        """
        combined = f"{query.lower().strip()}:{context_hash}"
        return f"llm:v1:{hashlib.sha256(combined.encode()).hexdigest()[:24]}"
    
    def _hash_context(self, chunks: list[dict]) -> str:
        """Stable hash of retrieved chunks."""
        content = json.dumps(
            [{"content": c["content"], "source": c.get("source", "")} for c in chunks],
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def get(self, query: str, chunks: list[dict]) -> dict | None:
        ctx_hash = self._hash_context(chunks)
        key = self._cache_key(query, ctx_hash)
        
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            log.warning("Cache read failed: %s", e)
        return None
    
    async def set(self, query: str, chunks: list[dict], response: dict) -> None:
        ctx_hash = self._hash_context(chunks)
        key = self._cache_key(query, ctx_hash)
        
        try:
            await self.redis.setex(key, self.ttl, json.dumps(response))
        except Exception as e:
            log.warning("Cache write failed: %s", e)
```

---

## Cost Tracking Per Query

```python
@dataclass
class QueryCost:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    cache_hit: bool = False

def calculate_cost(
    model_config: ModelConfig,
    input_tokens: int,
    output_tokens: int,
    cache_hit: bool = False,
) -> QueryCost:
    if cache_hit:
        return QueryCost(
            model=model_config.model_name,
            input_tokens=0, output_tokens=0,
            input_cost_usd=0, output_cost_usd=0,
            total_cost_usd=0, cache_hit=True,
        )
    
    input_cost = (input_tokens / 1_000_000) * model_config.cost_per_1m_input
    output_cost = (output_tokens / 1_000_000) * model_config.cost_per_1m_output
    
    return QueryCost(
        model=model_config.model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
    )

# Cost projection
def project_monthly_cost(
    daily_active_users: int,
    queries_per_user_per_day: float,
    avg_cost_per_query: float,
) -> float:
    daily_queries = daily_active_users * queries_per_user_per_day
    daily_cost = daily_queries * avg_cost_per_query
    return daily_cost * 30
```

---

## Budget Guard: Cost Targets

At 1,000 DAUs with 3 queries/user/day:

| Component | Target Cost | How to Hit It |
|---|---|---|
| LLM Generation | ~$50-90/month | 95% Flash, 5% Pro; 12h cache |
| Cohere Rerank | ~$60/month | Batch 50 docs per call; cache results |
| BGE-M3 Embedding | ~$20/month | T4 spot instance; embed once, search many |
| PubMed E-utilities | $0 | Free with API key |
| Tavily | ~$35/month | Basic tier; call only on cache miss |
| Qdrant Cloud | $0 | Free tier at <500K chunks |
| Cloud Run | ~$20/month | Scale-to-zero; no idle cost |
| **Total** | **~$185-225/month** | |

---

## What Not to Do

```python
# ❌ Using Pro for all queries — 4x cost for 5% accuracy gain
model = "gemini-2.5-pro"  # For every single drug lookup query

# ❌ No caching — same questions asked 100 times, paid 100 times
# Indian doctors ask "fidaxomicin vs vancomycin" every day

# ❌ Feeding all retrieved chunks into context
# 20 chunks × 512 tokens = 10,240 tokens of input cost, "lost in middle" degrades quality

# ❌ Not tracking costs — can't optimize what you don't measure

# ❌ Calling Tavily for every query — it's the most expensive real-time source
# Use Qdrant first; Tavily only when Qdrant returns < 3 results
```
