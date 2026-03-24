"""
Structured Cloud Logging integration.

On GCP (Cloud Run), this configures the standard Python logger to emit
structured JSON that Cloud Logging automatically parses — giving you:
  - Severity-based filtering in Cloud Logging Explorer
  - Trace correlation with Cloud Trace (if enabled)
  - Searchable structured fields (intent, user_phone, latency_ms, etc.)
  - Automatic error reporting integration

Locally, falls back to standard console logging.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


class _StructuredFormatter(logging.Formatter):
    """
    Formats log records as JSON objects that Cloud Logging parses natively.
    Cloud Run captures stdout and routes to Cloud Logging automatically.
    """

    _SEVERITY_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "severity": self._SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)

        # Merge extra structured fields (e.g., intent, user_phone, latency_ms)
        for key in ("intent", "user_phone", "language", "latency_ms",
                     "chunk_count", "source", "confidence", "query_hash",
                     "pmid_count", "pmc_count", "reranker", "model"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        # Cloud Trace correlation (when running on Cloud Run)
        trace_header = os.environ.get("HTTP_X_CLOUD_TRACE_CONTEXT")
        if trace_header:
            trace_id = trace_header.split("/")[0]
            project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
            if project:
                entry["logging.googleapis.com/trace"] = (
                    f"projects/{project}/traces/{trace_id}"
                )

        return json.dumps(entry, default=str)


def setup_logging(service_name: str = "hunt-ai") -> None:
    """
    Configure structured logging for the service.

    On Cloud Run (K_SERVICE env var set), uses JSON structured format.
    Locally, uses standard human-readable format.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if os.environ.get("K_SERVICE"):
        # Running on Cloud Run — use structured JSON
        handler.setFormatter(_StructuredFormatter())
    else:
        # Local development — human-readable
        handler.setFormatter(
            logging.Formatter(
                f"%(asctime)s [{service_name}] %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root.addHandler(handler)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a message with structured context fields.

    Usage:
        log_with_context(logger, logging.INFO, "Query processed",
                         intent="drug_lookup", latency_ms=342, chunk_count=5)
    """
    logger.log(level, message, extra=kwargs)
