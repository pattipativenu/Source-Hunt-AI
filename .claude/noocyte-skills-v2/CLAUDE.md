# Noocyte.ai — Claude Code Project Configuration

## What We're Building

Noocyte.ai is a grounded medical evidence retrieval engine delivered natively through WhatsApp for India's 1.4 million doctors. Every answer is synthesised from authoritative sources, every claim is verified against its cited source, and every number traces to a real, accessible paper.

**Stack:** Python 3.11 · FastAPI · Qdrant Cloud · BGE-M3 · Cohere Rerank 3.5 · MedCPT · Gemini 2.5 Flash · Meta WhatsApp Cloud API · GCP Cloud Run + Pub/Sub · Redis · Firestore · GCS

**Target cost:** ~$150-$170/month at MVP scale (100-500 DAU)

---

## Project Structure

```
noocyte/
├── api/                    # FastAPI application
│   ├── main.py             # App entry point, middleware, health check
│   ├── routes/
│   │   ├── webhook.py      # WhatsApp webhook handler (200 ACK + Pub/Sub enqueue)
│   │   └── health.py       # /health endpoint for Cloud Run liveness probe
│   └── middleware.py       # Rate limiting, request ID, logging
│
├── core/                   # Business logic
│   ├── query_router.py     # Intent classification, PICO extraction, brand→generic
│   ├── retrieval.py        # Parallel retrieval orchestration
│   ├── reranker.py         # Cohere + MedCPT two-tier reranking
│   ├── generator.py        # Gemini generation with structured JSON output
│   ├── citation_verifier.py # Post-generation NLI entailment verification
│   └── emergency.py        # Pre-LLM emergency detection (no API calls)
│
├── data/                   # Data access layer
│   ├── qdrant_client.py    # Qdrant hybrid search wrapper
│   ├── pubmed_client.py    # NCBI E-utilities with rate limiting
│   ├── tavily_client.py    # Live web search for recent papers
│   ├── drug_db.py          # 253K Indian medicine brand→generic lookup
│   └── firestore_client.py # Existing ICMR embeddings (migration source)
│
├── delivery/               # Response formatting and sending
│   ├── formatter.py        # WhatsApp markdown, 4096-char splitting, buttons
│   └── whatsapp_api.py     # Meta Cloud API delivery with retry
│
├── workers/                # Async background processing
│   └── rag_worker.py       # Pub/Sub consumer: dequeue → full RAG pipeline → deliver
│
├── models/                 # Pydantic data models (shared types)
│   ├── query.py            # QueryRequest, QueryIntent, PICoExtraction
│   ├── evidence.py         # RetrievedChunk, RerankedChunk, RAGResponse
│   └── citation.py         # Citation, Reference, ClaimVerification
│
├── utils/
│   ├── rate_limiter.py     # Token bucket (NCBI: 10 req/s, WhatsApp, Gemini)
│   ├── pii_redactor.py     # Presidio-based PII redaction before logging
│   ├── cache.py            # Redis semantic cache + response cache
│   └── logging.py          # Structured JSON logging for GCP Cloud Logging
│
├── scripts/
│   ├── migrate_firestore_to_qdrant.py  # One-time migration of ICMR embeddings
│   ├── load_drug_database.py           # Load 253K medicines into Qdrant
│   └── run_benchmark.py               # 10-query OpenEvidence quality benchmark
│
├── tests/
│   ├── conftest.py         # Shared fixtures, mock factories
│   ├── unit/               # Fast, no external dependencies
│   ├── integration/        # Real Qdrant test instance, mocked APIs
│   └── e2e/                # Full pipeline benchmark (10-query set)
│
├── .env.example            # Required environment variables (no secrets)
├── requirements.txt        # Pinned exact versions
├── Dockerfile              # Multi-stage build for Cloud Run (linux/amd64)
├── pyproject.toml          # Black, ruff, mypy, pytest configuration
└── CLAUDE.md               # This file
```

---

## Non-Negotiable Constraints

These are not preferences. They are hard requirements. Every PR must honour them.

### Medical Safety
1. **Never generate prescriptive language.** The system reports what guidelines say — it does not prescribe, advise, or instruct.
   - ❌ `"Give fidaxomicin 200mg BID"` / `"Prescribe X"` / `"Administer Y"`
   - ✅ `"IDSA/SHEA 2021 guidelines recommend fidaxomicin 200mg PO BID [1]"`

2. **Every factual claim requires an inline citation [N].** Statistics (percentages, hazard ratios, p-values) must trace to the specific source containing that number.

3. **Emergency detection runs before any LLM call.** Pre-LLM keyword check for cardiac arrest, STEMI, anaphylaxis, stroke, DKA, overdose, septic shock. If detected: prepend "Call 108" before evidence.

4. **PII must be redacted before any external API call.** Presidio runs on every query before it reaches Gemini, Cohere, PubMed, or Tavily.

### API Constraints
5. **NCBI E-utilities: maximum 10 requests/second.** The `NCBIRateLimiter` token bucket MUST be used before every NCBI request. Exceeding this risks IP ban.

6. **WhatsApp: 4,096 character hard limit.** The formatter MUST split long responses. Never send unsplit text that might be truncated by WhatsApp silently.

7. **Gemini temperature ≤ 0.1** for all medical generation. No exceptions.

8. **Structured JSON output enforced.** Every Gemini call that produces citations must use `response_mime_type: "application/json"` with a `response_schema`.

### Citation Rules
9. **Citation [N] in body maps exactly to references[N].** 1-indexed, sequential. No orphaned citations (inline [N] without a reference entry). No unused references.

10. **DOIs validated via CrossRef before delivery.** A citation with a non-resolving DOI is a hallucinated citation.

---

## Data Flow (Single Query)

```
WhatsApp message (doctor)
  ↓ POST /webhook (Cloud Run)
  ↓ Validate X-Hub-Signature-256 → 200 ACK → publish to Pub/Sub
  ↓ (async, Cloud Run worker)
  ↓ Query Router: emergency check → PII redact → brand→generic → PICO extract → intent classify
  ↓ Parallel retrieval [asyncio.gather]:
  │   ├── Qdrant hybrid (dense + sparse, top 50 candidates)
  │   ├── PubMed E-utilities (ESearch → EFetch, rate-limited)
  │   └── Tavily (only if Qdrant < 3 results OR query < 90 days old)
  ↓ Two-tier reranking:
  │   ├── Cohere Rerank 3.5 (all queries, 50 → 10)
  │   └── MedCPT Cross-Encoder (PubMed results only, 10 → 5)
  ↓ Context assembly (best chunk first, second-best last — lost-in-middle mitigation)
  ↓ Gemini 2.5 Flash (temperature 0.0, structured JSON, inline [N] citations)
  ↓ Citation verification (NLI entailment > 0.7 per claim, DOI resolution)
  ↓ WhatsApp formatter (split at 3,800 chars, buttons on final part)
  ↓ Meta Cloud API → Doctor's WhatsApp (3-8 seconds total)
```

---

## Source Priority Hierarchy

When multiple sources conflict, prioritise in this order:

1. **ICMR Standard Treatment Workflows** (Indian government, highest authority for Indian practice)
2. **Indian specialty society guidelines** (CSI, RSSDI, ISN India, IAP, ISG, ISI)
3. **International guidelines** (ACC/AHA, ESC, IDSA, ADA, KDIGO, NCCN, ASCO)
4. **Flagship general journals** (NEJM, Lancet, JAMA, BMJ)
5. **Specialty journals** (Circulation, JACC, JCO, Clinical Infectious Diseases, etc.)
6. **Meta-analyses and systematic reviews** from Cochrane or equivalent
7. **Individual RCTs** in peer-reviewed journals
8. **Expert reviews and cohort studies**

When the drug name is an Indian brand (Dolo, Augmentin, Glycomet, Ecosprin), always resolve to INN before searching PubMed.

---

## Environment Variables

Required in `.env` (see `.env.example` for all):

```bash
# Vector DB
QDRANT_URL=https://xxx.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=

# LLM
GEMINI_API_KEY=

# Reranking
COHERE_API_KEY=

# Literature retrieval
NCBI_API_KEY=         # CRITICAL: 10 req/s without this
NCBI_EMAIL=           # Required by NCBI ToS

# Live search
TAVILY_API_KEY=

# WhatsApp
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=  # For webhook signature validation

# Cache
REDIS_URL=redis://localhost:6379

# GCP
GOOGLE_CLOUD_PROJECT=
```

---

## Agents and Skills Available

Load these agents when delegating work. Full instructions in `agents/` directory.

| Task | Agent to Load |
|------|--------------|
| Implementation planning | `agents/planner.md` |
| Architecture decisions | `agents/architect.md` |
| Python code review | `agents/senior-python-engineer.md` |
| RAG/LLM pipeline review | `agents/senior-ai-engineer.md` |
| Medical output review | `agents/senior-medical-advisor.md` |
| Security audit | `agents/security-reviewer.md` |
| Database schema review | `agents/database-reviewer.md` |
| Build error diagnosis | `agents/build-error-resolver.md` |
| Benchmark evaluation | `agents/harness-optimizer.md` |
| General code review | `agents/code-reviewer.md` |

---

## Quality Gates

Every PR touching the RAG pipeline must pass:
- `pytest tests/unit/ --cov=noocyte --cov-fail-under=80`
- `mypy noocyte/ --strict`
- `ruff check noocyte/`
- `python scripts/run_benchmark.py` → ≥ 7/10 queries pass

Target progression:
- Week 1: 4/10 benchmark queries pass
- Week 2: 6/10
- Week 3: 7/10 (minimum for soft launch)
- Production: 9/10

---

## Slash Commands Available

| Command | When to Use |
|---------|------------|
| `/python-review` | After writing any Python module |
| `/build-fix` | When facing any build or runtime error |
| `/tdd` | Starting a new function — write tests first |
| `/plan` | Before any multi-file feature |
| `/security-check` | Before any PR involving auth, input handling, or external APIs |
| `/benchmark` | Before merging RAG pipeline changes |
| `/test-coverage` | When coverage drops below 80% |
| `/multi-plan` | For large features spanning multiple workstreams |

---

*Noocyte.ai — The intelligent cell of medical knowledge.*
*Noos (νοῦς) = intelligent mind. Cyte = fundamental unit of life.*
