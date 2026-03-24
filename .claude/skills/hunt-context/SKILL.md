---
name: hunt-context
description: Background domain knowledge for Hunt AI — a WhatsApp-native medical RAG system for Indian doctors. Load automatically when discussing architecture, pipeline stages, services, evidence tiers, hallucination prevention, or any Hunt AI code. Provides service map, data flow, key file locations, and design decisions.
user-invocable: false
---

# Hunt AI — Domain Context

## What it is
Hunt AI is a WhatsApp chatbot for Indian doctors that answers clinical questions with cited, NLI-verified answers grounded in ICMR guidelines, PubMed, PMC full-text, and the CDSCO drug database.

## Project root
`/Users/admin/Documents/hunt.ai/`

## Service map

| Service | Port | Entry point | Purpose |
|---------|------|-------------|---------|
| Webhook | 8080 | `services/webhook/main.py` | Twilio validation → Redis dedup → Pub/Sub publish |
| Worker  | 8083 | `services/worker/main.py`  | Full RAG pipeline (query → retrieval → generation → NLI → reply) |
| Reranker | 8001 | `services/reranker/main.py` | MedCPT Cross-Encoder scoring (POST /rerank) |
| Verifier | 8002 | `services/verifier/main.py` | DeBERTa NLI (upgrade path — POST /verify) |
| Dashboard | 8501 | `scripts/dashboard/app.py` | Streamlit metrics + reranker playground |

## Worker pipeline stages (in order)
1. **Query Understanding** — translate → classify intent → PICO extraction → query expansion
   File: `services/worker/query_understanding.py`
2. **Hybrid Retrieval** — 3 parallel sources: Qdrant (dense+sparse RRF) + NCBI E-utilities + PMC BioC full-text; Tavily fallback if NCBI < 5 recent results
   File: `services/worker/retrieval.py`
3. **Two-Tier Reranking** — Cohere Rerank 3.5 (50→15) → MedCPT (15→5)
   Same file: `services/worker/retrieval.py`
4. **Generation** — Gemini 2.5 Pro, JSON-mode, entropy-aware system prompt
   File: `services/worker/generation.py`
5. **Citation Verification** — per-claim NLI with adaptive depth (LEAD-inspired); DOI validation via CrossRef
   File: `services/worker/citation_verifier.py`
6. **Formatting** — WhatsApp markdown, confidence badges, 4096-char pagination
   File: `services/worker/formatter.py`

## Key shared files
- Config: `shared/config/settings.py` — all env vars via Pydantic BaseSettings
- Models: `shared/models/query.py` (QueryMessage, QueryIntent, PICOElements), `shared/models/response.py` (HuntAIResponse, Citation)
- Utils: `shared/utils/cache.py`, `shared/utils/cloud_logging.py`, `shared/utils/gemini_client.py`, `shared/utils/rate_limiter.py`

## Evidence tier weights
Tier 1 (ICMR/CDSCO) = 1.00 → Tier 6 (preprints) = 0.60
Temporal: 2025→1.00, 2024→0.98, 2023→0.94, <2020→excluded unless landmark

## Anti-hallucination (LEAD-inspired)
- Generation prompt requests `self_assessed_confidence` per claim
- `citation_verifier.py`: LOW-confidence claims get deep NLI (2000-char passage vs 800-char)
- `_find_better_source()`: searches all chunks when uncertain claim fails NLI
- `_strip_removed_citations()`: removes [N] from answer for CONTRADICTED claims
- Pipeline wires chunks to verifier: `verify(response, all_chunks=chunks)`

## Webhook deduplication
`dedup_key = f"dedup:{sha256(f'{From}:{text}').hexdigest()}"`
Redis SET NX EX 7200 before Pub/Sub publish. Prevents duplicate processing in 2-hour window.

## PMC full-text integration
`services/ingestion/pmc_fetcher.py` — PMID→PMCID conversion, BioC XML parsing.
In retrieval, PMC chunks replace abstract for same PMID (dedup). Source label: `PMC_fulltext`.

## Collections
- `medical_evidence` — ICMR guidelines + PubMed/PMC articles (BGE-M3, 1024-dim dense + sparse)
- `indian_drugs` — CDSCO drug database (tier=1, doc_type=drug_regulatory)

## Embedding backends
- `EMBEDDING_BACKEND=bge` (default) — BAAI/BGE-M3 dense+sparse, multilingual
- `EMBEDDING_BACKEND=google` — text-embedding-004, dense only, no GPU needed

## Cloud infrastructure
GCP Cloud Run (asia-south1), Pub/Sub topic `hunt-ai-queries`, Qdrant Cloud, Redis Memorystore.
Structured JSON logging via `shared/utils/cloud_logging.py` (auto-detects Cloud Run via `K_SERVICE`).
