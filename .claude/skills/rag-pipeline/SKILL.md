---
name: rag-pipeline
description: Use this skill whenever you're building, debugging, or optimizing a Retrieval-Augmented Generation (RAG) pipeline — including embedding generation, vector storage, hybrid search, reranking, LLM generation with citations, and post-generation verification. Also trigger for: context window management, "lost in the middle" problems, citation hallucination debugging, faithfulness evaluation, RAGAS metrics, retrieval latency optimization. This skill applies to any domain (medical, legal, financial, technical) and any vector DB (Qdrant, Pinecone, Weaviate, pgvector).
---

# RAG Pipeline — Production Patterns

A RAG pipeline has exactly one job: ensure the LLM generates answers that are grounded in retrieved evidence, with every claim traceable to a real source. When it fails, it fails in three ways: retrieval fails (wrong chunks), generation fails (ignores chunks), or citation fails (claims don't match sources). This skill addresses all three.

## The Architecture You Must Follow

```
Query
  ↓
Query Router (intent classification + entity extraction)
  ↓
Parallel Retrieval (vector DB + live web + drug DB + ...)
  ↓
Re-ranking (cross-encoder for precision)
  ↓
Context Assembly (lost-in-middle mitigation)
  ↓
LLM Generation (structured JSON + inline citations)
  ↓
Citation Verification (NLI entailment check)
  ↓
Response Formatting (output-channel specific)
```

Skip any step and you introduce a failure mode. Don't skip steps.

---

## Step 1: Embedding

### Model Selection

| Scenario | Model | Why |
|----------|-------|-----|
| Multilingual corpus (Hindi/English) | BGE-M3 | Dense + sparse in one pass; 100+ languages; 8192 tokens |
| English-only medical | PubMedBERT / MedCPT-Encoder | Trained on biomedical text |
| API-only (no GPU) | Gemini text-embedding-004 or Voyage-3 | Top MTEB; no infrastructure |
| Any (general purpose) | text-embedding-3-large (OpenAI) | Strong MTEB; API only |

### BGE-M3 (Recommended — Dense + Sparse in One Call)

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

def embed_batch(texts: list[str], batch_size: int = 32) -> dict:
    """Returns dense vectors and sparse lexical weights."""
    return model.encode(
        texts,
        batch_size=batch_size,
        max_length=8192,      # Full medical abstracts, no truncation
        return_dense=True,    # 1024-dim semantic vectors
        return_sparse=True,   # BM25-equivalent for exact term matching
        return_colbert_vecs=False,  # Skip unless doing late interaction reranking
    )

# Access results
output = embed_batch(["What is the treatment for CDI?"])
dense = output["dense_vecs"][0]         # list[float], dim=1024
sparse = output["lexical_weights"][0]   # dict[token_id, weight]
```

### Chunking Strategy

```python
def chunk_document(
    text: str,
    chunk_size: int = 512,    # tokens
    overlap: int = 128,       # tokens
    metadata: dict = None,
) -> list[dict]:
    """
    Structure-aware chunking — never split mid-sentence or mid-table.
    
    Rules:
    - Split at paragraph boundaries first
    - Then at sentence boundaries
    - Never split a table, dosage chart, or numbered list across chunks
    - Prepend every chunk with metadata header for context retention
    """
    header = ""
    if metadata:
        parts = []
        if metadata.get("source"): parts.append(f"Source: {metadata['source']}")
        if metadata.get("document"): parts.append(f"Document: {metadata['document']}")
        if metadata.get("section"): parts.append(f"Section: {metadata['section']}")
        if parts:
            header = f"[{' | '.join(parts)}]\n\n"
    
    # Split on double newlines (paragraphs) first
    paragraphs = text.split("\n\n")
    chunks = []
    current = header
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Rough token estimate: 1 token ≈ 4 chars
        if len(current) + len(para) < chunk_size * 4:
            current += para + "\n\n"
        else:
            if current.strip():
                chunks.append({
                    "content": current.strip(),
                    "metadata": metadata or {},
                })
            current = header + para + "\n\n"
    
    if current.strip():
        chunks.append({"content": current.strip(), "metadata": metadata or {}})
    
    return chunks
```

---

## Step 2: Vector Storage (Qdrant)

### Collection Setup

```python
from qdrant_client import QdrantClient, models

def create_hybrid_collection(
    client: QdrantClient,
    collection_name: str,
    dense_dim: int = 1024,  # BGE-M3 default
) -> None:
    """Create a collection supporting both dense and sparse vectors."""
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(
                size=dense_dim,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF,  # Critical: enables TF-IDF weighting
            ),
        },
        # Performance settings
        optimizers_config=models.OptimizersConfigDiff(
            indexing_threshold=10000,  # Build HNSW index after 10K vectors
        ),
    )
    
    # Create payload indexes for filters
    for field, schema in [
        ("source", models.PayloadSchemaType.KEYWORD),
        ("pub_year", models.PayloadSchemaType.INTEGER),
        ("evidence_level", models.PayloadSchemaType.KEYWORD),
        ("source_tier", models.PayloadSchemaType.INTEGER),
    ]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=schema,
        )
```

---

## Step 3: Hybrid Retrieval

### The Prefetch + RRF Pattern

```python
from qdrant_client.models import Prefetch, FusionQuery, Fusion, Filter, FieldCondition

async def hybrid_search(
    client: QdrantClient,
    collection: str,
    dense_vector: list[float],
    sparse_vector: dict[int, float],  # token_id -> weight
    limit: int = 50,  # Pre-reranking candidates
    year_from: int = 2020,
    source_tiers: list[int] = None,
) -> list:
    """
    Hybrid search combining dense (semantic) and sparse (BM25) retrieval
    with Reciprocal Rank Fusion.
    """
    # Build metadata filter
    must = [FieldCondition(key="pub_year", range=models.Range(gte=year_from))]
    if source_tiers:
        must.append(FieldCondition(key="source_tier", match=models.MatchAny(any=source_tiers)))
    
    filter_cond = Filter(must=must)
    
    sparse_qdrant = models.SparseVector(
        indices=list(sparse_vector.keys()),
        values=list(sparse_vector.values()),
    )
    
    return client.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(query=dense_vector, using="dense", limit=limit),
            Prefetch(query=sparse_qdrant, using="sparse", limit=limit),
        ],
        query=FusionQuery(fusion=Fusion.RRF),  # Reciprocal Rank Fusion
        limit=limit,
        query_filter=filter_cond,
        with_payload=True,
    ).points
```

---

## Step 4: Reranking

### Two-Tier Strategy

```python
# Tier 1: Cohere (default — multilingual, zero infrastructure)
import cohere

co = cohere.Client(api_key=os.environ["COHERE_API_KEY"])

def cohere_rerank(
    query: str,
    documents: list[str],
    top_n: int = 5,
    model: str = "rerank-v3.5",
) -> list[tuple[int, float]]:
    """Returns list of (original_index, relevance_score)."""
    response = co.rerank(
        model=model,
        query=query,
        documents=documents,
        top_n=top_n,
    )
    return [(r.index, r.relevance_score) for r in response.results]

# Tier 2: MedCPT (PubMed-specific, free, self-hosted)
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class MedCPTReranker:
    """
    MedCPT Cross-Encoder trained on 18M PubMed query-article pairs.
    Use specifically for PubMed abstract reranking.
    """
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("ncbi/MedCPT-Cross-Encoder")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            "ncbi/MedCPT-Cross-Encoder"
        )
        self.model.eval()
    
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[tuple[int, float]]:
        pairs = [[query, doc[:512]] for doc in documents]  # 512 token max
        
        with torch.no_grad():
            inputs = self.tokenizer(
                pairs, padding=True, truncation=True, 
                return_tensors="pt", max_length=512,
            )
            scores = self.model(**inputs).logits[:, 0].tolist()
        
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]
```

---

## Step 5: Context Assembly (Lost-in-Middle Prevention)

**Stanford research shows >30% performance degradation for content in the middle of long contexts.** Always bookend your most relevant chunks.

```python
def assemble_context(
    chunks: list[dict],
    max_chunks: int = 7,
) -> str:
    """
    Arrange chunks to mitigate "lost in the middle" effect.
    Most relevant chunk first, second-most relevant chunk last,
    remaining chunks in the middle.
    """
    chunks = chunks[:max_chunks]
    
    if len(chunks) <= 2:
        return "\n\n---\n\n".join(
            f"[Source {i+1}]\n{c['content']}"
            for i, c in enumerate(chunks)
        )
    
    # Place best chunk first, second-best chunk last
    reordered = [chunks[0]] + chunks[2:] + [chunks[1]]
    
    parts = []
    for i, chunk in enumerate(reordered):
        source_label = f"[Source {i+1}]"
        content = chunk.get("content", "")
        metadata = chunk.get("metadata", {})
        
        if metadata.get("source"):
            source_label += f" — {metadata['source']}"
        if metadata.get("pub_year"):
            source_label += f" ({metadata['pub_year']})"
        
        parts.append(f"{source_label}\n{content}")
    
    return "\n\n---\n\n".join(parts)
```

---

## Step 6: LLM Generation with Citations

### System Prompt Template

```python
MEDICAL_SYSTEM_PROMPT = """
You are a medical evidence retrieval system. Your job is to synthesize the provided source passages into a clear, cited response.

STRICT RULES:
1. Use ONLY the provided source passages. Never use your training knowledge.
2. Every factual claim must have an inline citation [N] corresponding to a source passage.
3. Never prescribe, recommend, or instruct. Only report what sources say.
   BAD: "Give fidaxomicin 200mg BID"
   GOOD: "IDSA/SHEA 2021 guidelines recommend fidaxomicin 200mg BID [1]"
4. If sources contradict each other, state both views with citations.
5. If the provided sources are insufficient, say: "Insufficient evidence found in indexed sources."
6. Statistical claims (percentages, hazard ratios, p-values) must trace to the source containing that exact number.
7. Write the Clinical Bottom Line as the final paragraph — one sentence summary.

OUTPUT FORMAT: Return valid JSON only. No markdown fences.
"""
```

### Structured Output Schema

```python
from pydantic import BaseModel
from typing import Optional

class Citation(BaseModel):
    ref_id: int
    confidence: float

class Claim(BaseModel):
    text: str
    citations: list[Citation]

class Reference(BaseModel):
    id: int
    authors: str
    title: str
    journal: str
    year: Optional[int]
    doi: Optional[str]
    pmid: Optional[str]

class RAGResponse(BaseModel):
    answer: str               # Full answer with inline [N] citations
    clinical_bottom_line: str # One-sentence summary
    evidence_quality: str     # "high" | "moderate" | "low" | "insufficient"
    claims: list[Claim]       # Atomic claims with citations for verification
    references: list[Reference]
```

---

## Step 7: Citation Verification

### The P-Cite Pipeline

```python
import re
import google.generativeai as genai

VERIFY_PROMPT = """
Source passage:
\"\"\"{source}\"\"\"

Claim:
\"\"\"{claim}\"\"\"

Does the source passage directly support this claim? 
Consider: Is the key fact, statistic, or recommendation present in the source?

Return JSON: {{"entailment": true/false, "confidence": 0.0-1.0, "reason": "brief"}}
"""

async def verify_claim(
    claim_text: str,
    source_passage: str,
    model: genai.GenerativeModel,
    threshold: float = 0.7,
) -> dict:
    """Verify a single claim against its cited source using LLM-as-judge."""
    prompt = VERIFY_PROMPT.format(
        source=source_passage[:2000],
        claim=claim_text[:500],
    )
    
    response = await model.generate_content_async(
        prompt,
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
    )
    
    result = json.loads(response.text)
    return {
        "entailment": result.get("entailment", False),
        "confidence": result.get("confidence", 0.0),
        "passes": result.get("confidence", 0.0) >= threshold,
    }
```

---

## Evaluation (RAGAS)

```python
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision, answer_relevancy

# Target scores for production
QUALITY_GATES = {
    "faithfulness": 0.85,        # Claims must exist in retrieved context
    "context_precision": 0.75,   # Retrieved chunks must be relevant
    "answer_relevancy": 0.80,    # Answer must address the query
}

def evaluate_rag(dataset) -> dict[str, float]:
    results = evaluate(dataset, metrics=[faithfulness, context_precision, answer_relevancy])
    
    failures = {
        metric: score
        for metric, score in results.items()
        if score < QUALITY_GATES.get(metric, 0)
    }
    
    if failures:
        raise ValueError(f"Quality gates failed: {failures}")
    
    return dict(results)
```

---

## What NOT to Do

```python
# ❌ Retrieve 3 chunks without reranking — low recall, no precision
results = qdrant.search(query_vector, limit=3)

# ❌ Feed all retrieved text into one giant context
context = "\n".join(all_50_chunks)  # Lost-in-middle kills accuracy

# ❌ No citation verification — ~26% of citations will be wrong
response = llm.generate(prompt)  # Trust and ship — guaranteed hallucinations

# ❌ Temperature > 0.1 for medical generation
config = {"temperature": 0.7}  # Randomness = hallucination

# ❌ No human filter on PubMed queries
search("CDI treatment")  # Returns rat studies alongside human trials

# ❌ Hard date cutoff instead of temporal weighting
WHERE pub_year >= 2023  # Misses the foundational 2021 IDSA guideline
```
