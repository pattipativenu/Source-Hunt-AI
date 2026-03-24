---
name: query-test
description: Test a clinical query through the Hunt AI RAG pipeline end-to-end. Use when debugging retrieval, generation quality, citation verification, or comparing pipeline changes. Runs a query and shows full pipeline output including retrieved chunks, confidence scores, and NLI results.
argument-hint: "<clinical question>"
disable-model-invocation: true
context: fork
allowed-tools: Bash, Read
---

# Hunt AI — End-to-End Query Test

Run a clinical question through the full Hunt AI pipeline and show detailed diagnostic output.

## Question
$ARGUMENTS

## Steps

1. **Verify worker service** is reachable:
   ```bash
   curl -sf http://localhost:8083/health || echo "Worker not running. Start with: cd /Users/admin/Documents/hunt.ai && python3 -m uvicorn services.worker.main:app --port 8083 --reload"
   ```

2. **Run the query** through the pipeline with verbose output:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 - <<'PYEOF'
   import asyncio, json, os, sys

   # Allow running from project root
   sys.path.insert(0, '.')

   async def run_query():
       question = """$ARGUMENTS"""
       if not question.strip():
           question = "What is the first-line treatment for MDR-TB in India?"

       print(f"\n{'='*60}")
       print(f"QUERY: {question}")
       print(f"{'='*60}\n")

       try:
           from services.worker.query_understanding import QueryUnderstanding
           from services.worker.retrieval import HybridRetriever
           from services.worker.generation import generate_answer
           from services.worker.citation_verifier import CitationVerifier
           from shared.config.settings import get_settings

           settings = get_settings()

           # Stage 1: Query Understanding
           print("📋 STAGE 1: Query Understanding")
           qu = QueryUnderstanding()
           understood = await qu.understand(question)
           print(f"  Intent: {understood.get('intent')}")
           print(f"  Translated: {understood.get('translated_query', question)}")
           print(f"  PICO: {json.dumps(understood.get('pico', {}), indent=4)}")

           # Stage 2: Retrieval
           print("\n🔍 STAGE 2: Retrieval")
           retriever = HybridRetriever()
           chunks = await retriever.retrieve(understood)
           print(f"  Retrieved {len(chunks)} chunks after reranking")
           for i, c in enumerate(chunks[:5]):
               print(f"  [{i+1}] {c.get('source','?')} | score={c.get('score',0):.3f} | {c.get('title','')[:60]}")

           # Stage 3: Generation
           print("\n✍️  STAGE 3: Generation (Gemini 2.5 Pro)")
           response = await generate_answer(understood, chunks)
           print(f"  Confidence: {response.get('confidence_level')}")
           print(f"  Answer preview: {response.get('answer','')[:200]}...")
           print(f"  Citations: {len(response.get('citations', []))}")

           # Stage 4: Citation Verification
           print("\n✅ STAGE 4: Citation Verification")
           verifier = CitationVerifier()
           verified = await verifier.verify(response, all_chunks=chunks)
           citations = verified.get('citations', [])
           for cit in citations:
               status = cit.get('nli_label', 'UNKNOWN')
               conf = cit.get('nli_confidence', 0)
               icon = '✅' if status == 'SUPPORTED' else ('❌' if status == 'CONTRADICTED' else '⚠️')
               print(f"  {icon} [{cit.get('id')}] {status} ({conf:.2f}) — {cit.get('title','')[:50]}")

           print(f"\n{'='*60}")
           print("FINAL ANSWER:")
           print(verified.get('answer', ''))
           print(f"{'='*60}\n")

       except Exception as e:
           import traceback
           print(f"\n❌ Pipeline error: {e}")
           traceback.print_exc()

   asyncio.run(run_query())
   PYEOF
   ```

3. **Summarize** the results:
   - Query intent and PICO extraction
   - Number of chunks retrieved per source (Qdrant, PubMed, PMC)
   - Top 5 reranked chunks with scores
   - Confidence level and answer quality
   - Citation NLI verification breakdown (SUPPORTED / CONTRADICTED / INSUFFICIENT)
   - Any errors or warnings

## Diagnostic tips
- **No chunks retrieved**: Check `QDRANT_URL` in `.env` and Qdrant collection has data (`/ingest`)
- **Generation fails**: Check `GEMINI_API_KEY` or Vertex AI credentials
- **All citations INSUFFICIENT**: Lower `nli_confidence_threshold` in settings (currently 0.70)
- **Slow response**: Check `RERANKER_SERVICE_URL` — reranker may be down or cold-starting
