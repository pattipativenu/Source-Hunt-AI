# Noocyte — Always-On Development Rules

These rules apply to every coding session. They are not optional and do not require activation.

---

## Medical Safety Rules (Non-Negotiable)

1. **Never generate prescriptive language.** The system must never output: "prescribe X", "give the patient X", "administer X", "start the patient on X". Always attribute: "Guidelines recommend X [N]".

2. **Every factual claim requires an inline citation.** Statistical claims (percentages, hazard ratios, p-values) must be traceable to a specific source. No bare assertions.

3. **PII must be redacted before logging.** Any log statement that could contain patient information must be wrapped in `redact_pii()`. Phone numbers, Aadhaar numbers, patient names must never appear in logs.

4. **Emergency queries get immediate safety warnings.** Before any evidence retrieval, check for emergency keywords. If detected, prepend emergency message with "Call 108" before evidence.

5. **Citation numbers [N] must be 1-indexed and sequential.** [1] in body text maps to reference [1]. No orphaned citations. No unused references.

---

## Code Quality Rules

6. **All external API calls must have a timeout.** No uncapped network requests. Minimum: `timeout=10.0` for all httpx/requests calls.

7. **NCBI E-utilities: maximum 10 requests/second.** The `NCBIRateLimiter` token bucket must be used before every NCBI API call. Violating this risks IP ban.

8. **Temperature ≤ 0.1 for all factual generation.** No exceptions for medical content. Higher temperature = hallucination risk.

9. **Structured JSON output is enforced.** `response_mime_type: "application/json"` with a `response_schema` on every Gemini call that returns citations.

10. **Retrieve 50 candidates, rerank to 5.** Never retrieve only 3-5 directly. The retrieve-then-rerank architecture is mandatory. Low retrieval count = low recall.

---

## Human-Only Filter Rule

11. **All PubMed queries must exclude animal studies.** Use the double-negative pattern:
```
NOT (animals[MeSH] NOT humans[MeSH])
```
Not just `AND Humans[MeSH]` — this misses non-MEDLINE human studies.

---

## Error Handling Rules

12. **`except Exception` without re-raising is banned.** Silent failures hide bugs. Either handle specifically and log, or catch and re-raise. Never swallow.

13. **Graceful degradation on every external dependency.** If Cohere is down: skip reranking, return raw Qdrant scores. If Tavily is down: proceed without live web results. If Gemini is rate-limited: queue and retry. Never crash the response pipeline.

14. **Dead letter queue for failed WhatsApp messages.** If the RAG worker fails after 3 retries, store in Redis DLQ for manual review. Never silently drop a doctor's query.

---

## Testing Rules

15. **New functions without tests are blocked.** Every new function must have at least one unit test for the happy path and one for each error case.

16. **External APIs must be mocked in tests.** No real API calls in unit or integration tests. Use `unittest.mock` or `pytest-mock`.

17. **The 10-query OpenEvidence benchmark must pass.** Any change to the RAG pipeline, prompt, or retrieval strategy must re-run the benchmark before merge.
