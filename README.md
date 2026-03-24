# Hunt AI 🩺

> **WhatsApp-native, evidence-first medical RAG for Indian doctors.**
> Ask a clinical question on WhatsApp → get a cited, NLI-verified answer grounded in ICMR guidelines, PubMed, PMC full-text, and the CDSCO drug database — in seconds.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
- [Data Sources & Evidence Tiers](#data-sources--evidence-tiers)
- [Hallucination Prevention (LEAD-Inspired)](#hallucination-prevention-lead-inspired)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Deployment (GCP)](#deployment-gcp)
- [Ingestion Pipeline](#ingestion-pipeline)
- [Evaluation](#evaluation)
- [Project Structure](#project-structure)
- [License](#license)

---

## Overview

Hunt AI is a production-grade medical question-answering system built as a WhatsApp chatbot for Indian physicians. It combines:

- **Hybrid vector search** over a curated knowledge base (Qdrant, BGE-M3 dense + sparse)
- **Live PubMed / PMC retrieval** for breaking research
- **Two-tier reranking** — Cohere Rerank 3.5 (multilingual) → MedCPT Cross-Encoder (PubMed-specific)
- **Gemini 2.5 Pro generation** with LEAD-inspired entropy-aware prompting
- **NLI citation verification** per claim before any answer reaches the doctor
- **Indian clinical context** — ICMR guidelines at top priority, CDSCO drug schedules, local epidemiology

```
Doctor on WhatsApp
      │  "What's the first-line treatment for MDR-TB in adults?"
      ▼
Twilio → Webhook → Pub/Sub → Worker (RAG Pipeline) → Twilio → Doctor
                                     │
                    ┌────────────────┼───────────────────┐
                    ▼                ▼                   ▼
              Query             Retrieval           Generation
             Understanding    (3 parallel          (Gemini 2.5 Pro
           (translate,         sources)             + citation NLI)
            PICO, intent)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WhatsApp / Twilio                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ POST /webhook
┌──────────────────────────▼──────────────────────────────────────┐
│  Webhook Service (Cloud Run, :8080)                             │
│  • Twilio signature validation                                  │
│  • Language detection (BCP-47, 40+ languages)                  │
│  • Redis deduplication (2-hour window, SHA-256 key)            │
│  • Pub/Sub publish → hunt-ai-queries topic                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Pub/Sub push
┌──────────────────────────▼──────────────────────────────────────┐
│  Worker Service (Cloud Run, :8083)                              │
│                                                                 │
│  1. Query Understanding                                         │
│     ├─ Translate to English (Gemini Flash)                      │
│     ├─ Intent: drug_lookup | guideline_query | research_        │
│     │         question | drug_interaction | epidemiology        │
│     ├─ PICO extraction (Population, Intervention,               │
│     │   Comparison, Outcome) — 5-shot Gemini                   │
│     └─ Query expansion (abbrevs, synonyms, brand→generic)       │
│                                                                 │
│  2. Hybrid Retrieval (parallel)                                 │
│     ├─ Qdrant hybrid search (dense + sparse RRF, BGE-M3)       │
│     ├─ NCBI E-utilities live PubMed fetch                       │
│     ├─ PMC BioC full-text API (open-access articles)           │
│     └─ Tavily fallback (if NCBI < 5 results ≥ 2023)           │
│                                                                 │
│  3. Two-Tier Reranking                                          │
│     ├─ Cohere Rerank 3.5 (multilingual, 50 docs → top 15)     │
│     └─ MedCPT Cross-Encoder (PubMed-specific, 15 → top 5)     │
│                                                                 │
│  4. Generation                                                  │
│     └─ Gemini 2.5 Pro (entropy-aware prompting, JSON-mode)     │
│                                                                 │
│  5. Citation Verification (LEAD-inspired)                       │
│     ├─ Claim extraction (Gemini Flash atomic claims)           │
│     ├─ Adaptive NLI depth (deep for low-confidence claims)     │
│     ├─ Evidence re-grounding (find better source if failed)    │
│     ├─ DOI validation via CrossRef API (24h Redis cache)       │
│     └─ Strip contradicted citations from final answer          │
│                                                                 │
│  6. Redis cache (12h TTL) + WhatsApp formatting + pagination   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
      ┌────────────────────▼────────────────────────┐
      │  Reranker Service (Cloud Run, :8001)         │
      │  MedCPT Cross-Encoder (GPU T4 optional)     │
      └─────────────────────────────────────────────┘
```

---

## Services

| Service | Port | Purpose | Key Tech |
|---------|------|---------|---------|
| **Webhook** | 8080 | Twilio WhatsApp entry point | FastAPI, Twilio, Pub/Sub |
| **Worker** | 8083 | Core RAG pipeline | FastAPI, Gemini, Qdrant, Cohere |
| **Reranker** | 8001 | MedCPT cross-encoder scoring | FastAPI, HuggingFace Transformers |
| **Verifier** | 8002 | DeBERTa NLI (upgrade path) | FastAPI, DeBERTa-v3-large |
| **Dashboard** | 8501 | Dev metrics & reranker playground | Streamlit |
| **Redis** | 6379 | Response cache, DOI cache, dedup | Redis 7 |

---

## Data Sources & Evidence Tiers

Hunt AI scores each retrieved chunk with a **tier weight × temporal multiplier**:

| Tier | Sources | Weight | Examples |
|------|---------|--------|---------|
| 1 | Official Indian guidelines | 1.00 | ICMR, CDSCO drug schedules |
| 2 | Cochrane, major guidelines | 0.95 | Cochrane Reviews, WHO, NICE |
| 3 | High-impact journals | 0.90 | NEJM, Lancet, JAMA, BMJ |
| 4 | PubMed RCTs / Systematic reviews | 0.80 | PubMed Live, PMC full-text |
| 5 | Observational studies | 0.70 | Cohort, case-control |
| 6 | Preprints | 0.60 | bioRxiv, medRxiv |

**Temporal multipliers** (publication year → score multiplier):
- 2025 → 1.00 · 2024 → 0.98 · 2023 → 0.94 · 2022 → 0.88 · 2021 → 0.80 · 2020 → 0.70
- Pre-2020 articles only included if flagged as landmark references

**PMC Full-Text** (via BioC XML API): Open-access articles are fetched at the full-text level with priority-ordered section extraction (Results → Discussion → Conclusions → Methods), replacing their abstract in the retrieval pool for the same PMID.

---

## Hallucination Prevention (LEAD-Inspired)

Hunt AI adapts ideas from the [LEAD paper](https://arxiv.org/abs/2603.13366) (Latent Entropy-Aware Decoding) to a text-based RAG setting:

| LEAD Concept | Hunt AI Adaptation |
|---|---|
| Token entropy → latent mode | Self-assessed claim confidence in generation prompt |
| Visual anchor injection | Evidence re-grounding: re-read source when uncertain |
| High-entropy transition words | Claim transition re-anchoring to citation markers |
| Discrete mode = confirmed reasoning | Deep NLI verification for `self_confidence: LOW` claims |
| Max switch count | Citation stripping for CONTRADICTED claims |

The pipeline produces **three confidence levels**:
- `HIGH` — ≥2 RCTs or meta-analyses from tier 1–3 sources
- `MODERATE` — 1 RCT/systematic review, or strong observational data
- `LOW` — Case reports, expert opinion, or insufficient evidence

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- GCP project with Pub/Sub, Cloud Run, Cloud Storage enabled
- [Twilio account](https://console.twilio.com) (WhatsApp sandbox or production)
- [Qdrant Cloud](https://cloud.qdrant.io) account (free tier: 500K chunks)
- [Gemini API key](https://aistudio.google.com/app/apikey) (or Vertex AI)

### 1. Clone and configure

```bash
git clone <repo-url> hunt.ai
cd hunt.ai
cp .env.local .env
# Edit .env with your credentials (see Environment Variables below)
```

### 2. Start the dev stack

```bash
docker-compose up --build
```

Or run services individually with Python (from project root):

```bash
# Redis (required first)
redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru

# Webhook
python3 -m uvicorn services.webhook.main:app --port 8080 --reload

# Worker
python3 -m uvicorn services.worker.main:app --port 8083 --reload

# Reranker
python3 -m uvicorn services.reranker.main:app --port 8001 --reload
```

### 3. Expose webhook for Twilio

```bash
ngrok http 8080
# Set https://<ngrok-url>/webhook as Twilio WhatsApp sandbox webhook URL
```

### 4. Run ingestion

```bash
python scripts/run_ingestion.py --source icmr
python scripts/run_ingestion.py --source pubmed --query "diabetes mellitus India"
python scripts/run_ingestion.py --source cdsco
```

---

## Environment Variables

Copy `.env.local` → `.env` and fill in all required values:

```bash
# ── Required ──────────────────────────────────────────────────────
GCP_PROJECT_ID=your-gcp-project-id
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# ── Gemini (choose one auth mode) ────────────────────────────────
GEMINI_API_KEY=AIza...               # Google AI Studio
# OR
GEMINI_USE_VERTEX=true               # Vertex AI (uses gcloud ADC)

# ── Vector DB ────────────────────────────────────────────────────
QDRANT_URL=https://xxx.qdrant.io
QDRANT_API_KEY=your_qdrant_key

# ── Optional but recommended ─────────────────────────────────────
COHERE_API_KEY=...                   # Tier-1 reranker (multilingual)
NCBI_API_KEY=...                     # 10 req/s vs 3 req/s without key
TAVILY_API_KEY=...                   # Web fallback retrieval
GCP_REGION=asia-south1               # Default: asia-south1 (Mumbai)
```

**Full variable reference:** see `shared/config/settings.py`

---

## Development

### Run tests

```bash
pytest tests/ -v
```

### Dashboard (reranker playground + metrics)

```bash
python3 -m streamlit run scripts/dashboard/app.py --server.port 8501
# Open http://localhost:8501
```

### Evaluate pipeline quality

```bash
python scripts/evaluate.py --benchmark golden_set.jsonl --top-k 5
```

---

## Deployment (GCP)

Hunt AI runs on **Google Cloud Run** (fully managed, auto-scaling to zero):

```bash
# Build and push all service images
docker build -f docker/Dockerfile.webhook -t gcr.io/$PROJECT/hunt-webhook .
docker build -f docker/Dockerfile.worker  -t gcr.io/$PROJECT/hunt-worker .
docker build -f docker/Dockerfile.reranker -t gcr.io/$PROJECT/hunt-reranker .
docker push gcr.io/$PROJECT/hunt-webhook
docker push gcr.io/$PROJECT/hunt-worker
docker push gcr.io/$PROJECT/hunt-reranker

# Deploy (example for webhook)
gcloud run deploy hunt-webhook \
  --image gcr.io/$PROJECT/hunt-webhook \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=$PROJECT \
  --set-secrets TWILIO_ACCOUNT_SID=twilio-sid:latest,...
```

Infrastructure-as-Code (Terraform + Helm for Qdrant) is in `infra/`.

---

## Ingestion Pipeline

The knowledge base is built from four sources:

| Source | Script | Collection |
|--------|--------|-----------|
| ICMR guidelines (PDFs from GCS) | `run_ingestion.py --source icmr` | `medical_evidence` |
| PubMed / PMC articles | `run_ingestion.py --source pubmed` | `medical_evidence` |
| CDSCO drug database | `run_ingestion.py --source cdsco` | `indian_drugs` |
| Legacy Firestore migration | `scripts/migrate_firestore_to_qdrant.py` | `medical_evidence` |

**Embedding:** BAAI/BGE-M3 (dense 1024-dim + sparse SPLADE) — set `EMBEDDING_BACKEND=bge` (default).
**Fallback:** Google `text-embedding-004` (dense 768-dim only) — set `EMBEDDING_BACKEND=google`.

---

## Project Structure

```
hunt.ai/
├── services/
│   ├── webhook/          # Twilio WhatsApp entry point
│   │   ├── main.py       # FastAPI + deduplication + Pub/Sub publish
│   │   ├── language_detector.py
│   │   └── signature_validator.py
│   ├── worker/           # Core RAG pipeline
│   │   ├── main.py       # Pub/Sub consumer + Twilio reply
│   │   ├── pipeline.py   # Orchestrates all pipeline stages
│   │   ├── query_understanding.py  # Translate, PICO, intent, expand
│   │   ├── retrieval.py  # Qdrant + NCBI + PMC + Tavily + reranking
│   │   ├── generation.py # Gemini 2.5 Pro structured generation
│   │   ├── citation_verifier.py  # NLI per-claim verification
│   │   └── formatter.py  # WhatsApp markdown + pagination
│   ├── reranker/         # MedCPT Cross-Encoder service
│   ├── verifier/         # DeBERTa NLI service (upgrade path)
│   └── ingestion/        # Batch knowledge base builder
│       ├── pubmed_fetcher.py
│       ├── pmc_fetcher.py
│       ├── drug_ingestion.py
│       ├── icmr_parser.py
│       ├── embedder.py
│       └── qdrant_writer.py
├── shared/
│   ├── config/settings.py  # Pydantic BaseSettings (all env vars)
│   ├── models/             # QueryMessage, HuntAIResponse, Citation
│   └── utils/              # cache.py, chunker.py, cloud_logging.py,
│                           # gemini_client.py, rate_limiter.py
├── scripts/
│   ├── run_ingestion.py
│   ├── evaluate.py
│   └── dashboard/app.py
├── docker/                 # Dockerfiles per service
├── infra/                  # Terraform + Helm
├── docker-compose.yml
└── .env.local              # Template for environment variables
```

---

## License

MIT License © 2026 pattipativenu
