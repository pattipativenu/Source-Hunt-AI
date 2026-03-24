---
name: logs
description: Stream or fetch Hunt AI service logs — locally from uvicorn processes or from GCP Cloud Run. Use when debugging errors, tracing a specific request, or checking pipeline latency.
argument-hint: "[service: webhook|worker|reranker|all] [--cloud] [--lines N] [--trace REQUEST_ID]"
disable-model-invocation: true
allowed-tools: Bash
---

# Hunt AI — Log Viewer

Stream or fetch logs from Hunt AI services.

## Arguments
`$ARGUMENTS` — service and options. Examples:
- `/logs worker` — tail worker logs locally
- `/logs webhook --cloud` — fetch Cloud Run webhook logs
- `/logs all --cloud --lines 50` — last 50 lines from all Cloud Run services
- `/logs worker --trace abc123` — find logs for a specific request ID

## Local logs (dev)

```bash
# Tail worker service (adjust PID or use process name)
cd /Users/admin/Documents/hunt.ai

# Option 1: If running via uvicorn in terminal, logs appear there directly.
# Option 2: Check recent structured logs in /tmp if cloud logging writes locally:
ls /tmp/hunt-ai-*.log 2>/dev/null | head -5

# Option 3: Query Redis for cached responses (shows what was answered)
python3 - <<'PYEOF'
import redis, json
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
keys = r.keys('response:*')[:20]
print(f"Cached responses: {len(r.keys('response:*'))}")
print(f"Dedup keys active: {len(r.keys('dedup:*'))}")
for k in keys[:5]:
    val = r.get(k)
    if val:
        try:
            data = json.loads(val)
            print(f"  {k}: confidence={data.get('confidence_level','?')}, answer[:60]={data.get('answer','')[:60]}")
        except:
            print(f"  {k}: {val[:80]}")
PYEOF
```

## Cloud Run logs

```bash
PROJECT=$(grep GCP_PROJECT_ID /Users/admin/Documents/hunt.ai/.env 2>/dev/null | cut -d= -f2 || echo "YOUR_PROJECT")
REGION=asia-south1
LINES=30

# Parse arguments for service name
SERVICE="hunt-worker"  # default
if echo "$ARGUMENTS" | grep -q "webhook"; then SERVICE="hunt-webhook"; fi
if echo "$ARGUMENTS" | grep -q "reranker"; then SERVICE="hunt-reranker"; fi

echo "=== Fetching logs for $SERVICE ==="
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE" \
  --project=$PROJECT \
  --limit=$LINES \
  --freshness=1h \
  --format="value(timestamp,jsonPayload.message,textPayload)" \
  | head -100
```

## Trace a specific request (Cloud Run structured logs)

```bash
PROJECT=$(grep GCP_PROJECT_ID /Users/admin/Documents/hunt.ai/.env 2>/dev/null | cut -d= -f2)
TRACE_ID="$ARGUMENTS"

# Search for trace in structured JSON logs
gcloud logging read \
  "resource.type=cloud_run_revision AND jsonPayload.trace_id=\"$TRACE_ID\"" \
  --project=$PROJECT \
  --limit=50 \
  --format=json | python3 -c "
import sys, json
logs = json.load(sys.stdin)
for l in logs:
    p = l.get('jsonPayload', {})
    print(f\"{l.get('timestamp','')} [{p.get('level','INFO')}] {p.get('service','')} — {p.get('message','')}\")
    if p.get('latency_ms'): print(f\"  latency={p['latency_ms']}ms chunks={p.get('chunk_count','?')}\")
"
```

## Error summary

```bash
PROJECT=$(grep GCP_PROJECT_ID /Users/admin/Documents/hunt.ai/.env 2>/dev/null | cut -d= -f2)

echo "=== ERROR SUMMARY (last 1h) ==="
gcloud logging read \
  "resource.type=cloud_run_revision AND severity>=ERROR" \
  --project=$PROJECT \
  --freshness=1h \
  --limit=20 \
  --format="value(timestamp,resource.labels.service_name,jsonPayload.message,textPayload)"
```

## Key log fields (structured logging)
Hunt AI uses `shared/utils/cloud_logging.py` which emits JSON logs with these fields:
- `service` — which service (webhook, worker, reranker)
- `message` — log message
- `intent` — query intent (drug_lookup, guideline_query, etc.)
- `latency_ms` — pipeline stage latency
- `chunk_count` — chunks retrieved
- `confidence_level` — HIGH / MODERATE / LOW
- `trace_id` — Cloud Trace correlation ID
