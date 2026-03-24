"""
Main orchestration pipeline for the worker service.

Called by the Cloud Run push subscription handler when a Pub/Sub message arrives.
"""

from __future__ import annotations

import logging

from shared.config import get_settings
from shared.models.query import QueryMessage
from pydantic import ValidationError
from shared.models.response import HuntAIResponse
from shared.utils import RedisCache
from .query_understanding import QueryUnderstanding
from .retrieval import HybridRetriever
from .generation import Generator
from .citation_verifier import CitationVerifier
from .formatter import WhatsAppFormatter

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGPipeline:
    def __init__(self) -> None:
        self._cache = RedisCache(host=settings.redis_host, port=settings.redis_port)
        self._query_understanding = QueryUnderstanding()
        self._retriever = HybridRetriever()
        self._generator = Generator()
        self._verifier = CitationVerifier(cache=self._cache)
        self._formatter = WhatsAppFormatter()

    async def run(self, msg: QueryMessage) -> list[str]:
        """
        Run the full RAG pipeline and return a list of WhatsApp message parts.
        Returns list[str] because responses may be paginated into multiple parts.
        """
        query_text = msg.raw_text

        # Check response cache first
        cached = await self._cache.get_response(query_text)
        if cached:
            try:
                response = HuntAIResponse(**cached)
                logger.info("Cache hit for query: %s", query_text[:50])
                return self._formatter.format(response, msg.language_code)
            except (ValidationError, TypeError, KeyError) as e:
                logger.warning("Stale cache entry, reprocessing: %s", e)

        # Step 1: Query understanding (translation, intent, PICO, specialty, demographics)
        msg = await self._query_understanding.process(msg)
        logger.info(
            "Intent: %s | Specialty: %s | Language: %s | Guideline: %s | PICO: %s",
            msg.intent, msg.specialty, msg.language_code, msg.guideline_body, msg.pico
        )

        # Step 2: Hybrid retrieval + re-ranking
        chunks = await self._retriever.retrieve(msg)
        logger.info("Retrieved %d chunks after re-ranking", len(chunks))

        if not chunks:
            return [
                "⚠️ No relevant evidence found for your query. "
                "Please try rephrasing or ask a more specific clinical question."
            ]

        # Step 3: Generation
        effective_query = msg.translated_text or msg.raw_text
        response = await self._generator.generate(effective_query, chunks)

        # Step 4: Citation verification (pass all chunks for better-source fallback)
        response = await self._verifier.verify(response, all_chunks=chunks)

        # Step 5: Cache result
        await self._cache.set_response(
            query_text, response.model_dump(), settings.redis_ttl_response
        )

        # Step 6: Format for WhatsApp (including back-translation if needed)
        parts = self._formatter.format(response, msg.language_code)
        return parts

    async def close(self) -> None:
        await self._cache.close()
