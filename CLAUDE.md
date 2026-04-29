# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Before anything else

Read [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — it is the primary project guide and overrides this file on product rules (no prescriptive language, mandatory citations, ICMR priority, PII redaction, temperature ≤ 0.1, structured JSON, brand neutrality).

After modifying any code file, run `graphify update .` to keep the knowledge graph current (AST-only, no API cost). Before answering architecture questions, check [`graphify-out/GRAPH_REPORT.md`](graphify-out/GRAPH_REPORT.md) for the core abstractions and community structure.

---

## Development setup

```bash
cp .env.local .env   # then fill in credentials
docker-compose up --build
# With local Qdrant instead of Qdrant Cloud:
docker-compose --profile local up --build
```

Individual services are exposed at:
- `webhook` → `localhost:8080`
- `worker`  → `localhost:8083`
- `reranker` → `localhost:8001`

For local WhatsApp testing, expose the webhook via ngrok: `ngrok http 8080`, then set that URL in the Twilio console.

---

## Common commands

**Format and lint (run before every commit):**
```bash
black .
ruff check . --fix
ruff format .
```

**Type check:**
```bash
mypy --strict services/ shared/
```

**Security scan:**
```bash
bandit -r services/ shared/
```

**Run evaluation benchmark (must pass before merging RAG changes):**
```bash
python scripts/evaluate.py --golden scripts/eval_data/golden_set.json
```

**Run ingestion pipeline:**
```bash
python scripts/run_ingestion.py
```

**Run the Streamlit benchmark dashboard:**
```bash
cd scripts/dashboard && pip install -r requirements.txt && streamlit run app.py
```

---

## Testing

There is no `pytest` test suite yet — the primary quality gate is the evaluation harness above. When adding tests:

```bash
pytest -m unit         # fast, no external deps
pytest -m integration  # requires Redis + Qdrant running
pytest -m benchmark    # runs the 10-query golden set
```

Per `.claude/rules/common/testing.md`: external APIs (PubMed, Gemini, Cohere, Qdrant Cloud) must be mocked in unit and integration tests. Emergency detection requires 100% coverage; citation verifier 95%.

---

## Architecture

### Service topology

Four independently deployed Cloud Run services communicate via Pub/Sub and direct HTTP:

```
WhatsApp (Twilio) → webhook → Cloud Pub/Sub → worker → WhatsApp (Twilio)
                                                  ↓
                                     reranker (MedCPT, HTTP)
                                     verifier (DeBERTa NLI, HTTP)
```

- **`services/webhook`** — FastAPI. Validates Twilio signature, deduplicates (Redis SHA-256 key, 2h window), detects language, publishes `QueryMessage` to Pub/Sub, returns TwiML ACK in <5s.
- **`services/worker`** — FastAPI. Consumes Pub/Sub push subscription. Owns the full RAG pipeline (`RAGPipeline` in `pipeline.py`).
- **`services/reranker`** — FastAPI + PyTorch. Loads `ncbi/MedCPT-Cross-Encoder` on startup; scores (query, document) pairs for PubMed-specific re-ranking.
- **`services/verifier`** — FastAPI + PyTorch. Loads `cross-encoder/nli-deberta-v3-large`; classifies each (claim, premise) pair as SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE.

### RAG pipeline (`services/worker/pipeline.py`)

`RAGPipeline.run()` is the single entry point for all queries, executing these steps in order:

1. **Redis cache check** — keyed on raw query text (12h TTL).
2. **`QueryUnderstanding`** — Gemini 2.5 Flash: language detection, translation to English, PICO extraction, intent classification (`research_question | guideline_query | drug_interaction | epidemiology | other`), specialty detection, demographic inference, query expansion.
3. **`HybridRetriever.retrieve()`** — runs Qdrant hybrid search + NCBI live retrieval concurrently; then PMC BioC full-text + Tavily fallback concurrently; merges, deduplicates by PMID, two-tier re-ranks (Cohere → MedCPT), applies weighted scoring, returns top-5.
4. **`Generator.generate()`** — Gemini 2.5 Pro, `temperature=0.0`, structured JSON output enforced via `response_schema`.
5. **`CitationVerifier.verify()`** — NLI entailment > 0.70 threshold; removes unsupported claims; DOI validation via CrossRef (Redis-cached 24h).
6. **Cache write** — stores `HuntAIResponse` in Redis.
7. **`WhatsAppFormatter.format()`** — BLUF structure, message splitting at paragraph boundaries, back-translation to source language if needed.

### Retrieval scoring

Re-ranking uses a multiplicative formula applied in `services/worker/retrieval.py`:

```
final_score = reranker_score × tier_weight × year_multiplier × doc_type_weight × journal_boost
```

- **`TIER_WEIGHTS`**: ICMR/Indian guidelines (1.00) → international guidelines (0.95) → Big 4 journals (0.90) → …
- **`DOC_TYPE_WEIGHTS`**: guideline (1.00) → meta-analysis (0.95) → trial (0.90) → …
- **`YEAR_MULTIPLIERS`**: pre-2020 non-landmark articles score 0.0 (excluded entirely).
- **`_SPECIALTY_JOURNAL_BOOST`** (1.15): applied when the query's detected specialty matches a journal's ISSN.

### Shared layer (`shared/`)

- **`shared/config/settings.py`** — single `Settings` class via pydantic-settings; `get_settings()` is `@lru_cache`. All four services import from here.
- **`shared/models/query.py`** — `QueryMessage` (34 edges in the knowledge graph — the core DTO). Carries raw text, translated text, PICO, intent, specialty, expanded queries, and demographics through the entire pipeline.
- **`shared/models/response.py`** — `HuntAIResponse` + `Citation`. Structured output contract between generator and formatter.
- **`shared/utils/`** — `RedisCache`, `NCBIRateLimiter` (10 req/s token bucket — must wrap every NCBI call), `GeminiClient`, `BGEEmbedder` (lazy-loaded), chunker.

### Ingestion (`services/ingestion/`)

Offline pipeline run manually via `scripts/run_ingestion.py`. Fetches ICMR PDFs from GCS, PubMed abstracts, PMC full-text, and CDSCO drug data; embeds with BGE-M3 (dense 1024-dim + sparse SPLADE); writes to two Qdrant collections: `medical_evidence` and `indian_drugs`.

### Embedding backend

Controlled by `EMBEDDING_BACKEND` env var:
- `"bge"` (default) — `BAAI/bge-m3`, dense + sparse, multilingual, self-hosted, requires GPU for ingestion.
- `"google"` — `text-embedding-004`, dense only, 768-dim, no GPU needed.

### Infrastructure

- `infra/terraform/` — GCP Cloud Run services, Pub/Sub, Cloud Memorystore (Redis), BigQuery.
- `infra/helm/qdrant-values.yaml` — Qdrant self-hosted Helm values (alternative to Qdrant Cloud).

---

## Key env vars

| Variable | Purpose |
|---|---|
| `QDRANT_URL` | Qdrant Cloud URL or `http://localhost:6333` |
| `EMBEDDING_BACKEND` | `bge` or `google` |
| `RERANKER_SERVICE_URL` | Internal URL of the reranker Cloud Run service |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_NUMBER` | Twilio sandbox or production credentials |
| `COHERE_API_KEY` | Primary re-ranker; gracefully skipped if absent |
| `NCBI_API_KEY` | PubMed: 3 req/s without key, 10 req/s with key |
| `TAVILY_API_KEY` | Fallback web search; skipped gracefully if absent |

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
