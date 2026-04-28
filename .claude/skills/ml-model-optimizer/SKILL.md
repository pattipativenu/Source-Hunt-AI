---
name: ml-model-optimizer
description: >
  Improve the accuracy and efficiency of ML models in the Noocyte AI pipeline,
  including embedding models, rerankers, and NLI verifiers. Use when benchmark
  scores are below target, retrieval quality is poor, or citation verification
  is failing. Covers fine-tuning strategies, prompt optimization for Gemini,
  retrieval parameter tuning, and PyTorch-based model improvements.
argument-hint: "<component: embedding|reranker|nli|gemini-prompt> <current score> <target score>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# ML Model Optimizer

## Purpose

When the Noocyte AI benchmark score is below target, the problem is almost always in one of three places: the embedding model is not finding the right chunks, the reranker is not prioritizing the best evidence, or Gemini's prompt is not generating the right structure. This skill gives you the tools to diagnose and fix each of these.

You do not need a computer science background to use this skill. Each optimization is explained in plain language with the exact code to run.

---

## The Optimization Hierarchy

Always optimize in this order — earlier steps have more impact and are cheaper:

```
1. PROMPT OPTIMIZATION (free, highest impact)
   → Improve Gemini's system prompt and output schema
   
2. RETRIEVAL PARAMETER TUNING (free, high impact)
   → Adjust top_k, similarity threshold, hybrid search weights
   
3. RERANKER TUNING (free, medium impact)
   → Adjust reranking model, top_n, score thresholds
   
4. EMBEDDING MODEL UPGRADE (moderate cost, medium impact)
   → Switch to a better embedding model
   
5. FINE-TUNING (high cost, high impact — only if 1-4 fail)
   → Fine-tune embedding or reranker on medical data
```

---

## Level 1: Gemini Prompt Optimization

This is the fastest and highest-impact optimization. Most quality issues come from the prompt, not the model.

### The OpenEvidence Quality Standard

Study the 10 OpenEvidence benchmark answers. Every Noocyte AI response should match this pattern:

```
Structure of a high-quality OpenEvidence-style answer:
1. Direct answer in first sentence (BLUF)
2. Guideline citation with strength of recommendation
3. Quantified comparison (e.g., "16% vs 25% recurrence rate")
4. Alternative option when first-line is unavailable
5. Inline [N] citations for every factual claim
6. References section with full DOIs
```

### Prompt Engineering for Medical Accuracy

```python
# The Noocyte AI system prompt — optimize this first
MEDICAL_SYSTEM_PROMPT = """You are Noocyte AI, a clinical decision support tool for Indian doctors.

CRITICAL RULES (never violate):
1. NEVER use prescriptive language: "prescribe", "administer", "give the patient", "start on"
   ALWAYS use: "Guidelines recommend", "Evidence supports", "According to [source]"
2. EVERY factual claim needs an inline citation [N]
3. Statistical claims (percentages, hazard ratios, p-values) MUST cite a specific study
4. If ICMR guidelines exist for this condition, cite them FIRST before international guidelines
5. For Indian drug brands, always include the INN (generic name) in parentheses

OUTPUT FORMAT (JSON):
{
  "answer": "string — the clinical answer with inline [N] citations",
  "citations": [
    {
      "id": 1,
      "title": "Full paper title",
      "authors": "Last FM et al.",
      "journal": "Journal Name",
      "year": "YYYY",
      "doi": "10.xxxx/xxxxx",
      "relevance": "Why this citation supports the claim"
    }
  ],
  "confidence_level": "HIGH|MEDIUM|LOW",
  "india_specific_note": "string or null — India-specific context if applicable",
  "follow_up_question": "string — one follow-up question to deepen engagement"
}

QUALITY CHECKLIST before responding:
- Does the first sentence directly answer the question?
- Is every percentage/ratio/p-value cited?
- Are ICMR guidelines prioritized for India-specific conditions?
- Is the answer free of prescriptive language?
- Are all [N] citations sequential and matched to the references array?
"""

# Optimization technique: few-shot examples
FEW_SHOT_EXAMPLES = [
    {
        "query": "First-line treatment for CDI?",
        "ideal_answer": "Fidaxomicin 200mg BD × 10 days is preferred over vancomycin for initial non-fulminant CDI [1], with significantly lower recurrence rates (16% vs 25%) [2]. Vancomycin 125mg QID × 10 days is acceptable when fidaxomicin is unavailable [1].",
    },
    # Add more examples from the OpenEvidence benchmark
]
```

### A/B Testing Prompt Changes

```python
# Never change the prompt without measuring the impact
async def ab_test_prompt(
    prompt_a: str,
    prompt_b: str,
    test_queries: list[dict],
) -> dict:
    """
    Compare two prompts on the benchmark queries.
    Returns which prompt performs better and by how much.
    """
    scores_a = []
    scores_b = []
    
    for query in test_queries:
        result_a = await generate_with_prompt(prompt_a, query["question"])
        result_b = await generate_with_prompt(prompt_b, query["question"])
        
        score_a = evaluate_response(result_a, query["gold_answer"])
        score_b = evaluate_response(result_b, query["gold_answer"])
        
        scores_a.append(score_a)
        scores_b.append(score_b)
    
    avg_a = sum(scores_a) / len(scores_a)
    avg_b = sum(scores_b) / len(scores_b)
    
    winner = "A" if avg_a > avg_b else "B"
    improvement = abs(avg_a - avg_b) / min(avg_a, avg_b) * 100
    
    return {
        "winner": winner,
        "prompt_a_score": avg_a,
        "prompt_b_score": avg_b,
        "improvement_pct": improvement,
        "recommendation": f"Use Prompt {winner} — {improvement:.1f}% better",
    }
```

---

## Level 2: Retrieval Parameter Tuning

### Hybrid Search Weight Optimization

BGE-M3 generates both dense and sparse vectors. The balance between them affects retrieval quality:

```python
# Qdrant hybrid search parameters to tune
RETRIEVAL_PARAMS = {
    "dense_weight": 0.7,    # Weight for semantic (dense) search
    "sparse_weight": 0.3,   # Weight for keyword (sparse/BM25) search
    "top_k": 50,            # Candidates before reranking
    "score_threshold": 0.3, # Minimum similarity score to include
}

# When to adjust:
# - Queries with exact drug names (e.g., "fidaxomicin") → increase sparse_weight
# - Conceptual queries (e.g., "best treatment for CDI") → increase dense_weight
# - Too many irrelevant chunks → increase score_threshold
# - Missing relevant chunks → decrease score_threshold or increase top_k

def tune_hybrid_weights(query_type: str) -> dict:
    """Return optimized weights based on query type."""
    if query_type == "drug_lookup":
        # Drug name queries benefit from exact keyword matching
        return {"dense_weight": 0.4, "sparse_weight": 0.6}
    elif query_type == "guideline":
        # Guideline queries benefit from semantic understanding
        return {"dense_weight": 0.8, "sparse_weight": 0.2}
    else:
        # Default balanced weights
        return {"dense_weight": 0.7, "sparse_weight": 0.3}
```

### Chunk Size Optimization

The size of text chunks stored in Qdrant directly affects retrieval quality:

```python
CHUNK_STRATEGIES = {
    "small_chunks": {
        "size": 256,    # tokens
        "overlap": 32,
        "best_for": "precise fact retrieval (drug doses, specific statistics)",
        "risk": "loses context — a chunk may not contain enough to answer the question",
    },
    "medium_chunks": {
        "size": 512,    # tokens — CURRENT DEFAULT
        "overlap": 64,
        "best_for": "balanced retrieval — works for most medical queries",
        "risk": "may split a table or list across chunks",
    },
    "large_chunks": {
        "size": 1024,   # tokens
        "overlap": 128,
        "best_for": "guideline sections that need full context",
        "risk": "slower embedding, may dilute relevance score",
    },
}

# Recommendation: Use 512 tokens for most content, 256 for drug information tables
```

---

## Level 3: Reranker Tuning

```python
# Tune the reranker's top_n and score threshold
RERANKER_PARAMS = {
    "cohere_top_n": 10,         # After Cohere: keep top 10 from 50
    "medcpt_top_n": 5,          # After MedCPT: keep top 5 from 10
    "min_cohere_score": 0.1,    # Discard chunks below this score
    "min_medcpt_score": 0.3,    # Discard chunks below this score
}

# Diagnostic: if all citations are INSUFFICIENT after NLI verification,
# the reranker may be returning irrelevant chunks.
# Fix: lower min_cohere_score to include more candidates, or increase cohere_top_n

# Diagnostic: if response is slow (> 8 seconds),
# the reranker may be processing too many chunks.
# Fix: lower top_k from 50 to 30, or increase min_cohere_score
```

---

## Level 4: Embedding Model Upgrade

Only consider this if Levels 1-3 have not solved the problem.

```python
# How to safely upgrade the embedding model
async def upgrade_embedding_model(
    new_model: str,
    test_queries: list[str],
    current_model: str = "BAAI/bge-m3",
) -> dict:
    """
    Evaluate a new embedding model before migrating.
    
    IMPORTANT: Changing the embedding model requires re-embedding ALL documents.
    This is expensive. Only do it if the improvement is > 5%.
    """
    # Step 1: Evaluate new model on test queries
    new_scores = await evaluate_retrieval(new_model, test_queries)
    current_scores = await evaluate_retrieval(current_model, test_queries)
    
    improvement = (new_scores["avg_ndcg"] - current_scores["avg_ndcg"]) / current_scores["avg_ndcg"] * 100
    
    if improvement < 5.0:
        return {
            "recommendation": "KEEP CURRENT MODEL",
            "reason": f"Only {improvement:.1f}% improvement — not worth re-embedding cost",
        }
    
    return {
        "recommendation": "UPGRADE",
        "improvement": improvement,
        "migration_steps": [
            "1. Create new Qdrant collection with new model's vector dimensions",
            "2. Re-embed all documents with new model",
            "3. Run benchmark on new collection",
            "4. If benchmark passes, switch traffic to new collection",
            "5. Keep old collection for 1 week as rollback",
        ],
    }
```

---

## Level 5: Fine-Tuning (Advanced)

Fine-tuning is only needed if the pre-trained models consistently fail on a specific type of query. For Noocyte AI, the most likely candidate is fine-tuning the embedding model on Indian medical text.

```python
# Fine-tuning the embedding model on Indian medical query-passage pairs
# This requires:
# 1. A dataset of (query, relevant_passage, irrelevant_passage) triplets
# 2. GPU compute (at least 16GB VRAM)
# 3. ~2-4 hours of training time

# Dataset format for contrastive fine-tuning
TRAINING_EXAMPLE = {
    "query": "First-line treatment for MDR-TB in India",
    "positive": "ICMR recommends a 6-month regimen of bedaquiline, linezolid, and clofazimine (BPaL) for MDR-TB...",
    "negative": "Tuberculosis is a bacterial infection caused by Mycobacterium tuberculosis...",
}

# Use sentence-transformers for fine-tuning
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

def fine_tune_embedding_model(
    base_model: str,
    training_data: list[dict],
    output_path: str,
    epochs: int = 3,
):
    model = SentenceTransformer(base_model)
    
    train_examples = [
        InputExample(
            texts=[ex["query"], ex["positive"], ex["negative"]],
        )
        for ex in training_data
    ]
    
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
    train_loss = losses.TripletLoss(model=model)
    
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=100,
        output_path=output_path,
    )
    
    print(f"Fine-tuned model saved to {output_path}")
```

---

## What NOT to Do

```python
# ❌ Changing multiple parameters at once — can't tell what helped
RETRIEVAL_PARAMS["top_k"] = 100
RETRIEVAL_PARAMS["dense_weight"] = 0.9
RERANKER_PARAMS["cohere_top_n"] = 20
# Now benchmark improved by 15% — but which change caused it?

# ✅ Change one parameter at a time, measure, then change the next
RETRIEVAL_PARAMS["top_k"] = 100  # Change only this
score_after = run_benchmark()
# If improved → keep it. If not → revert. Then try the next change.

# ❌ Fine-tuning before trying prompt optimization
# Fine-tuning takes hours and requires GPU. Prompt optimization takes minutes.
# Always try the cheap options first.

# ❌ Evaluating on the same queries used for optimization
# This is overfitting. Always hold out 2-3 queries for final evaluation.
```

---

*Optimize the prompt first. The model is rarely the problem.*
