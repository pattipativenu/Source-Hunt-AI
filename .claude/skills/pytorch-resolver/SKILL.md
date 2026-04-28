---
name: pytorch-resolver
description: >
  Diagnose and resolve PyTorch, CUDA, and Hugging Face Transformers build
  errors, dependency conflicts, and runtime failures in the Noocyte AI
  environment. Use when model loading fails, CUDA is not detected, package
  versions conflict, or inference produces unexpected results. Covers
  Cloud Run deployment constraints and CPU-only fallback patterns.
argument-hint: "<error message or symptom>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# PyTorch Resolver

## Purpose

The Noocyte AI pipeline uses several PyTorch-based models (BGE-M3, MedCPT, NLI verifier). These models can fail to load, produce errors, or run slowly due to version conflicts, missing CUDA drivers, or incorrect configuration. This skill gives you the exact commands and fixes for the most common problems.

You do not need to understand PyTorch deeply to use this skill. Follow the diagnostic steps and apply the matching fix.

---

## Quick Diagnostic Commands

Run these first to understand your environment:

```bash
# Check Python and pip versions
python3 --version
pip3 --version

# Check PyTorch installation and CUDA availability
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
"

# Check Transformers and related packages
python3 -c "
import transformers, sentence_transformers, FlagEmbedding
print(f'Transformers: {transformers.__version__}')
print(f'SentenceTransformers: {sentence_transformers.__version__}')
"

# Check for dependency conflicts
pip3 check
```

---

## Error Catalog and Fixes

### Error 1: `ModuleNotFoundError: No module named 'FlagEmbedding'`

```bash
# Symptom: BGE-M3 model fails to load
# Cause: FlagEmbedding package not installed

# Fix:
pip3 install FlagEmbedding

# If on Cloud Run (no GPU):
pip3 install FlagEmbedding torch --extra-index-url https://download.pytorch.org/whl/cpu
```

### Error 2: `CUDA out of memory`

```bash
# Symptom: Model loads but crashes during inference
# Cause: GPU memory exhausted

# Fix Option 1: Use CPU instead
python3 -c "
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cpu')
"

# Fix Option 2: Reduce batch size
# In your embedding code, change batch_size from 32 to 4

# Fix Option 3: Use FP16 to halve memory usage
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)  # Requires CUDA
```

### Error 3: `OSError: [Errno 28] No space left on device`

```bash
# Symptom: Model download fails
# Cause: Hugging Face model cache is filling the disk

# Check disk usage
df -h
du -sh ~/.cache/huggingface/

# Fix: Clear old model cache
rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-m3/blobs/

# Fix: Change cache directory to a larger disk
export HF_HOME=/mnt/data/huggingface_cache
```

### Error 4: `RuntimeError: CUDA error: device-side assert triggered`

```bash
# Symptom: Cryptic CUDA error during model inference
# Cause: Usually an input that is too long or contains invalid token IDs

# Debug: Run with CUDA_LAUNCH_BLOCKING to get the real error
CUDA_LAUNCH_BLOCKING=1 python3 your_script.py

# Common fix: Add input truncation
encoded = tokenizer(
    text,
    truncation=True,      # ← Add this
    max_length=512,       # ← Add this
    return_tensors="pt",
)
```

### Error 5: `ImportError: cannot import name 'AutoModelForSequenceClassification'`

```bash
# Symptom: MedCPT reranker fails to import
# Cause: Transformers version is too old

# Check current version
python3 -c "import transformers; print(transformers.__version__)"

# Fix: Upgrade transformers
pip3 install --upgrade transformers>=4.35.0
```

### Error 6: Version Conflict — `torch` and `transformers` incompatible

```bash
# Symptom: pip check shows conflicts, or models fail with cryptic errors
# Cause: torch and transformers versions are not compatible

# Fix: Install a known-good combination
pip3 install torch==2.1.0 transformers==4.36.0 sentence-transformers==2.3.1

# For Cloud Run (CPU only, smaller image):
pip3 install torch==2.1.0+cpu transformers==4.36.0 sentence-transformers==2.3.1 \
  --extra-index-url https://download.pytorch.org/whl/cpu
```

---

## Cloud Run Deployment Constraints

Cloud Run has specific constraints that affect PyTorch models:

```python
# Cloud Run constraints for ML models:
CLOUD_RUN_CONSTRAINTS = {
    "max_memory": "32GB",       # Maximum memory per instance
    "max_cpu": "8 vCPUs",       # No GPU on standard Cloud Run
    "max_image_size": "10GB",   # Docker image size limit
    "startup_timeout": "300s",  # Model must load within 5 minutes
    "request_timeout": "3600s", # Maximum request processing time
}

# Recommendations for Cloud Run:
# 1. Use CPU-only PyTorch (saves ~2GB in Docker image)
# 2. Pre-download models during Docker build, not at runtime
# 3. Use model quantization (INT8) to reduce memory and speed up inference
# 4. Consider running models as a separate Cloud Run service (microservice pattern)
```

### Dockerfile for ML Models on Cloud Run

```dockerfile
# Dockerfile.ml-service — Optimized for Cloud Run
FROM python:3.11-slim

# Install CPU-only PyTorch (smaller image)
RUN pip3 install torch==2.1.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip3 install transformers==4.36.0 sentence-transformers==2.3.1 FlagEmbedding

# Pre-download models during build (not at runtime)
# This adds to image size but eliminates cold-start download time
ENV HF_HOME=/app/models
RUN python3 -c "
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cpu')
print('BGE-M3 downloaded successfully')
"

COPY . /app
WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## CPU-Only Fallback Pattern

When GPU is not available (Cloud Run, local development), use this pattern:

```python
import torch
from typing import Literal

def get_device() -> Literal["cuda", "cpu"]:
    """Get the best available device, with graceful CPU fallback."""
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"Using GPU: {gpu_name}")
    else:
        device = "cpu"
        logger.info("GPU not available — using CPU (inference will be slower)")
    return device

class EmbeddingService:
    def __init__(self):
        device = get_device()
        use_fp16 = device == "cuda"  # FP16 only works on GPU
        
        self.model = BGEM3FlagModel(
            "BAAI/bge-m3",
            use_fp16=use_fp16,
            device=device,
        )
        logger.info(f"BGE-M3 loaded on {device} (fp16={use_fp16})")
```

---

## Performance Benchmarks

Know what to expect so you can identify when something is wrong:

| Model | Hardware | Batch Size | Latency |
|-------|----------|-----------|---------|
| BGE-M3 (embedding) | CPU (8 vCPU) | 12 | ~800ms |
| BGE-M3 (embedding) | GPU (T4) | 32 | ~120ms |
| MedCPT (reranking) | CPU (8 vCPU) | 10 | ~400ms |
| MedCPT (reranking) | GPU (T4) | 10 | ~80ms |
| DeBERTa NLI | CPU (8 vCPU) | 5 | ~600ms |
| DeBERTa NLI | GPU (T4) | 5 | ~100ms |

**If your latency is 3x higher than these benchmarks, something is wrong.**
Common causes: model loaded on wrong device, batch size too large, input not truncated.

---

## What NOT to Do

```python
# ❌ Loading the model inside a request handler — catastrophic latency
@app.post("/embed")
async def embed(text: str):
    model = BGEM3FlagModel("BAAI/bge-m3")  # 10 seconds every request!
    return model.encode([text])

# ✅ Load once at startup
embedding_service = EmbeddingService()  # Loaded once when app starts

@app.post("/embed")
async def embed(text: str):
    return embedding_service.encode([text])  # < 1 second

# ❌ Not handling the case where CUDA is unavailable
model = BGEM3FlagModel("BAAI/bge-m3", device="cuda")  # Crashes on CPU-only Cloud Run

# ✅ Always use the device detection pattern
device = get_device()
model = BGEM3FlagModel("BAAI/bge-m3", device=device)
```

---

*A model that crashes in production helps no doctor. A model that runs slowly on CPU still helps doctors.*
