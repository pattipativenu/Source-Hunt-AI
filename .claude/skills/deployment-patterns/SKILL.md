---
name: deployment-patterns
description: Use this skill for deploying Python services to GCP Cloud Run, setting up CI/CD, Dockerizing applications, managing health checks, and configuring rollback strategies. Also trigger for: Cloud Run deployment, Docker multi-stage builds, GitHub Actions CI, environment variable injection, zero-downtime deployment, Cloud Run concurrency settings, GCP Secret Manager. Applies to any GCP-hosted API service.
---

# Deployment Patterns — GCP Cloud Run

## Docker Multi-Stage Build

```dockerfile
# Stage 1: Build dependencies (separate from runtime — smaller final image)
FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime (copy only what's needed)
FROM python:3.11-slim

# Security: don't run as root
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser . .

# Cloud Run: listen on PORT env var
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Cloud Run Service Configuration

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: noocyte-api
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"   # Scale to zero when idle
        autoscaling.knative.dev/maxScale: "10"  # Cap at 10 instances
        run.googleapis.com/cpu-throttling: "false"  # Keep CPU allocated during requests
    spec:
      containers:
        - image: gcr.io/PROJECT_ID/noocyte-api:latest
          resources:
            limits:
              memory: "2Gi"
              cpu: "2"
          env:
            - name: QDRANT_URL
              valueFrom:
                secretKeyRef:
                  name: qdrant-url
                  key: latest
            - name: GEMINI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: gemini-api-key
                  key: latest
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
```

## Health Check Endpoint

```python
from fastapi import FastAPI
import time

app = FastAPI()
START_TIME = time.time()

@app.get("/health")
async def health():
    """
    Health check for Cloud Run liveness probe.
    Returns 200 if all critical dependencies are reachable.
    """
    checks = {}
    overall_healthy = True
    
    # Check Qdrant connectivity
    try:
        await qdrant_client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"
        overall_healthy = False
    
    # Check Redis connectivity
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        # Redis is a cache — degraded but not critical
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "uptime_seconds": int(time.time() - START_TIME),
        "checks": checks,
    }, 200 if overall_healthy else 503
```

## GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest tests/unit/ -v --cov=. --cov-fail-under=80
  
  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and push
        run: |
          docker buildx build --platform linux/amd64 \
            -t gcr.io/${{ vars.GCP_PROJECT }}/noocyte-api:${{ github.sha }} \
            -t gcr.io/${{ vars.GCP_PROJECT }}/noocyte-api:latest \
            --push .
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy noocyte-api \
            --image gcr.io/${{ vars.GCP_PROJECT }}/noocyte-api:${{ github.sha }} \
            --region asia-south1 \
            --platform managed \
            --min-instances 0 \
            --max-instances 10 \
            --memory 2Gi \
            --cpu 2 \
            --concurrency 80 \
            --timeout 60s
```

## GCP Secret Manager (Never Hardcode Secrets)

```python
# In Cloud Run: secrets injected as env vars via Secret Manager
# In local dev: use .env file (in .gitignore)

# Accessing secrets in Cloud Run
import os
from google.cloud import secretmanager  # Only needed for programmatic access

# Preferred: Cloud Run injects as env vars automatically
api_key = os.environ["GEMINI_API_KEY"]  # Set in Cloud Run service config

# Alternative: Direct Secret Manager access (for dynamic rotation)
def get_secret(secret_id: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

## Zero-Downtime Rollback

```bash
# List recent revisions
gcloud run revisions list --service=noocyte-api --region=asia-south1

# Rollback to previous revision (100% traffic)
gcloud run services update-traffic noocyte-api \
  --region=asia-south1 \
  --to-revisions=PREVIOUS_REVISION=100

# Canary: 10% to new, 90% to stable
gcloud run services update-traffic noocyte-api \
  --region=asia-south1 \
  --to-revisions=NEW_REVISION=10,STABLE_REVISION=90
```

## Common Deployment Mistakes

```bash
# ❌ Building on M1/M2 Mac without platform flag — runs on Mac, crashes on Cloud Run
docker build -t my-image .
# ✅
docker buildx build --platform linux/amd64 -t my-image .

# ❌ Listening on localhost — Cloud Run can't reach it
uvicorn main:app --host 127.0.0.1 --port 8080
# ✅ Must be 0.0.0.0
uvicorn main:app --host 0.0.0.0 --port $PORT

# ❌ Hardcoded port — Cloud Run injects PORT env var
uvicorn main:app --port 8080
# ✅
import os; port = int(os.environ.get("PORT", 8080))
```
