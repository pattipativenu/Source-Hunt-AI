---
name: search-first
description: Use this skill before starting any implementation task that involves unfamiliar APIs, third-party libraries, infrastructure patterns, or technical decisions where the wrong choice wastes days. This skill enforces the research-before-coding discipline: find the right approach first, then implement it. Trigger for: "how should I implement X", "what's the best library for Y", "before I start coding", API integration planning, architecture decisions, library selection. Applies to any technical project.
---

# Search First — Research Before You Code

The most expensive mistake in software development is implementing the wrong approach. An hour of research prevents a week of refactoring.

## The Research Protocol

Before writing any code for a new capability:

### Step 1: Define What You Actually Need

Write down, in plain language:
1. What the input is
2. What the output must be
3. What constraints apply (latency, cost, accuracy, language)
4. What "done" looks like (testable acceptance criteria)

Do this before searching. It stops you from researching the wrong thing.

### Step 2: Find the Authoritative Source

For every technology domain, there is a hierarchy of information quality:

| Source Quality | Examples |
|---|---|
| **Excellent** | Official docs, GitHub README, API reference |
| **Good** | Official blog posts, conference talks by authors |
| **Acceptable** | Recent (< 2 years) tutorials from known engineers |
| **Dangerous** | Stack Overflow (often outdated), generic AI answers |
| **Avoid** | Undated tutorials, Medium articles from 2019 |

For LLM/AI libraries (2025):
- Gemini: [ai.google.dev/docs](https://ai.google.dev/docs)
- Qdrant: [qdrant.tech/documentation](https://qdrant.tech/documentation)
- BGE-M3: [github.com/FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)
- Cohere: [docs.cohere.com](https://docs.cohere.com)
- NCBI E-utilities: [www.ncbi.nlm.nih.gov/books/NBK25497/](https://www.ncbi.nlm.nih.gov/books/NBK25497/)
- Tavily: [docs.tavily.com](https://docs.tavily.com)

### Step 3: Find the Canonical Code Example

Don't read walls of documentation — find the minimal working example. For most libraries:
- GitHub `examples/` folder
- Quickstart in README
- Official Colab notebook

Run the canonical example BEFORE modifying it. Many bugs come from modifying code you don't understand.

### Step 4: Identify Known Limitations

Every library has limitations the docs don't emphasize. Find them:
- GitHub Issues: search "bug", "limitation", "not supported"
- GitHub Discussions: "how do I..." questions reveal what's hard
- README "Known Issues" section

**Specific known limitations to check for Noocyte:**

| Library | Known Limitation |
|---------|-----------------|
| BGE-M3 | 512-token limit on sparse vector queries (use dense for long queries) |
| MedCPT Cross-Encoder | 512 token input max per (query, doc) pair |
| Qdrant Cloud free tier | 500K vectors max; limited collections |
| NCBI E-utilities | 10 req/s with API key; some new articles not yet indexed |
| Tavily | No native date filter; post-filter on published_date |
| Gemini Structured Output | `propertyOrdering` needed to control generation sequence |
| PMC BioC API | Only Open Access articles; ~3M of 37M PubMed articles |

### Step 5: Check for Breaking Changes

Before using any library version, check:
- Is this version still maintained?
- Were there breaking API changes in the last 6 months?
- Is there a newer version I should use instead?

```bash
# Check latest version
pip index versions qdrant-client

# Check recent releases (look for breaking change notes)
# Go to GitHub Releases page
```

---

## Library Selection Framework

When choosing between competing libraries:

| Criterion | Weight | How to Evaluate |
|-----------|--------|-----------------|
| Maintenance activity | High | Commits in last 30 days; response to issues |
| Documentation quality | High | Can you understand it in 10 minutes? |
| Breaking change history | Medium | How often do they break backward compat? |
| Community size | Medium | GitHub stars, Stack Overflow answers |
| License compatibility | Critical | MIT/Apache ≥ GPL ≥ proprietary |
| Production usage examples | High | Who's using it in production? |

---

## Decision Documentation

After research, document your decision before coding. Use this template in a comment or ADR (Architecture Decision Record):

```python
"""
Decision: Use BGE-M3 for document embedding.

Context:
- Need hybrid search (dense + sparse) for Noocyte's RAG pipeline
- Corpus includes Hindi-English mixed medical text (Indian drug names)
- Running on GCP with T4 GPU budget ~$20/month

Options considered:
1. BGE-M3 (BAAI/bge-m3) — MIT license, dense+sparse in one pass, 100+ languages
2. PubMedBERT — English-only, optimized for biomedical but no multilingual support
3. text-embedding-004 (Gemini) — API-based, no GPU needed, dense only

Decision: BGE-M3
Reason: Only model that generates both dense and sparse vectors in one pass,
eliminating need for a separate BM25 encoder. Hindi support is required.
Known limitation: 512-token max for sparse vectors; use dense for long queries.
Reference: https://github.com/FlagOpen/FlagEmbedding/tree/master/research/BGE_M3

Revisit if: Gemini embedding API adds sparse vector support (would save GPU cost).
"""
```

---

## What Not to Do

```python
# ❌ Code first, research later
# Three days of implementation, then discovery that the API doesn't support what you built

# ❌ Using the first Stack Overflow answer from 2021
# Libraries change. The Qdrant API from 2021 is completely different from 2025.

# ❌ Not checking the version
pip install some-library  # Gets latest, might be 0.x alpha that breaks constantly

# ❌ Reading docs without running the example
# You don't understand code you haven't run

# ❌ Researching in isolation, not sharing findings
# Next engineer makes the same research journey — document decisions
```
