---
name: deploy
description: Deploy Hunt AI services to Google Cloud Run. Builds Docker images, pushes to GCR, and deploys webhook or worker or reranker to Cloud Run in asia-south1.
argument-hint: "[webhook|worker|reranker|all] [--project PROJECT_ID] [--dry-run]"
disable-model-invocation: true
allowed-tools: Bash, Read
---

# Hunt AI — GCP Cloud Run Deployment

Deploy one or all Hunt AI services to Google Cloud Run.

## Arguments
`$ARGUMENTS` — service selection. Examples:
- `/deploy webhook` — deploy webhook service only
- `/deploy worker` — deploy worker service only
- `/deploy reranker` — deploy reranker service only
- `/deploy all` — deploy all three services
- `/deploy all --dry-run` — show commands without executing

## Pre-flight checklist

Before deploying, verify:

```bash
# 1. Authenticated with GCP
gcloud auth list | grep ACTIVE

# 2. Project set
gcloud config get-value project

# 3. Required APIs enabled
gcloud services list --enabled | grep -E "run|pubsub|secretmanager"

# 4. .env has GCP_PROJECT_ID
grep GCP_PROJECT_ID /Users/admin/Documents/hunt.ai/.env
```

## Deployment steps

Set project variable:
```bash
PROJECT=$(grep GCP_PROJECT_ID /Users/admin/Documents/hunt.ai/.env | cut -d= -f2)
REGION=asia-south1
```

### Deploy webhook
```bash
cd /Users/admin/Documents/hunt.ai
docker build -f docker/Dockerfile.webhook -t gcr.io/$PROJECT/hunt-webhook:latest .
docker push gcr.io/$PROJECT/hunt-webhook:latest
gcloud run deploy hunt-webhook \
  --image gcr.io/$PROJECT/hunt-webhook:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION \
  --set-secrets TWILIO_ACCOUNT_SID=twilio-sid:latest,TWILIO_AUTH_TOKEN=twilio-token:latest,TWILIO_WHATSAPP_NUMBER=twilio-number:latest
```

### Deploy worker
```bash
cd /Users/admin/Documents/hunt.ai
docker build -f docker/Dockerfile.worker -t gcr.io/$PROJECT/hunt-worker:latest .
docker push gcr.io/$PROJECT/hunt-worker:latest
gcloud run deploy hunt-worker \
  --image gcr.io/$PROJECT/hunt-worker:latest \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 20 \
  --set-env-vars GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION \
  --set-secrets GEMINI_API_KEY=gemini-key:latest,QDRANT_URL=qdrant-url:latest,QDRANT_API_KEY=qdrant-key:latest,COHERE_API_KEY=cohere-key:latest
```

### Deploy reranker
```bash
cd /Users/admin/Documents/hunt.ai
docker build -f docker/Dockerfile.reranker -t gcr.io/$PROJECT/hunt-reranker:latest .
docker push gcr.io/$PROJECT/hunt-reranker:latest
gcloud run deploy hunt-reranker \
  --image gcr.io/$PROJECT/hunt-reranker:latest \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 4Gi \
  --cpu 4 \
  --min-instances 1 \
  --max-instances 5
```

## Post-deployment verification

```bash
# Get webhook URL and test health
WEBHOOK_URL=$(gcloud run services describe hunt-webhook --region $REGION --format='value(status.url)')
curl -s $WEBHOOK_URL/health

# Check worker logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=hunt-worker" \
  --limit=20 --format="value(textPayload)" --freshness=5m
```

## Secrets setup (first-time only)
```bash
# Store secrets in Secret Manager
echo -n "ACxxxxxxx" | gcloud secrets create twilio-sid --data-file=-
echo -n "your_token" | gcloud secrets create twilio-token --data-file=-
echo -n "whatsapp:+14155238886" | gcloud secrets create twilio-number --data-file=-
echo -n "AIza..." | gcloud secrets create gemini-key --data-file=-
echo -n "https://xxx.qdrant.io" | gcloud secrets create qdrant-url --data-file=-
echo -n "your_key" | gcloud secrets create qdrant-key --data-file=-
echo -n "your_key" | gcloud secrets create cohere-key --data-file=-
```

## Key files
- `docker/Dockerfile.webhook`
- `docker/Dockerfile.worker`
- `docker/Dockerfile.reranker`
- `infra/terraform/` — GCP resource provisioning
