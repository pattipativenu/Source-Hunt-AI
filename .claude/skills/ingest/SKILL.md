---
name: ingest
description: Run the Hunt AI knowledge base ingestion pipeline. Use when adding new ICMR guidelines, PubMed articles, or CDSCO drug data to the Qdrant vector store.
argument-hint: "[source: icmr|pubmed|cdsco|all] [--query 'search terms'] [--limit N]"
disable-model-invocation: true
context: fork
allowed-tools: Bash, Read, Glob
---

# Hunt AI — Ingestion Pipeline

Run the knowledge base ingestion for Hunt AI. The ingestion pipeline fetches, parses, embeds, and writes chunks to Qdrant.

## Arguments
`$ARGUMENTS` — source selection and options. Examples:
- `/ingest icmr` — ingest ICMR guidelines from GCS bucket
- `/ingest pubmed --query "MDR tuberculosis India"` — ingest PubMed articles
- `/ingest cdsco` — ingest CDSCO drug database
- `/ingest all` — run all three sources sequentially
- `/ingest` (no args) — show status and available sources

## Steps

1. **Check environment** — verify `.env` exists and required vars are set:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 -c "from shared.config.settings import get_settings; s = get_settings(); print('Config OK — Qdrant:', s.qdrant_url)"
   ```

2. **Run ingestion** based on `$ARGUMENTS`:

   For `icmr` or `all`:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 scripts/run_ingestion.py --source icmr
   ```

   For `pubmed`:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 scripts/run_ingestion.py --source pubmed $ARGUMENTS
   ```

   For `cdsco`:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 scripts/run_ingestion.py --source cdsco
   ```

   For `all`:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 scripts/run_ingestion.py --source icmr && \
   python3 scripts/run_ingestion.py --source cdsco && \
   python3 scripts/run_ingestion.py --source pubmed --query "India clinical guidelines"
   ```

3. **Verify** — check chunk count in Qdrant after ingestion:
   ```bash
   cd /Users/admin/Documents/hunt.ai
   python3 -c "
   from qdrant_client import QdrantClient
   from shared.config.settings import get_settings
   s = get_settings()
   c = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)
   for col in [s.qdrant_collection_guidelines, s.qdrant_collection_drugs]:
       try:
           info = c.get_collection(col)
           print(f'{col}: {info.vectors_count:,} vectors')
       except Exception as e:
           print(f'{col}: {e}')
   "
   ```

4. **Report** the number of chunks ingested per source and any errors encountered.

## Key files
- `scripts/run_ingestion.py` — CLI entry point
- `services/ingestion/icmr_parser.py` — PDF parsing (Marker ML + PyMuPDF4LLM fallback)
- `services/ingestion/pubmed_fetcher.py` — NCBI E-utilities
- `services/ingestion/pmc_fetcher.py` — PMC BioC full-text API
- `services/ingestion/drug_ingestion.py` — CDSCO drug database (tier=1)
- `services/ingestion/embedder.py` — BGE-M3 dense+sparse embedding
- `services/ingestion/qdrant_writer.py` — Qdrant upsert

## Common issues
- **NCBI rate limit**: Add `NCBI_API_KEY` to `.env` for 10 req/s (vs 3 req/s)
- **Marker not installed**: icmr_parser falls back to PyMuPDF4LLM automatically
- **Qdrant connection failed**: Check `QDRANT_URL` and `QDRANT_API_KEY` in `.env`
- **GCS permission denied**: Run `gcloud auth application-default login` for ICMR bucket access
