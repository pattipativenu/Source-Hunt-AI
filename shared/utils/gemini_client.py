"""
Gemini client factory — Vertex AI only.

Auth: Application Default Credentials (ADC).
  Local:     gcloud auth application-default login
  Cloud Run: uses attached service account automatically
"""

from __future__ import annotations

from typing import Any


def get_gemini_model(model_name: str) -> Any:
    """Return a Vertex AI GenerativeModel using ADC. Lazy-imports to keep startup fast."""
    from shared.config import get_settings
    settings = get_settings()

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except ImportError as e:
        raise RuntimeError(
            "Run: pip install google-cloud-aiplatform\n"
            "Local auth: gcloud auth application-default login"
        ) from e

    vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
    return GenerativeModel(model_name)


def make_generation_config(
    temperature: float = 0.1,
    top_p: float = 0.95,
    max_output_tokens: int = 8192,
    json_mode: bool = True,
) -> Any:
    """
    Build a GenerationConfig compatible with both SDK paths.
    Both SDKs accept the same kwargs, so we return a plain dict
    and let each caller unpack it appropriately.
    """
    config: dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "max_output_tokens": max_output_tokens,
    }
    if json_mode:
        config["response_mime_type"] = "application/json"
    return config
