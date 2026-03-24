"""
Centralised configuration via Pydantic Settings.
All secrets are read from environment variables or GCP Secret Manager.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── GCP ──────────────────────────────────────────────────────────────────
    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="asia-south1", alias="GCP_REGION")
    gcs_bucket_icmr: str = Field(default="limitless-medical-guidelines", alias="GCS_BUCKET_ICMR")
    gcs_icmr_prefix: str = Field(
        default="raw-indian-medical-guidelines-pdfs", alias="GCS_ICMR_PREFIX"
    )

    # ── Pub/Sub ───────────────────────────────────────────────────────────────
    pubsub_topic_queries: str = Field(default="hunt-ai-queries", alias="PUBSUB_TOPIC_QUERIES")
    pubsub_subscription_worker: str = Field(
        default="hunt-ai-worker-sub", alias="PUBSUB_SUBSCRIPTION_WORKER"
    )

    # ── Qdrant Cloud ─────────────────────────────────────────────────────────
    # Get your URL + API key from cloud.qdrant.io (free tier: 500K chunks)
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection_guidelines: str = Field(
        default="medical_evidence", alias="QDRANT_COLLECTION_GUIDELINES"
    )
    qdrant_collection_drugs: str = Field(
        default="indian_drugs", alias="QDRANT_COLLECTION_DRUGS"
    )

    # ── Gemini ────────────────────────────────────────────────────────────────
    # Two auth modes:
    #   GEMINI_USE_VERTEX=false → uses GEMINI_API_KEY (Google AI Studio, simpler)
    #   GEMINI_USE_VERTEX=true  → uses Application Default Credentials (Vertex AI)
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_use_vertex: bool = Field(default=False, alias="GEMINI_USE_VERTEX")
    gemini_model_primary: str = Field(
        default="gemini-2.5-flash-preview-05-20", alias="GEMINI_MODEL_PRIMARY"
    )
    gemini_model_pro: str = Field(
        default="gemini-2.5-pro-preview-05-06", alias="GEMINI_MODEL_PRO"
    )

    # ── Twilio WhatsApp ───────────────────────────────────────────────────────
    # Sandbox: console.twilio.com → Messaging → Try it out → Send a WhatsApp message
    # Sandbox number: whatsapp:+14155238886 (doctors join via "join <word>-<word>")
    twilio_account_sid: str = Field(..., alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_number: str = Field(..., alias="TWILIO_WHATSAPP_NUMBER")

    # ── External APIs ─────────────────────────────────────────────────────────
    ncbi_api_key: str | None = Field(default=None, alias="NCBI_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    crossref_mailto: str = Field(default="hunt@hunt.ai", alias="CROSSREF_MAILTO")

    # ── Cohere (primary re-ranker) ────────────────────────────────────────────
    # Zero infrastructure, 392ms/50 docs, 100+ languages, $2/1K searches
    cohere_api_key: str | None = Field(default=None, alias="COHERE_API_KEY")

    # ── Redis (Memorystore) ───────────────────────────────────────────────────
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_ttl_response: int = Field(default=43200, description="12h in seconds")
    redis_ttl_doi: int = Field(default=86400, description="24h in seconds")
    redis_ttl_dedup: int = Field(default=7200, description="2h dedup window")

    # ── Firestore (existing ICMR embeddings) ──────────────────────────────────
    firestore_collection_chunks: str = Field(
        default="guideline_chunks", alias="FIRESTORE_COLLECTION_CHUNKS"
    )

    # ── Internal service URLs (Cloud Run) ─────────────────────────────────────
    reranker_service_url: str = Field(
        default="http://localhost:8001", alias="RERANKER_SERVICE_URL"
    )

    # ── Embedding backend ─────────────────────────────────────────────────────
    # "bge"    → BAAI/bge-m3 (dense + sparse, multilingual, self-hosted)
    # "google" → text-embedding-004 via Gemini API (dense only, no GPU needed)
    embedding_backend: str = Field(default="bge", alias="EMBEDDING_BACKEND")
    google_embedding_model: str = Field(
        default="text-embedding-004", alias="GOOGLE_EMBEDDING_MODEL"
    )
    google_embedding_dim: int = Field(default=768, alias="GOOGLE_EMBEDDING_DIM")

    # ── Retrieval tuning ──────────────────────────────────────────────────────
    retrieval_prefetch_limit: int = Field(default=50)
    retrieval_final_limit: int = Field(default=100)
    # Top 5 chunks to LLM (avoid "lost in the middle" degradation beyond this)
    reranker_top_k: int = Field(default=5)
    nli_confidence_threshold: float = Field(default=0.70, description="MiniCheck/Gemini-judge threshold")
    semantic_cache_threshold: float = Field(default=0.98)

    # ── Temporal filtering ────────────────────────────────────────────────────
    min_pub_year: int = Field(default=2020)
    ncbi_recent_date_filter: str = Field(default="2023/01/01:3000[pdat]")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
