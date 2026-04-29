---
name: ncbi-pubmed
description: >-
  Use this skill whenever you integrate with NCBI E-utilities for PubMed searches, fetch biomedical literature, retrieve PubMed Central full-text via BioC API, build MeSH-based search strategies, handle NCBI rate limits, or work with PMID/PMCID/DOI resolution. Trigger on: PubMed, NCBI, E-utilities, biomedical search, MeSH, ESearch, EFetch, PMC, BioC API, medical literature retrieval.
---

# NCBI PubMed Integration

PubMed is the gold standard for biomedical literature. It indexes 37M+ citations with structured metadata, human-assigned MeSH terms, and publication type classification. The E-utilities API gives programmatic access to all of it — but has strict rate limits and nuanced behaviour you must know before building against it.

## Critical: API Key First

Without an API key: **3 requests/second**.  
With an API key: **10 requests/second**.

Register immediately at https://www.ncbi.nlm.nih.gov/account/

```bash
NCBI_API_KEY=your_key_here
NCBI_EMAIL=your@email.com  # Required for Entrez — never spam, they mean it
```

If you exceed rate limits without an API key, NCBI will temporarily block your IP.

---

## The E-utilities Workflow

Every PubMed query follows this cascade:

```
ESearch → get PMIDs → EFetch → get records
     ↑
     History Server (usehistory=y) — avoids passing huge ID lists
```

### Step 1: ESearch — Find PMIDs

```python
import httpx
import asyncio
from xml.etree import ElementTree as ET
import os
import time

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ["NCBI_API_KEY"]
EMAIL = os.environ["NCBI_EMAIL"]

async def esearch(
    client: httpx.AsyncClient,
    query: str,
    max_results: int = 50,
    date_from: str = None,  # "2023/01/01" format
    date_to: str = None,
    article_types: list[str] = None,  # ["Clinical Trial", "Meta-Analysis", etc]
) -> tuple[str, str, int]:
    """
    Search PubMed, return (WebEnv, query_key, total_count) for History Server.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "usehistory": "y",     # CRITICAL: enables History Server
        "retmode": "json",
        "api_key": API_KEY,
        "email": EMAIL,
    }
    
    if date_from and date_to:
        params["datetype"] = "pdat"  # Publication date
        params["mindate"] = date_from
        params["maxdate"] = date_to
    
    if article_types:
        # Append publication type filter to query
        type_filter = " OR ".join(f'"{t}"[pt]' for t in article_types)
        params["term"] = f"({query}) AND ({type_filter})"
    
    response = await client.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
    response.raise_for_status()
    data = response.json()
    
    esearch_result = data["esearchresult"]
    return (
        esearch_result["webenv"],
        esearch_result["querykey"],
        int(esearch_result["count"]),
    )
```

### Step 2: EFetch — Retrieve Records

```python
async def efetch_abstracts(
    client: httpx.AsyncClient,
    web_env: str,
    query_key: str,
    retstart: int = 0,
    retmax: int = 50,
) -> list[dict]:
    """
    Retrieve abstract records using History Server WebEnv.
    Returns list of parsed article dicts.
    """
    params = {
        "db": "pubmed",
        "query_key": query_key,
        "WebEnv": web_env,
        "retstart": retstart,
        "retmax": retmax,
        "retmode": "xml",        # XML has richer metadata than JSON
        "rettype": "abstract",
        "api_key": API_KEY,
        "email": EMAIL,
    }
    
    response = await client.get(f"{NCBI_BASE}/efetch.fcgi", params=params)
    response.raise_for_status()
    
    return parse_pubmed_xml(response.text)


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML into structured dicts."""
    root = ET.fromstring(xml_text)
    articles = []
    
    for article in root.findall(".//PubmedArticle"):
        try:
            # Extract PMID
            pmid = article.findtext(".//PMID", default="")
            
            # Extract title
            title = article.findtext(".//ArticleTitle", default="")
            
            # Extract abstract (may have multiple sections)
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(
                (a.get("Label", "") + ": " + (a.text or "")).strip()
                for a in abstract_parts
                if a.text
            )
            
            # Extract authors
            authors = []
            for author in article.findall(".//Author"):
                last = author.findtext("LastName", "")
                first = author.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {first[0]}." if first else last)
            
            # Extract journal info
            journal = article.findtext(".//Journal/Title", default="")
            pub_year = article.findtext(".//PubDate/Year", default="")
            volume = article.findtext(".//Volume", default="")
            issue = article.findtext(".//Issue", default="")
            pages = article.findtext(".//MedlinePgn", default="")
            
            # Extract DOI
            doi = ""
            for id_elem in article.findall(".//ArticleId"):
                if id_elem.get("IdType") == "doi":
                    doi = id_elem.text or ""
                    break
            
            # Extract MeSH terms
            mesh_terms = [
                mh.findtext("DescriptorName", "")
                for mh in article.findall(".//MeshHeading")
            ]
            
            # Extract publication types
            pub_types = [
                pt.text for pt in article.findall(".//PublicationType")
                if pt.text
            ]
            
            if pmid and (title or abstract):
                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors[:5],  # Cap at 5 for display
                    "journal": journal,
                    "pub_year": int(pub_year) if pub_year.isdigit() else None,
                    "volume": volume,
                    "issue": issue,
                    "pages": pages,
                    "doi": doi,
                    "mesh_terms": mesh_terms,
                    "pub_types": pub_types,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
        except Exception as e:
            log.warning("Failed to parse article PMID=%s: %s", pmid, e)
            continue
    
    return articles
```

### Step 3: Full Pipeline with Rate Limiting

```python
import asyncio
from collections import deque

class NCBIRateLimiter:
    """Token bucket rate limiter: 10 req/s with API key, 3 without."""
    
    def __init__(self, rate: float = 10.0):
        self.rate = rate
        self.tokens = rate
        self.last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_refill = now
            
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
            else:
                self.tokens -= 1


ncbi_limiter = NCBIRateLimiter(rate=10.0)

async def search_pubmed(
    query: str,
    max_results: int = 50,
    years: tuple[int, int] = (2020, 2026),
    human_only: bool = True,
    article_types: list[str] = None,
) -> list[dict]:
    """
    Complete PubMed search pipeline with rate limiting and MeSH filters.
    """
    # Apply human filter — critical for clinical evidence retrieval
    if human_only:
        # Double-negative approach: don't just add Humans[MeSH]
        # This preserves articles that are BOTH human and animal
        query = f"({query}) NOT (animals[MeSH] NOT humans[MeSH])"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Rate limit before each request
        await ncbi_limiter.acquire()
        
        web_env, query_key, total = await esearch(
            client,
            query,
            max_results=max_results,
            date_from=f"{years[0]}/01/01",
            date_to=f"{years[1]}/12/31",
            article_types=article_types,
        )
        
        if total == 0:
            return []
        
        await ncbi_limiter.acquire()
        articles = await efetch_abstracts(
            client, web_env, query_key,
            retmax=min(max_results, total),
        )
    
    # Sort by pub_year desc, filter None years
    articles.sort(key=lambda x: x.get("pub_year") or 0, reverse=True)
    return articles
```

---

## MeSH Search Strategy

MeSH (Medical Subject Headings) is PubMed's controlled vocabulary. Using it correctly dramatically improves precision.

### The Master Search Formula

```python
def build_mesh_query(
    topic_keywords: list[str],
    mesh_terms: list[str],
    human_only: bool = True,
    publication_types: list[str] = None,
) -> str:
    """
    Build a PubMed query combining MeSH terms with keyword fallback.
    Searches MEDLINE (MeSH) AND non-MEDLINE (title/abstract) sources.
    """
    # MeSH side — for indexed MEDLINE articles
    mesh_parts = [f'"{term}"[MeSH]' for term in mesh_terms]
    mesh_query = " OR ".join(mesh_parts)
    
    # Keyword side — for non-MEDLINE (preprints, recent unindexed)
    kw_parts = [f'"{kw}"[tiab]' for kw in topic_keywords]
    kw_query = " OR ".join(kw_parts)
    
    # Combine: (MeSH for MEDLINE) OR (keywords for non-MEDLINE)
    full_query = f"({mesh_query}) OR ({kw_query})"
    
    if human_only:
        full_query = f"({full_query}) NOT (animals[MeSH] NOT humans[MeSH])"
    
    if publication_types:
        pt_filter = " OR ".join(f'"{pt}"[pt]' for pt in publication_types)
        full_query = f"({full_query}) AND ({pt_filter})"
    
    return full_query


# Example for CDI treatment query
query = build_mesh_query(
    topic_keywords=["Clostridioides difficile", "CDI treatment", "fidaxomicin vancomycin"],
    mesh_terms=["Clostridioides Infections", "Anti-Bacterial Agents", "Fidaxomicin"],
    human_only=True,
    publication_types=["Randomized Controlled Trial", "Meta-Analysis", "Practice Guideline"],
)
```

### MeSH Specialty Map

```python
SPECIALTY_MESH = {
    "cardiology": ['"Cardiovascular Diseases"[MeSH]', '"Heart"[MeSH]'],
    "oncology": ['"Neoplasms"[MeSH]'],
    "nephrology": ['"Kidney Diseases"[MeSH]', '"Renal Insufficiency, Chronic"[MeSH]'],
    "neurology": ['"Nervous System Diseases"[MeSH]', '"Brain Diseases"[MeSH]'],
    "pulmonology": ['"Lung Diseases"[MeSH]', '"Respiratory Tract Diseases"[MeSH]'],
    "gastroenterology": ['"Digestive System Diseases"[MeSH]', '"Gastrointestinal Diseases"[MeSH]'],
    "endocrinology": ['"Diabetes Mellitus"[MeSH]', '"Endocrine System Diseases"[MeSH]'],
    "infectious_disease": ['"Communicable Diseases"[MeSH]', '"Infection"[MeSH]'],
    "pediatrics": ['"Child"[MeSH]', '"Infant"[MeSH]', '"Adolescent"[MeSH]'],
}

AGE_MESH = {
    "newborn": '"Infant, Newborn"[MeSH]',
    "infant": '"Infant"[MeSH]',
    "child": '"Child"[MeSH]',
    "adolescent": '"Adolescent"[MeSH]',
    "adult": '"Adult"[MeSH]',
    "middle_aged": '"Middle Aged"[MeSH]',
    "elderly": '"Aged"[MeSH]',
    "very_elderly": '"Aged, 80 and over"[MeSH]',
}
```

---

## PMC Full-Text via BioC API

For open-access articles (~3M), get full text — not just abstracts:

```python
async def fetch_pmc_fulltext(
    client: httpx.AsyncClient,
    pmid: str,
) -> str:
    """
    Fetch full text of an OA article via PMC BioC API.
    Returns empty string if article is not open access.
    """
    # First convert PMID to PMCID
    id_conv_url = (
        f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
        f"?ids={pmid}&format=json&email={EMAIL}"
    )
    
    await ncbi_limiter.acquire()
    id_resp = await client.get(id_conv_url)
    id_resp.raise_for_status()
    id_data = id_resp.json()
    
    records = id_data.get("records", [])
    if not records or "pmcid" not in records[0]:
        return ""  # Not in PMC or not open access
    
    pmcid = records[0]["pmcid"]
    
    # Fetch BioC JSON full text
    bioc_url = (
        f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi"
        f"/BioC_json/{pmcid}/unicode"
    )
    
    await ncbi_limiter.acquire()
    bioc_resp = await client.get(bioc_url)
    
    if bioc_resp.status_code == 404:
        return ""  # Not in OA subset
    
    bioc_resp.raise_for_status()
    data = bioc_resp.json()
    
    # Extract text from BioC passages
    texts = []
    for doc in data.get("documents", []):
        for passage in doc.get("passages", []):
            text = passage.get("text", "")
            if text and len(text) > 50:  # Skip boilerplate
                texts.append(text)
    
    return "\n\n".join(texts)
```

---

## DOI Resolution via CrossRef

```python
async def resolve_doi(client: httpx.AsyncClient, doi: str) -> dict:
    """
    Get full metadata for a DOI via CrossRef (50 req/s in Polite Pool).
    """
    url = f"https://api.crossref.org/works/{doi}"
    params = {"mailto": EMAIL}  # Puts you in "Polite Pool" — higher rate limit
    
    response = await client.get(url, params=params, timeout=10.0)
    if response.status_code == 404:
        return {}  # DOI doesn't exist — citation is likely hallucinated
    
    response.raise_for_status()
    work = response.json().get("message", {})
    
    return {
        "doi": doi,
        "title": " ".join(work.get("title", [])),
        "authors": [
            f"{a.get('family', '')} {a.get('given', [''])[0]}."
            for a in work.get("author", [])[:5]
        ],
        "journal": work.get("container-title", [None])[0],
        "year": work.get("published", {}).get("date-parts", [[None]])[0][0],
        "url": work.get("URL", f"https://doi.org/{doi}"),
        "exists": True,
    }
```

---

## Common Mistakes and Fixes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| No API key | Blocked after 3 req/s | Register at ncbi.nlm.nih.gov |
| `Humans[MeSH]` only filter | Misses non-MEDLINE human studies | Use double-negative: `NOT (animals[MeSH] NOT humans[MeSH])` |
| Fetching without History Server | Can't paginate; huge URL with PMIDs | Use `usehistory=y`, pass WebEnv + query_key |
| Parsing only first author | Misses authorship context | Capture up to 5 authors |
| Not handling `pub_year` as None | Crash on ancient records | Safely cast: `int(year) if year and year.isdigit() else None` |
| No rate limiting | IP ban | Implement token bucket: 10 req/s with key |
| Using EFetch without ESearch first | No History Server, PMID list in URL | Always ESearch → WebEnv → EFetch |
| Trusting DOI in PubMed record without validation | Hallucinated citations | Validate all DOIs via CrossRef |
