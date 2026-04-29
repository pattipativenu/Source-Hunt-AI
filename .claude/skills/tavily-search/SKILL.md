---
name: tavily-search
description: >-
  Use this skill whenever you need to integrate Tavily API for real-time web search, retrieve recent articles not yet indexed in databases, find cutting-edge research published in the last 30-90 days, supplement PubMed results with current web content, or build hybrid retrieval pipelines that combine vector search with live web retrieval. Trigger on: Tavily integration, live web search in RAG, recent publications not in PubMed, breaking research, web content retrieval, real-time document fetching.
---

# Tavily Search Integration

Tavily is a search API built specifically for AI agents. Unlike Google Search (designed for humans) or Qdrant (searches your private corpus), Tavily searches the live web and returns clean, AI-ready content — no HTML parsing, no JavaScript rendering, no paywall handling.

## When to Use Tavily vs. Other Sources

| Source | Use When |
|--------|----------|
| Qdrant (vector DB) | Searching pre-indexed corpus (ICMR guidelines, drug DB) |
| PubMed E-utilities | Searching biomedical literature with MeSH precision |
| PMC BioC API | Fetching full-text of open access articles |
| **Tavily** | Recent publications (<90 days), breaking research, trial results announced at conferences but not yet in PubMed, journal website summaries of paywalled articles |

**Key insight:** PubMed indexing lags 7-30 days behind publication. For queries about very recent evidence (2025 trials, newly updated guidelines), Tavily finds what PubMed hasn't indexed yet.

---

## Setup

```python
# Install
pip install tavily-python

# Environment
TAVILY_API_KEY=tvly-...  # Get from https://tavily.com
```

---

## Core Usage Patterns

### Pattern 1: Basic Medical Search

```python
from tavily import TavilyClient
import os

client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def search_recent_evidence(query: str, max_results: int = 5) -> list[dict]:
    """
    Search for recent medical evidence not yet in PubMed.
    
    Returns list of {url, title, content, score, published_date}
    """
    response = client.search(
        query=query,
        search_depth="advanced",    # "basic" is faster but shallower
        max_results=max_results,
        include_answer=False,        # We do our own synthesis, skip Tavily's
        include_raw_content=False,   # Clean content is enough
        include_domains=[            # Only trusted medical sources
            "nejm.org",
            "thelancet.com",
            "jamanetwork.com",
            "bmj.com",
            "acc.org",
            "heart.org",
            "idsociety.org",
            "ascopost.com",
            "medscape.com",
            "nih.gov",
            "pubmed.ncbi.nlm.nih.gov",
        ],
        # exclude_domains=["wikipedia.org", "webmd.com"]  # Alternative: exclusion list
    )
    
    return [
        {
            "url": r["url"],
            "title": r["title"],
            "content": r["content"][:1500],  # Truncate for embedding
            "score": r["score"],
            "published_date": r.get("published_date"),
        }
        for r in response.get("results", [])
        if r.get("score", 0) > 0.5  # Filter low-relevance results
    ]
```

### Pattern 2: Fetch Full Article Content

When Tavily finds an article but the content is truncated, use `extract` to get the full text:

```python
async def fetch_article_content(url: str) -> str:
    """
    Fetch full article content from a URL.
    Better than BeautifulSoup — handles paywalls, JS rendering, and clean extraction.
    """
    try:
        response = client.extract(urls=[url])
        results = response.get("results", [])
        if results:
            return results[0].get("raw_content", "")
        return ""
    except Exception as e:
        log.warning("Tavily extract failed for %s: %s", url, e)
        return ""
```

### Pattern 3: Time-Windowed Search for Breaking Research

```python
from datetime import datetime, timedelta

def search_recent_trials(condition: str, days: int = 90) -> list[dict]:
    """
    Find phase 3 trial results published in the last N days.
    Critical for staying current when PubMed indexing lags.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Tavily doesn't have native date filter, so we use query augmentation
    query = f"{condition} clinical trial results 2025 phase 3 randomized"
    
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=10,
        include_domains=[
            "nejm.org", "thelancet.com", "ascopost.com",
            "medpagetoday.com", "healio.com", "ajmc.com",
        ],
    )
    
    # Post-filter by date if published_date is available
    results = response.get("results", [])
    recent = [
        r for r in results
        if not r.get("published_date") or r["published_date"] >= cutoff
    ]
    
    return recent
```

### Pattern 4: Hybrid Retrieval (Tavily + Qdrant)

This is the recommended pattern for RAG pipelines that need both depth (pre-indexed corpus) and recency (live web):

```python
import asyncio

async def hybrid_retrieve(
    query: str,
    qdrant_client,
    tavily_client: TavilyClient,
    top_k: int = 5,
) -> list[dict]:
    """
    Parallel retrieval from Qdrant (pre-indexed) and Tavily (live web).
    Merges and deduplicates results.
    """
    # Run both retrievals in parallel
    qdrant_results, tavily_results = await asyncio.gather(
        search_qdrant(qdrant_client, query, limit=20),
        asyncio.to_thread(  # Tavily is sync, wrap for async
            tavily_client.search,
            query=query,
            search_depth="advanced",
            max_results=5,
        ),
        return_exceptions=True,
    )
    
    chunks = []
    
    # Process Qdrant results
    if not isinstance(qdrant_results, Exception):
        chunks.extend([
            {
                "content": r.payload["content"],
                "source": r.payload.get("source", "ICMR"),
                "pub_year": r.payload.get("pub_year", 2024),
                "score": r.score,
                "source_type": "indexed",
            }
            for r in qdrant_results
        ])
    
    # Process Tavily results
    if not isinstance(tavily_results, Exception):
        for r in tavily_results.get("results", []):
            if r.get("score", 0) > 0.5:
                chunks.append({
                    "content": r["content"][:1500],
                    "source": r["url"],
                    "pub_year": 2025,  # Assumed recent
                    "score": r["score"] * 0.9,  # Slight penalty vs indexed
                    "source_type": "live_web",
                })
    
    # Sort by score, dedup by content similarity
    chunks.sort(key=lambda x: x["score"], reverse=True)
    return chunks[:top_k]
```

---

## Rate Limits and Cost Management

```
Free tier: 1,000 requests/month
Basic: $35/month — 10,000 requests
Professional: $100/month — 50,000 requests
```

**Cost optimization strategies:**

1. **Cache aggressively:** Tavily results are expensive per-call. Cache for 24 hours for stable queries:
```python
cache_key = f"tavily:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
cached = redis.get(cache_key)
if cached:
    return json.loads(cached)

results = client.search(query=query, ...)
redis.setex(cache_key, 86400, json.dumps(results))  # 24h cache
```

2. **Only call when PubMed insufficient:** Use Tavily as a fallback, not a primary:
```python
pubmed_results = await search_pubmed(query)
if len(pubmed_results) < 3 or all_results_older_than_6_months(pubmed_results):
    tavily_results = search_tavily(query)
```

3. **Use `basic` depth for simple queries:** `search_depth="advanced"` costs 2x more API credit.

---

## Domain Allowlist for Medical Search

Always use `include_domains` to restrict to trusted sources. The full allowlist for medical evidence:

```python
MEDICAL_TRUSTED_DOMAINS = [
    # General flagship journals
    "nejm.org", "thelancet.com", "jamanetwork.com", "bmj.com",
    # Specialty societies
    "acc.org", "heart.org", "escardio.org",
    "idsociety.org", "idsa.org",
    "diabetes.org", "kdigo.org",
    "thoracic.org", "ginasthma.org",
    "nccn.org", "asco.org", "esmo.org",
    "gastro.org", "rheumatology.org",
    # News and summaries (secondary, lower weight)
    "ascopost.com", "medpagetoday.com", "healio.com",
    "mdedge.com", "medscape.com",
    # Government/institutional
    "nih.gov", "cdc.gov", "who.int",
    "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    # Indian sources
    "icmr.gov.in", "mohfw.gov.in", "cdsco.gov.in",
]
```

---

## What NOT to Do

```python
# ❌ No domain restrictions — retrieves Wikipedia, Reddit, random blogs
client.search(query="fidaxomicin CDI treatment")

# ❌ include_answer=True — Tavily's answer synthesis is not medically verified
# Use your own LLM synthesis with verified citations instead
response = client.search(query=query, include_answer=True)
answer = response["answer"]  # Don't trust this for medical use

# ❌ No score threshold — returns irrelevant results
results = response["results"]  # All results, including score=0.1

# ❌ No caching — burns API budget on repeated identical queries
for query in same_queries_100_times:
    client.search(query=query)  # 100 API calls instead of 1

# ❌ Blocking call in async context without to_thread wrapper
async def get_results():
    return client.search(query=query)  # Blocks event loop
```

---

## Testing Tavily Integration

```python
# Mock for unit tests — never call real API in tests
from unittest.mock import patch, MagicMock

def test_recent_search_returns_filtered_results():
    mock_response = {
        "results": [
            {"url": "https://nejm.org/test", "title": "Test", 
             "content": "Sample content", "score": 0.9, "published_date": "2025-01-15"},
            {"url": "https://blog.example.com", "title": "Low quality",
             "content": "Bad", "score": 0.2, "published_date": "2025-01-01"},
        ]
    }
    
    with patch.object(TavilyClient, "search", return_value=mock_response):
        results = search_recent_evidence("CDI treatment")
    
    # Only the high-score result should pass
    assert len(results) == 1
    assert results[0]["score"] == 0.9
```
