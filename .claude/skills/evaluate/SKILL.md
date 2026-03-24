---
name: evaluate
description: Run Hunt AI pipeline evaluation and benchmarking. Use when measuring retrieval quality, answer accuracy, citation verification rates, or comparing changes to the RAG pipeline.
argument-hint: "[--benchmark FILE] [--top-k N] [--query 'single question']"
disable-model-invocation: true
context: fork
allowed-tools: Bash, Read, Glob
---

# Hunt AI — Pipeline Evaluation

Evaluate the Hunt AI RAG pipeline against a benchmark set or run a single test query.

## Arguments
`$ARGUMENTS` — evaluation options. Examples:
- `/evaluate` — run default benchmark (golden_set.jsonl)
- `/evaluate --query "What is first-line TB treatment in India?"` — single query test
- `/evaluate --benchmark custom.jsonl --top-k 3` — custom benchmark

## Steps

1. **Check services are running** (worker + reranker required):
   ```bash
   curl -s http://localhost:8001/health 2>/dev/null | python3 -m json.tool || echo "⚠️  Reranker not running — start with: python3 -m uvicorn services.reranker.main:app --port 8001"
   curl -s http://localhost:8083/health 2>/dev/null | python3 -m json.tool || echo "⚠️  Worker not running — start with: python3 -m uvicorn services.worker.main:app --port 8083"
   ```

2. **Run evaluation**:

   For a single query test:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 -c "
   import asyncio, json
   from services.worker.pipeline import MedicalRAGPipeline

   async def test():
       p = MedicalRAGPipeline()
       result = await p.run('$ARGUMENTS' or 'What is the first-line treatment for MDR-TB in India?')
       print(json.dumps(result, indent=2, default=str))

   asyncio.run(test())
   "
   ```

   For full benchmark:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 scripts/evaluate.py $ARGUMENTS
   ```

3. **Dashboard** — open the Streamlit metrics dashboard for visual comparison:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 -m streamlit run scripts/dashboard/app.py --server.port 8501
   ```
   Then open http://localhost:8501

4. **Report** key metrics:
   - Retrieval: precision@k, recall@k, MRR
   - Citation verification: % SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE
   - Confidence distribution: HIGH / MODERATE / LOW
   - Latency: P50, P95, P99 (ms)
   - Cache hit rate

## Key metrics to watch
- **Citation support rate** > 85% = healthy; < 70% = check NLI threshold (`nli_confidence_threshold` in settings)
- **HIGH confidence rate** < 20% = normal for complex clinical questions
- **Retrieval latency** > 2s = check Qdrant connection or reranker health
- **PMC full-text hit rate** — how often PMC BioC replaces abstract (expect 15–30% of PubMed results)

## Key files
- `scripts/evaluate.py` — benchmark runner
- `scripts/dashboard/app.py` — Streamlit metrics UI
- `services/worker/pipeline.py` — pipeline orchestrator
- `services/worker/citation_verifier.py` — NLI verification (check `nli_confidence_threshold`)
