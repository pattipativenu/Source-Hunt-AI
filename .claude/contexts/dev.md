# Development Mode Context

## Active project: Noocyte.ai

**What we're building:** WhatsApp-native medical evidence retrieval engine for Indian doctors.
**Current sprint:** Week 1-4 build — Core RAG pipeline → WhatsApp integration → Indian data → Launch

**Stack:** Python 3.11, FastAPI, Qdrant Cloud, BGE-M3, Cohere Rerank 3.5, MedCPT, Gemini 2.5 Flash, Meta WhatsApp Cloud API, GCP Cloud Run + Pub/Sub, Redis, Firestore

**Critical constraints:**
- Never generate prescriptive language ("prescribe X", "give the patient X")
- Every factual claim must have an inline citation [N]
- NCBI E-utilities: max 10 req/s (token bucket rate limiter is MANDATORY)
- WhatsApp: 4,096 char limit, split before sending
- Citation [N] in body must map exactly to references[N] list
- Temperature ≤ 0.1 for all medical generation

**Quality bar:** Pass 7/10 OpenEvidence benchmark queries by Week 3.

**Source priority:** ICMR STWs > ACC/AHA/ESC/IDSA > NEJM/Lancet/JAMA > Specialty journals

When writing code, always check: agents/senior-python-engineer.md and agents/senior-ai-engineer.md
