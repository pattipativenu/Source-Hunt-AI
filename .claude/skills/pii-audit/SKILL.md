---
name: pii-audit
description: >
  Audit, detect, and redact Personally Identifiable Information (PII) from
  queries, logs, and stored data in Noocyte AI. Use before any query is
  logged, stored, or sent to external APIs. Covers Indian PII patterns
  (Aadhaar, phone numbers, patient names), DPDP Act 2023 compliance,
  and automated audit scripts for log files.
argument-hint: "<text to audit or log file path>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# PII Audit

## Purpose

Noocyte AI is a professional clinical search engine. While doctors use it for evidence-based decision support, their queries may occasionally include patient identifiers (e.g., "Patient Rahul Sharma with Aadhaar..."). To maintain professional standards and comply with data processing best practices, this skill ensures that **clinical evidence remains the focus** by stripping out non-clinical identifiers (Aadhaar, names, phone numbers) before any query is logged, cached, or analyzed.

This ensures the "Noocyte Search Engine" remains a clean repository of clinical knowledge without the clutter of individual patient data.

---

## Indian PII Patterns

```python
import re

# Indian PII detection patterns
INDIAN_PII_PATTERNS = {
    # Aadhaar number: 12 digits, may be formatted with spaces
    "aadhaar": re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),
    
    # Indian mobile numbers: 10 digits starting with 6-9, or +91 prefix
    "phone_in": re.compile(r'(\+91[\s-]?)?[6-9]\d{9}\b'),
    
    # PAN card: 5 letters + 4 digits + 1 letter
    "pan": re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
    
    # Indian passport: 1 letter + 7 digits
    "passport": re.compile(r'\b[A-Z][0-9]{7}\b'),
    
    # Email addresses
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    
    # Patient name patterns (common in Indian medical queries)
    # "patient Mr./Mrs./Dr. [Name]" or "patient [Name] aged [N]"
    "patient_name": re.compile(
        r'(?:patient|pt\.?)\s+(?:mr\.?|mrs\.?|ms\.?|dr\.?)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        re.IGNORECASE
    ),
    
    # Age + gender combinations that could identify a patient
    "age_gender": re.compile(
        r'\b(\d{1,3})\s*(?:year|yr|y)s?\s*(?:old)?\s*(?:male|female|m|f|M|F)\b',
        re.IGNORECASE
    ),
}

def redact_pii(text: str) -> str:
    """
    Redact all detected PII from text.
    
    Replaces detected PII with safe placeholders.
    Preserves clinical content (drug names, diagnoses, dosages).
    
    Args:
        text: Raw query or log text that may contain PII
    
    Returns:
        Text with PII replaced by [REDACTED] placeholders
    
    Example:
        redact_pii("Patient Mr. Rahul Sharma, Aadhaar 1234 5678 9012, has fever")
        → "Patient [NAME REDACTED], Aadhaar [AADHAAR REDACTED], has fever"
    """
    redacted = text
    
    # Redact Aadhaar numbers
    redacted = INDIAN_PII_PATTERNS["aadhaar"].sub("[AADHAAR REDACTED]", redacted)
    
    # Redact phone numbers
    redacted = INDIAN_PII_PATTERNS["phone_in"].sub("[PHONE REDACTED]", redacted)
    
    # Redact PAN cards
    redacted = INDIAN_PII_PATTERNS["pan"].sub("[PAN REDACTED]", redacted)
    
    # Redact email addresses
    redacted = INDIAN_PII_PATTERNS["email"].sub("[EMAIL REDACTED]", redacted)
    
    # Redact patient names (careful — don't redact drug names)
    redacted = INDIAN_PII_PATTERNS["patient_name"].sub(
        lambda m: m.group(0).replace(m.group(1), "[NAME REDACTED]"),
        redacted
    )
    
    return redacted

def contains_pii(text: str) -> tuple[bool, list[str]]:
    """
    Check if text contains PII without redacting it.
    Returns (has_pii, list_of_pii_types_found).
    """
    found_types = []
    for pii_type, pattern in INDIAN_PII_PATTERNS.items():
        if pattern.search(text):
            found_types.append(pii_type)
    return len(found_types) > 0, found_types
```

---

## Integration Points — Where PII Must Be Redacted

```python
# RULE: PII must be redacted at these exact points in the pipeline:

# 1. BEFORE LOGGING — always redact before any log statement
import logging
logger = logging.getLogger(__name__)

# ❌ WRONG — logs raw query with potential PII
logger.info(f"Processing query: {raw_query}")

# ✅ CORRECT — redact before logging
logger.info(f"Processing query: {redact_pii(raw_query)}")

# 2. BEFORE EXTERNAL API CALLS — redact before sending to Gemini, Cohere, Tavily
# ❌ WRONG — sends raw query to Gemini (which may log it on their end)
response = await gemini.generate(raw_query, context)

# ✅ CORRECT — send redacted query to external APIs
clean_query = redact_pii(raw_query)
response = await gemini.generate(clean_query, context)

# 3. BEFORE STORING IN REDIS CACHE — never cache PII
# ❌ WRONG — caches the raw query as the cache key
cache_key = hashlib.md5(raw_query.encode()).hexdigest()

# ✅ CORRECT — cache key derived from redacted query
cache_key = hashlib.md5(redact_pii(raw_query).encode()).hexdigest()

# 4. BEFORE WRITING TO BIGQUERY/ANALYTICS — redact all query text
# ❌ WRONG — stores raw queries in analytics
await bigquery.insert({"query": raw_query, "timestamp": now})

# ✅ CORRECT — store only redacted queries
await bigquery.insert({"query": redact_pii(raw_query), "timestamp": now})
```

---

## Automated Log Audit

Run this script to audit existing log files for PII leakage:

```bash
# Audit all log files for PII
python3 scripts/audit_logs_for_pii.py --log-dir /var/log/noocyte/

# Audit a specific log file
python3 scripts/audit_logs_for_pii.py --file /var/log/noocyte/app.log

# Audit Cloud Logging (GCP)
python3 scripts/audit_logs_for_pii.py --cloud-run --project noocyte-ai --days 7
```

```python
# scripts/audit_logs_for_pii.py
def audit_log_file(log_path: str) -> dict:
    """
    Scan a log file for PII and produce an audit report.
    Does NOT modify the log file — audit only.
    """
    findings = []
    
    with open(log_path) as f:
        for line_num, line in enumerate(f, 1):
            has_pii, pii_types = contains_pii(line)
            if has_pii:
                findings.append({
                    "line": line_num,
                    "pii_types": pii_types,
                    "preview": line[:100] + "..." if len(line) > 100 else line,
                    "severity": "HIGH" if "aadhaar" in pii_types else "MEDIUM",
                })
    
    return {
        "file": log_path,
        "total_lines": line_num,
        "pii_findings": len(findings),
        "high_severity": sum(1 for f in findings if f["severity"] == "HIGH"),
        "findings": findings,
        "recommendation": "IMMEDIATE ACTION REQUIRED" if findings else "CLEAN",
    }
```

---

## DPDP Act 2023 Compliance Checklist

India's Digital Personal Data Protection Act 2023 requires:

```
✅ REQUIRED:
- [ ] No personal data stored without explicit consent
- [ ] Query logs retain only redacted text (no raw queries with PII)
- [ ] Data retention policy: query logs deleted after 90 days
- [ ] Doctor's WhatsApp number stored only as a hashed identifier
- [ ] No patient data (names, Aadhaar, phone) stored anywhere
- [ ] Privacy policy accessible to all users
- [ ] Data breach notification within 72 hours (to CERT-In)

⚠️ PROHIBITED:
- Storing raw queries containing patient identifiers
- Sharing query data with third parties without consent
- Using patient data for model training without consent
- Retaining query logs indefinitely
```

---

## Testing This Skill

```python
# tests/unit/test_pii_audit.py
from shared.utils.pii_redactor import redact_pii, contains_pii

class TestPIIRedaction:
    def test_aadhaar_redacted(self):
        text = "Patient Aadhaar: 1234 5678 9012"
        result = redact_pii(text)
        assert "1234 5678 9012" not in result
        assert "[AADHAAR REDACTED]" in result

    def test_phone_redacted(self):
        result = redact_pii("Call me at +91 9876543210")
        assert "9876543210" not in result
        assert "[PHONE REDACTED]" in result

    def test_clinical_content_preserved(self):
        text = "Patient has T2DM, prescribe Metformin 500mg BD"
        result = redact_pii(text)
        # Clinical content must be preserved
        assert "T2DM" in result
        assert "Metformin" in result
        assert "500mg" in result

    def test_email_redacted(self):
        result = redact_pii("Contact: doctor@hospital.com")
        assert "doctor@hospital.com" not in result
        assert "[EMAIL REDACTED]" in result

    def test_clean_text_unchanged(self):
        text = "What is the first-line treatment for CDI?"
        result = redact_pii(text)
        assert result == text  # No PII → no change
```

---

*Patient privacy is not a feature. It is the foundation.*
