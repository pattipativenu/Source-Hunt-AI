"""
Gemini client factory.

Supports two auth modes controlled by GEMINI_USE_VERTEX:
  false (default) → google-generativeai SDK with GEMINI_API_KEY (Google AI Studio)
  true            → google-cloud-aiplatform / vertexai SDK with ADC (Vertex AI)

Using AI Studio is recommended for solo dev / local testing — no gcloud auth needed,
no GCP project billing surprises, and the free tier is generous.
Switch to Vertex AI before production for enterprise SLAs and VPC controls.
"""

from __future__ import annotations

from typing import Any


def get_gemini_model(model_name: str) -> Any:
    """
    Return a Gemini GenerativeModel instance using the appropriate SDK.
    Lazy-imports to avoid loading both SDKs at module level.
    """
    from shared.config import get_settings
    settings = get_settings()

    if settings.gemini_use_vertex:
        return _get_vertex_model(model_name, settings)
    else:
        return _get_aistudio_model(model_name, settings)


def _get_aistudio_model(model_name: str, settings: Any) -> Any:
    """Google AI Studio path — uses GEMINI_API_KEY."""
    try:
        import google.generativeai as genai  # type: ignore[import]
    except ImportError as e:
        raise RuntimeError("Run: pip install google-generativeai") from e

    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Get one at aistudio.google.com → Get API key."
        )
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(model_name)


def _get_vertex_model(model_name: str, settings: Any) -> Any:
    """Vertex AI path — uses Application Default Credentials."""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except ImportError as e:
        raise RuntimeError("Run: pip install google-cloud-aiplatform") from e

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
