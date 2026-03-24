output "webhook_url" {
  value       = google_cloud_run_v2_service.webhook.uri
  description = "Webhook Cloud Run service URL — configure as Twilio WhatsApp webhook"
}

output "worker_url" {
  value       = google_cloud_run_v2_service.worker.uri
  description = "Worker Cloud Run service URL"
}

output "reranker_url" {
  value       = google_cloud_run_v2_service.reranker.uri
  description = "MedCPT reranker service URL"
}

output "verifier_url" {
  value       = google_cloud_run_v2_service.verifier.uri
  description = "DeBERTa NLI verifier service URL"
}

output "redis_host" {
  value       = google_redis_instance.cache.host
  description = "Redis Memorystore internal IP"
}
