# Graph Report - hunt.ai  (2026-04-29)

## Corpus Check
- 45 files · ~34,838 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 355 nodes · 704 edges · 23 communities detected
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 290 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]

## God Nodes (most connected - your core abstractions)
1. `BGEEmbedder` - 42 edges
2. `QueryMessage` - 34 edges
3. `HuntAIResponse` - 26 edges
4. `QdrantWriter` - 23 edges
5. `PubMedFetcher` - 20 edges
6. `RAGPipeline` - 17 edges
7. `HybridRetriever` - 17 edges
8. `DocumentChunk` - 16 edges
9. `Citation` - 16 edges
10. `QueryUnderstanding` - 16 edges

## Surprising Connections (you probably didn't know these)
- `QueryMessage` --uses--> `Twilio WhatsApp webhook receiver.  Twilio sends an HTTP POST with form fields wh`  [INFERRED]
  shared/models/query.py → services/webhook/main.py
- `QueryMessage` --uses--> `Receive inbound WhatsApp message from Twilio, ACK immediately, queue for process`  [INFERRED]
  shared/models/query.py → services/webhook/main.py
- `QueryMessage` --uses--> `Twilio delivery status callback — log and acknowledge.`  [INFERRED]
  shared/models/query.py → services/webhook/main.py
- `get_settings()` --calls--> `migrate()`  [INFERRED]
  shared/config/settings.py → scripts/migrate_firestore_to_qdrant.py
- `get_settings()` --calls--> `_validate_search()`  [INFERRED]
  shared/config/settings.py → scripts/migrate_firestore_to_qdrant.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (46): _cdsco_drug_to_text(), DrugIngestion, _medicine_to_text(), _parse_cdsco_json(), _parse_csv(), Indian drug data ingestion into Qdrant.  Two data sources:   1. Indian Medicine, Export brand→generic mappings for use in query_understanding.py.         Returns, Ingest CDSCO (Central Drugs Standard Control Organisation) approved drug list. (+38 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (37): Citation, HuntAIResponse, Pydantic models for Hunt AI structured response output. Gemini 1.5 Pro is instru, main(), Offline evaluation harness for Hunt AI (ARES-adapted).  Metrics:   - Citation Re, run_evaluation(), CitationVerifier, _extract_journal() (+29 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (27): _convert_pmids_to_pmcids(), _fetch_bioc_article(), _parse_bioc_xml(), PMCFetcher, PMC BioC full-text fetcher for open-access articles.  PMC's BioC API provides st, Parse BioC XML into a structured article dict with labeled sections.      BioC s, Fetches full-text open-access articles from PMC via:     1. PMC ID conversion (P, Given PubMed IDs, convert to PMCIDs, fetch full-text, extract key sections. (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (14): _mask_spans(), Structure-aware chunker for parsed markdown documents (ICMR PDFs via Marker).  R, Produce overlapping character windows over prose text., Infer chapter/section from heading depth., Split a full markdown document into overlapping chunks.         Tables are extra, Replace table spans with blank lines so heading detection still works., Return list of (heading_line, block_text) tuples., _sliding_window() (+6 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (20): _generate_gemini(), Hunt AI — Reranker Playground Dashboard  Run locally:     cd /Users/admin/Docume, Generate an answer using Gemini via Vertex AI ADC. Returns {answer, latency_ms,, Generate an answer using Gemini. Returns {answer, latency_ms, error}., BenchmarkQuery, get_queries_by_difficulty(), OpenEvidence 10-query benchmark set for Hunt AI playground.  Each query includes, Filter benchmark queries by difficulty level. (+12 more)

### Community 5 - "Community 5"
Cohesion: 0.18
Nodes (15): PICOElements, QueryDemographics, Pydantic models for incoming queries and intermediate query state., Demographic signals extracted from the query for PubMed filtering., _detect_guideline_body(), _expand_query(), _preprocess(), Query understanding layer.  Pipeline (in order):   0. Preprocess (whitespace nor (+7 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (11): BaseModel, MedCPT Cross-Encoder reranker service.  Deployed as a dedicated Cloud Run servic, # NOTE: .set_eval_mode() is a PyTorch method that disables dropout/batch-norm, rerank(), RerankRequest, RerankResponse, DeBERTa NLI citation verifier service.  Deployed as CPU-only Cloud Run service (, verify() (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (8): pubsub_push(), Worker Cloud Run service entry point.  Receives Pub/Sub push messages from the h, Handle Pub/Sub push subscription messages., Twilio WhatsApp message sender.  Uses Twilio REST API to send response parts bac, Send a plain text WhatsApp message., Send multiple message parts sequentially., Send an immediate ACK message while pipeline runs., WhatsAppSender

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (12): detect_language(), Fast language detection for incoming WhatsApp messages.  Uses langdetect with a, Detect the language of a text string.     Returns a BCP-47 language code (e.g.,, _publish_message(), Twilio WhatsApp webhook receiver.  Twilio sends an HTTP POST with form fields wh, Twilio delivery status callback — log and acknowledge., Receive inbound WhatsApp message from Twilio, ACK immediately, queue for process, twilio_status() (+4 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (9): BaseSettings, get_settings(), Centralised configuration via Pydantic Settings. All secrets are read from envir, Settings, get_gemini_model(), make_generation_config(), Gemini client factory.  Supports two auth modes controlled by GEMINI_USE_VERTEX:, Return a Vertex AI GenerativeModel using ADC. Lazy-imports to keep startup fast. (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.21
Nodes (6): _cosine_similarity(), Redis cache wrapper for: - Semantic query cache (embedding cosine similarity ≥ 0, Store query embedding + response for semantic cache lookup., Brute-force cosine similarity over candidate keys.         For production, repla, RedisCache, _sha256()

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (5): GoogleEmbedder, Google text-embedding-004 embedder (alternative to BGE-M3).  Advantages over BGE, Async wrapper around Vertex AI text embedding API using ADC., Embed a batch of texts. Returns dense vectors only (no sparse).         task_typ, Embed a single query with the RETRIEVAL_QUERY task type.

### Community 12 - "Community 12"
Cohesion: 0.25
Nodes (7): log_with_context(), Structured Cloud Logging integration.  On GCP (Cloud Run), this configures the s, Log a message with structured context fields.      Usage:         log_with_conte, Formats log records as JSON objects that Cloud Logging parses natively.     Clou, Configure structured logging for the service.      On Cloud Run (K_SERVICE env v, setup_logging(), _StructuredFormatter

### Community 13 - "Community 13"
Cohesion: 0.48
Nodes (6): all_skill_files(), extract_yaml_frontmatter(), main(), Extract the first YAML frontmatter block:      ---     <yaml>     ---, staged_skill_files(), validate_skill_file()

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Use NCBI ID Converter API to map PMIDs → PMCIDs.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Fetch and parse a single article from PMC BioC API.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Return a Gemini GenerativeModel instance using the appropriate SDK.     Lazy-imp

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Google AI Studio path — uses GEMINI_API_KEY.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Vertex AI path — uses Application Default Credentials.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Build a GenerationConfig compatible with both SDK paths.     Both SDKs accept th

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Async wrapper around Google Generative AI text embedding API.     Uses GEMINI_AP

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Embed a batch of texts. Returns dense vectors only (no sparse).         task_typ

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Embed a single query with the RETRIEVAL_QUERY task type.

## Knowledge Gaps
- **64 isolated node(s):** `Centralised configuration via Pydantic Settings. All secrets are read from envir`, `Structure-aware chunker for parsed markdown documents (ICMR PDFs via Marker).  R`, `Split a full markdown document into overlapping chunks.         Tables are extra`, `Replace table spans with blank lines so heading detection still works.`, `Return list of (heading_line, block_text) tuples.` (+59 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 18`** (1 nodes): `Use NCBI ID Converter API to map PMIDs → PMCIDs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Fetch and parse a single article from PMC BioC API.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Return a Gemini GenerativeModel instance using the appropriate SDK.     Lazy-imp`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Google AI Studio path — uses GEMINI_API_KEY.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Vertex AI path — uses Application Default Credentials.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Build a GenerationConfig compatible with both SDK paths.     Both SDKs accept th`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Async wrapper around Google Generative AI text embedding API.     Uses GEMINI_AP`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Embed a batch of texts. Returns dense vectors only (no sparse).         task_typ`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Embed a single query with the RETRIEVAL_QUERY task type.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QueryMessage` connect `Community 2` to `Community 1`, `Community 5`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.225) - this node is a cross-community bridge._
- **Why does `BGEEmbedder` connect `Community 0` to `Community 2`, `Community 3`?**
  _High betweenness centrality (0.180) - this node is a cross-community bridge._
- **Why does `HybridRetriever` connect `Community 2` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `BGEEmbedder` (e.g. with `Migrate existing ICMR embeddings from Firestore → Qdrant Cloud.  Context (from b` and `Spot-check retrieval quality with known ICMR queries.`) actually correct?**
  _`BGEEmbedder` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `QueryMessage` (e.g. with `Offline evaluation harness for Hunt AI (ARES-adapted).  Metrics:   - Citation Re` and `Twilio WhatsApp webhook receiver.  Twilio sends an HTTP POST with form fields wh`) actually correct?**
  _`QueryMessage` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `HuntAIResponse` (e.g. with `WhatsAppFormatter` and `WhatsApp response formatter.  - Converts structured HuntAIResponse to WhatsApp m`) actually correct?**
  _`HuntAIResponse` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `QdrantWriter` (e.g. with `One-shot ingestion script for bootstrapping the Qdrant collection.  Runs:   1. C` and `Migrate existing ICMR embeddings from Firestore → Qdrant Cloud.  Context (from b`) actually correct?**
  _`QdrantWriter` has 19 INFERRED edges - model-reasoned connections that need verification._