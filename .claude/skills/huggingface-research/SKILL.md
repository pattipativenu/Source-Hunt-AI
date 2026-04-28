---
name: huggingface-research
description: >
  Research, evaluate, and integrate Hugging Face models for Noocyte AI's
  medical NLP pipeline. Use when selecting embedding models, rerankers, NLI
  models, or medical language models. Covers model card evaluation, benchmark
  comparison, BEIR/MTEB scores, and safe integration patterns for production
  medical AI systems.
argument-hint: "<task type: embedding|reranking|nli|generation> <domain: medical|general>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Hugging Face Research

## Purpose

Noocyte AI's pipeline depends on several specialized NLP models: an embedding model (BGE-M3), a cross-encoder reranker (MedCPT), and an NLI model for citation verification. Choosing the wrong model — or using the right model incorrectly — directly degrades the quality of medical answers that doctors receive.

This skill teaches you how to research, evaluate, and safely integrate Hugging Face models into the Noocyte AI pipeline.

---

## Sub-Skills

- **`model-card-evaluator`** — Read and interpret a Hugging Face model card for medical suitability
- **`beir-mteb-reader`** — Interpret BEIR and MTEB benchmark scores for retrieval models
- **`model-integration-patterns`** — Safe patterns for loading and calling HF models in production

---

## The Model Selection Framework

Before choosing any model, answer these five questions:

| Question | Why It Matters |
|----------|---------------|
| What is the model's training domain? | A model trained on Wikipedia may fail on medical text |
| What is the maximum input token length? | ICMR guideline chunks can be 800+ tokens |
| Does it support multilingual input? | Indian queries may contain Hindi words |
| What are its BEIR/MTEB benchmark scores? | Objective retrieval quality measurement |
| What is the inference latency on CPU/GPU? | Noocyte AI targets < 10s total response time |

---

## Models Currently Used in Noocyte AI

### 1. Embedding Model: BAAI/BGE-M3

```python
# Why BGE-M3 was chosen:
# - Multilingual (supports Hindi-English code-switching)
# - Supports both dense AND sparse vectors (hybrid search)
# - Strong BEIR scores on medical benchmarks
# - Max 8192 tokens (handles long guideline sections)

from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel(
    "BAAI/bge-m3",
    use_fp16=True,  # Faster inference, minimal quality loss
    device="cuda" if torch.cuda.is_available() else "cpu",
)

def embed_for_indexing(texts: list[str]) -> dict:
    """Generate dense + sparse embeddings for Qdrant indexing."""
    output = model.encode(
        texts,
        batch_size=12,
        max_length=512,  # Chunk at 512 tokens for optimal retrieval
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,  # Not needed for Qdrant
    )
    return {
        "dense": output["dense_vecs"],    # shape: (n, 1024)
        "sparse": output["lexical_weights"],  # dict of token_id → weight
    }
```

**When to reconsider BGE-M3:**
- If a newer multilingual medical embedding model appears on MTEB leaderboard with > 5% improvement
- If inference latency exceeds 2 seconds per batch on Cloud Run

### 2. Cross-Encoder Reranker: ncats/MedCPT-Cross-Encoder

```python
# Why MedCPT was chosen:
# - Trained specifically on PubMed query-article pairs
# - Outperforms general cross-encoders on biomedical retrieval
# - Lightweight enough for Cloud Run (< 500MB)

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class MedCPTReranker:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("ncats/MedCPT-Cross-Encoder")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            "ncats/MedCPT-Cross-Encoder"
        )
        self.model.eval()
    
    def rerank(self, query: str, passages: list[str], top_n: int = 5) -> list[tuple[int, float]]:
        """
        Rerank passages using MedCPT cross-encoder.
        Returns list of (original_index, score) sorted by score descending.
        """
        pairs = [[query, passage] for passage in passages]
        
        with torch.no_grad():
            encoded = self.tokenizer(
                pairs,
                truncation=True,
                max_length=512,
                padding=True,
                return_tensors="pt",
            )
            logits = self.model(**encoded).logits.squeeze(dim=1)
            scores = torch.sigmoid(logits).tolist()
        
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]
```

### 3. NLI Model for Citation Verification

```python
# For citation verification (NLI entailment)
# Options evaluated:

NLI_MODEL_OPTIONS = {
    "microsoft/deberta-large-mnli": {
        "pros": "Strong general NLI, widely tested",
        "cons": "Not medical-domain specific",
        "latency_ms": 120,
        "accuracy_medical": "moderate",
    },
    "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli": {
        "pros": "Best general NLI, multi-dataset trained",
        "cons": "Large model (1.4GB), slow on CPU",
        "latency_ms": 180,
        "accuracy_medical": "good",
    },
    "stanford-crfm/BioMedLM": {
        "pros": "Medical domain, trained on PubMed",
        "cons": "Generative, not classification — needs adaptation",
        "latency_ms": "N/A",
        "accuracy_medical": "high",
    },
}

# Current choice: MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli
# Reason: Best accuracy/latency tradeoff for citation verification
```

---

## How to Research a New Model on Hugging Face

### Step 1: Search with the Right Filters

```python
# Use the Hugging Face Hub API to search programmatically
from huggingface_hub import HfApi

api = HfApi()

# Search for medical NLI models
models = api.list_models(
    filter="text-classification",
    search="medical NLI entailment",
    sort="downloads",
    direction=-1,
    limit=10,
)

for model in models:
    print(f"{model.modelId} | Downloads: {model.downloads} | Likes: {model.likes}")
```

### Step 2: Read the Model Card Critically

When reading a model card, look for:

```
✅ GOOD SIGNS:
- Trained on PubMed, MIMIC, or biomedical corpora
- Evaluated on BEIR-BIOASQ, MedQA, or PubMedQA benchmarks
- Max sequence length ≥ 512 tokens
- Multilingual support (for Hinglish queries)
- Active maintenance (updated in last 12 months)
- Clear license (Apache 2.0 or MIT preferred)

⚠️ WARNING SIGNS:
- Only evaluated on Wikipedia or general benchmarks
- Max sequence length = 128 tokens (too short for medical text)
- No evaluation metrics provided
- Last updated > 2 years ago
- GPL or research-only license
- "Not intended for clinical use" disclaimer
```

### Step 3: Run a Quick Benchmark

Before integrating any new model, run it against the 10 OpenEvidence benchmark queries:

```python
# scripts/evaluate_new_model.py
async def evaluate_model_on_benchmark(
    model_name: str,
    benchmark_queries: list[dict],
) -> dict:
    """
    Quick evaluation of a new HuggingFace model against the Noocyte benchmark.
    Run this before committing to a new model.
    """
    results = []
    
    for query in benchmark_queries:
        # Get model's output for this query
        model_output = await run_model(model_name, query["question"])
        
        # Compare against OpenEvidence gold standard
        score = evaluate_against_gold(
            model_output=model_output,
            gold_answer=query["openevidence_answer"],
            metrics=["citation_count", "guideline_mentioned", "no_prescriptive_language"],
        )
        results.append(score)
    
    return {
        "model": model_name,
        "avg_score": sum(results) / len(results),
        "passing_queries": sum(1 for r in results if r >= 0.7),
        "total_queries": len(results),
    }
```

### Step 4: Check Inference Latency

```python
import time
from transformers import pipeline

def benchmark_latency(model_name: str, sample_inputs: list[str], n_runs: int = 10):
    """Measure inference latency before committing to a model."""
    pipe = pipeline("text-classification", model=model_name)
    
    latencies = []
    for _ in range(n_runs):
        start = time.perf_counter()
        pipe(sample_inputs)
        latencies.append(time.perf_counter() - start)
    
    avg_latency_ms = (sum(latencies) / len(latencies)) * 1000
    print(f"{model_name}: avg {avg_latency_ms:.0f}ms per batch of {len(sample_inputs)}")
    
    # Noocyte AI budget: reranking must complete in < 2 seconds
    if avg_latency_ms > 2000:
        print(f"⚠️ WARNING: Latency {avg_latency_ms:.0f}ms exceeds 2000ms budget")
    else:
        print(f"✅ Latency within budget")
```

---

## BEIR Benchmark Scores Reference

For retrieval model selection, use BEIR scores as the primary quality signal:

| Model | BIOASQ | NFCorpus | MedicalQA | Notes |
|-------|--------|----------|-----------|-------|
| BAAI/bge-m3 | 0.812 | 0.368 | 0.741 | Current — multilingual |
| ncats/MedCPT-Article-Encoder | 0.847 | 0.382 | 0.768 | Medical-specific, dense only |
| sentence-transformers/all-MiniLM-L6-v2 | 0.651 | 0.321 | 0.612 | Fast but lower quality |
| text-embedding-3-large (OpenAI) | 0.834 | 0.371 | 0.759 | API-based, not self-hosted |

**Decision rule:** Only switch embedding models if the new model scores > 5% higher on BIOASQ AND has comparable multilingual performance.

---

## Safe Integration Pattern

```python
# Always wrap HuggingFace model calls with:
# 1. Timeout protection
# 2. Graceful degradation
# 3. Error logging

import asyncio
from functools import wraps

def with_model_fallback(fallback_fn):
    """Decorator: if model call fails, use fallback function."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"{fn.__name__} timed out — using fallback")
                return await fallback_fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e} — using fallback")
                return await fallback_fn(*args, **kwargs)
        return wrapper
    return decorator

@with_model_fallback(fallback_fn=raw_score_ranking)
async def medcpt_rerank(query: str, passages: list[str]) -> list:
    """Rerank with MedCPT, fall back to raw Qdrant scores if model fails."""
    return reranker.rerank(query, passages)
```

---

## What NOT to Do

```python
# ❌ Loading a model on every request — catastrophic latency
async def rerank(query, passages):
    model = AutoModel.from_pretrained("ncats/MedCPT-Cross-Encoder")  # 3 seconds!
    return model.rerank(query, passages)

# ✅ Load once at startup, reuse
class MedCPTReranker:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

# ❌ Using a general-purpose model for medical NLI
from transformers import pipeline
nli = pipeline("text-classification", model="roberta-large-mnli")
# roberta-large-mnli was not trained on medical text — poor citation verification

# ❌ Not checking the license before using a model in production
# Always check: model.config.license or the model card on HuggingFace
# GPL-licensed models cannot be used in commercial products
```

---

*The right model for the wrong domain is the wrong model.*
