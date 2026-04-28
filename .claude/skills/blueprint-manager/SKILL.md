---
name: blueprint-manager
description: >
  Maintain and enforce the Noocyte AI Technical Blueprint as the single source
  of truth for all architectural decisions. Use when reviewing new features,
  resolving architectural disagreements, checking sprint milestone gates, or
  validating that proposed changes align with the 4-week sprint plan and
  defined data flow. Prevents scope creep and cost overruns.
argument-hint: "<proposed change or feature description>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Blueprint Manager

## Purpose

Every project needs a single source of truth. For Noocyte AI, that is the Technical Blueprint. This skill ensures that every architectural decision — every API choice, every data flow change, every new dependency — is evaluated against the blueprint before it is implemented.

This skill is especially important for a non-technical founder. It gives you a clear framework to evaluate technical proposals without needing a computer science background: if it's in the blueprint, it's approved; if it's not, it needs justification.

---

## The Noocyte AI Architecture (Single Source of Truth)

```
INBOUND:
WhatsApp User Message
        ↓
Meta Cloud API (Webhook)
        ↓
FastAPI Webhook Handler (Cloud Run)
        ↓
Google Cloud Pub/Sub (message queue)
        ↓
Worker Service (Cloud Run)

QUERY PROCESSING:
        ↓
[1] Emergency Keyword Check → if emergency: return 108 message immediately
        ↓
[2] PII Redaction → remove Aadhaar, phone, patient names
        ↓
[3] Indian Context Resolution → brand→INN, Hinglish normalization
        ↓
[4] Query Understanding → PICO extraction, intent classification
        ↓
[5] Parallel Retrieval:
    ├── Qdrant (ICMR + guidelines, pre-indexed)
    ├── PubMed E-utilities (live, rate-limited)
    └── Tavily (only if Qdrant < 3 results OR query < 90 days old)
        ↓
[6] Two-Tier Reranking:
    ├── Cohere Rerank 3.5 (50 candidates → 10)
    └── MedCPT Cross-Encoder (10 candidates → 5)
        ↓
[7] Context Assembly (lost-in-the-middle mitigation, source priority)
        ↓
[8] Gemini 2.5 Flash (structured JSON generation, temperature=0.0)
        ↓
[9] Citation Verification (NLI entailment > 0.7, DOI validation via CrossRef)
        ↓
[10] WhatsApp Formatter (BLUF structure, message splitting, buttons)
        ↓
Meta Cloud API (send response)
        ↓
OUTBOUND: WhatsApp Response to Doctor
```

---

## Source Priority Hierarchy (Enforced in Context Assembly)

```python
SOURCE_PRIORITY = {
    1: "ICMR Standard Treatment Workflows",
    2: "Indian specialty society guidelines (CSI, RSSDI, ISN India, IAP, ISG, ISI)",
    3: "International guidelines (ACC/AHA, ESC, IDSA, ADA, KDIGO, NCCN, ASCO)",
    4: "Flagship general journals (NEJM, Lancet, JAMA, BMJ)",
    5: "Specialty journals (Circulation, JACC, JCO, etc.)",
    6: "Meta-analyses and systematic reviews (Cochrane)",
    7: "Individual RCTs in peer-reviewed journals",
    8: "Expert reviews and cohort studies",
}

# For India-specific conditions (TB, dengue, malaria, etc.):
# Priority 1 (ICMR) is MANDATORY — must appear before any international guideline
```

---

## The Approved Technology Stack

```python
APPROVED_STACK = {
    # Infrastructure
    "cloud_provider": "Google Cloud Platform",
    "compute": "Cloud Run (serverless containers)",
    "message_queue": "Google Cloud Pub/Sub",
    "vector_database": "Qdrant (self-hosted on Cloud Run)",
    "cache": "Redis (Cloud Memorystore)",
    "analytics": "BigQuery",
    "storage": "Google Cloud Storage",
    
    # AI/ML
    "primary_llm": "Gemini 2.5 Flash",
    "fallback_llm": "Gemini 2.5 Pro (complex generation only)",
    "embedding_model": "BAAI/BGE-M3",
    "reranker_1": "Cohere Rerank 3.5",
    "reranker_2": "ncats/MedCPT-Cross-Encoder",
    "nli_model": "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",
    
    # Data Sources
    "primary_knowledge_base": "Qdrant (ICMR + guidelines)",
    "live_search": "PubMed E-utilities (NCBI API)",
    "fallback_search": "Tavily (recent/missing content only)",
    
    # Messaging
    "whatsapp_api": "Meta Cloud API (WhatsApp Business Platform)",
    
    # Backend
    "api_framework": "FastAPI",
    "language": "Python 3.11+",
    "async_framework": "asyncio + httpx",
}
```

---

## The 4-Week Sprint Plan (Milestone Gates)

```python
SPRINT_MILESTONES = {
    "week_1": {
        "goal": "Core RAG pipeline working end-to-end",
        "gate": "4/10 benchmark queries pass",
        "deliverables": [
            "Qdrant collection with ICMR guidelines indexed",
            "PubMed E-utilities integration",
            "Cohere + MedCPT two-tier reranking",
            "Gemini 2.5 Flash generating structured JSON",
            "Citation verifier (NLI > 0.7)",
        ],
    },
    "week_2": {
        "goal": "WhatsApp integration working end-to-end",
        "gate": "5/10 benchmark queries pass + WhatsApp round-trip < 10s",
        "deliverables": [
            "Meta Cloud API webhook integration",
            "WhatsApp formatter (BLUF, message splitting, buttons)",
            "Redis semantic caching",
            "Emergency detection",
            "PII redaction in all logs",
        ],
    },
    "week_3": {
        "goal": "India-aware responses",
        "gate": "7/10 benchmark queries pass",
        "deliverables": [
            "Indian drug brand dictionary (100+ entries)",
            "Hinglish normalization",
            "ICMR source priority enforcement",
            "India-specific context injection",
        ],
    },
    "week_4": {
        "goal": "Production-ready soft launch",
        "gate": "9/10 benchmark queries pass + Meta Business Verification approved",
        "deliverables": [
            "Meta Business Verification approved",
            "5+ doctors tested and provided feedback",
            "Zero hallucinated statistics in last 50 test queries",
            "Monitoring and alerting configured",
            "Privacy policy published",
        ],
    },
}
```

---

## The V2 Deferred Features List

These features are explicitly **not** in the MVP. Reject any implementation attempt during the 4-week sprint:

```python
V2_DEFERRED = [
    "Multi-language UI output (Hindi, Tamil, Telugu)",
    "Voice note input (Whisper/Bhashini)",
    "Image/scan analysis (lab reports, X-rays, ECGs)",
    "Patient-specific dosing calculators",
    "Conversation history search",
    "Doctor NMC verification",
    "MiniCheck deployment (replace NLI verifier)",
    "Differential diagnosis tool",
    "DotFlows-style reusable commands",
    "Drug-drug interaction checker",
    "Lab value interpretation",
    "Prescription generation",
    "Telemedicine integration",
]
```

---

## Blueprint Review Decision Framework

```
Proposed change: [description]

Step 1: Is it in the approved technology stack?
  YES → Continue to Step 2
  NO  → REJECTED unless there is a compelling reason (document it)

Step 2: Does it follow the defined data flow (steps 1-10)?
  YES → Continue to Step 3
  NO  → FLAGGED — specify which step it violates and how to fix it

Step 3: Is it in the 4-week sprint plan?
  YES → APPROVED
  NO  → Is it in the V2 deferred list?
    YES → REJECTED — log to v2 backlog
    NO  → FLAGGED — needs blueprint amendment before implementation

Step 4: Does it add a new external dependency?
  YES → Cost impact analysis required before approval
  NO  → APPROVED
```

---

## How to Use This Skill

**Before starting any new feature:**
1. Describe the feature in plain language
2. Apply the Decision Framework above
3. If APPROVED: proceed with implementation
4. If FLAGGED: make the specified correction, then re-apply the framework
5. If REJECTED: add to the v2 backlog and stop

**When reviewing a PR:**
1. Check the data flow — does the code follow steps 1-10?
2. Check the technology stack — are all dependencies approved?
3. Check the sprint milestone — does this contribute to the current week's gate?

---

*The blueprint is the contract. Every line of code is a commitment to that contract.*
