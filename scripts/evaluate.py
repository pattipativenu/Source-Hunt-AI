"""
Offline evaluation harness for Hunt AI (ARES-adapted).

Metrics:
  - Citation Recall: % of Tier 1 sources retrieved for known-answer queries
  - Context Utilization: % of retrieved chunks actually cited
  - Temporal Accuracy: % of citations from 2023-2025 (excluding landmark)
  - Indian Context Accuracy: % with Indian guidelines prioritised
  - NLI Support Rate: % of claims verified SUPPORTED by DeBERTa
  - DOI Validity Rate: % of cited DOIs resolving via CrossRef

Usage:
  python scripts/evaluate.py --golden scripts/eval_data/golden_set.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_evaluation(golden_path: Path) -> dict[str, float]:
    golden_set: list[dict[str, Any]] = json.loads(golden_path.read_text())
    logger.info("Evaluating on %d golden queries", len(golden_set))

    from shared.config import get_settings
    from shared.models.query import QueryMessage
    from services.worker.pipeline import RAGPipeline

    settings = get_settings()
    pipeline = RAGPipeline()

    metrics = {
        "citation_recall": [],
        "context_utilization": [],
        "temporal_accuracy": [],
        "indian_context_accuracy": [],
        "nli_support_rate": [],
        "doi_validity_rate": [],
    }

    for item in golden_set:
        query = item["query"]
        expected_tier1_sources = set(item.get("expected_tier1_sources", []))
        has_indian_guideline = item.get("has_indian_guideline", False)

        msg = QueryMessage(
            message_id="eval",
            user_phone="whatsapp:+910000000000",
            raw_text=query,
        )

        # Run pipeline to get structured response (not just formatted parts)
        from services.worker.query_understanding import QueryUnderstanding
        from services.worker.retrieval import HybridRetriever
        from services.worker.generation import Generator
        from services.worker.citation_verifier import CitationVerifier
        from shared.utils import RedisCache

        cache = RedisCache(host=settings.redis_host, port=settings.redis_port)
        qu = QueryUnderstanding()
        retriever = HybridRetriever()
        generator = Generator()
        verifier = CitationVerifier(cache=cache)

        msg = await qu.process(msg)
        chunks = await retriever.retrieve(msg)
        response = await generator.generate(msg.translated_text or query, chunks)
        response = await verifier.verify(response)

        # ── Citation Recall ────────────────────────────────────────────────
        cited_sources = {c.source_type for c in response.citations if c.tier == 1}
        if expected_tier1_sources:
            recall = len(cited_sources & expected_tier1_sources) / len(expected_tier1_sources)
        else:
            recall = 1.0
        metrics["citation_recall"].append(recall)

        # ── Context Utilization ────────────────────────────────────────────
        cited_count = len(response.citations)
        total_chunks = len(chunks)
        metrics["context_utilization"].append(
            cited_count / total_chunks if total_chunks > 0 else 0.0
        )

        # ── Temporal Accuracy ─────────────────────────────────────────────
        total_cites = len(response.citations)
        if total_cites > 0:
            recent = sum(
                1 for c in response.citations
                if c.year >= 2023 or c.source_type == "guideline"
            )
            metrics["temporal_accuracy"].append(recent / total_cites)
        else:
            metrics["temporal_accuracy"].append(0.0)

        # ── Indian Context Accuracy ────────────────────────────────────────
        if has_indian_guideline:
            has_icmr = any(
                c.tier == 1 or "ICMR" in (c.journal or "")
                for c in response.citations
            )
            metrics["indian_context_accuracy"].append(1.0 if has_icmr else 0.0)

        # ── NLI Support Rate ──────────────────────────────────────────────
        nli_labeled = [c for c in response.citations if c.nli_label is not None]
        if nli_labeled:
            supported = sum(1 for c in nli_labeled if c.nli_label == "SUPPORTED")
            metrics["nli_support_rate"].append(supported / len(nli_labeled))

        # ── DOI Validity Rate ─────────────────────────────────────────────
        doi_checked = [c for c in response.citations if c.doi_valid is not None]
        if doi_checked:
            valid = sum(1 for c in doi_checked if c.doi_valid)
            metrics["doi_validity_rate"].append(valid / len(doi_checked))

        await cache.close()

    await pipeline.close()

    # Aggregate
    results: dict[str, float] = {}
    for metric, values in metrics.items():
        results[metric] = round(sum(values) / len(values), 4) if values else 0.0

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Hunt AI evaluation harness")
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("scripts/eval_data/golden_set.json"),
        help="Path to golden test set JSON",
    )
    args = parser.parse_args()

    results = asyncio.run(run_evaluation(args.golden))

    print("\n=== Hunt AI Evaluation Results ===")
    for metric, score in results.items():
        bar = "█" * int(score * 20)
        print(f"  {metric:<30} {score:.1%}  {bar}")
    print()

    # Save results
    out = Path("scripts/eval_data/latest_results.json")
    out.write_text(json.dumps(results, indent=2))
    logger.info("Results saved to %s", out)


if __name__ == "__main__":
    main()
