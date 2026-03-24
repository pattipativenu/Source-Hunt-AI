terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "hunt-ai-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable required APIs ───────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "container.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "redis.googleapis.com",
    "storage.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ── Pub/Sub ───────────────────────────────────────────────────────────────────
resource "google_pubsub_topic" "queries" {
  name = "hunt-ai-queries"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "worker" {
  name  = "hunt-ai-worker-sub"
  topic = google_pubsub_topic.queries.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/pubsub/push"
    oidc_token {
      service_account_email = google_service_account.worker_sa.email
    }
  }

  ack_deadline_seconds       = 300  # 5 min — allow time for full RAG pipeline
  message_retention_duration = "3600s"

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "60s"
  }
}

# ── Service Accounts ──────────────────────────────────────────────────────────
resource "google_service_account" "webhook_sa" {
  account_id   = "hunt-ai-webhook"
  display_name = "Hunt AI Webhook Service"
}

resource "google_service_account" "worker_sa" {
  account_id   = "hunt-ai-worker"
  display_name = "Hunt AI Worker Service"
}

# Grant worker SA access to Pub/Sub, Vertex AI, GCS, Secret Manager
resource "google_project_iam_member" "worker_roles" {
  for_each = toset([
    "roles/pubsub.subscriber",
    "roles/aiplatform.user",
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor",
    "roles/redis.editor",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.worker_sa.email}"
}

resource "google_project_iam_member" "webhook_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.webhook_sa.email}"
}

# ── Cloud Run: Webhook ────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "webhook" {
  name     = "hunt-ai-webhook"
  location = var.region

  template {
    service_account = google_service_account.webhook_sa.email
    containers {
      image = "gcr.io/${var.project_id}/hunt-ai-webhook:latest"
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "TWILIO_ACCOUNT_SID"
        value_source {
          secret_key_ref {
            secret  = "twilio-account-sid"
            version = "latest"
          }
        }
      }
      env {
        name = "TWILIO_AUTH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = "twilio-auth-token"
            version = "latest"
          }
        }
      }
      env {
        name = "TWILIO_WHATSAPP_NUMBER"
        value_source {
          secret_key_ref {
            secret  = "twilio-whatsapp-number"
            version = "latest"
          }
        }
      }
    }
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }
  depends_on = [google_project_service.apis]
}

# ── Cloud Run: Worker ─────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "worker" {
  name     = "hunt-ai-worker"
  location = var.region

  template {
    service_account = google_service_account.worker_sa.email
    containers {
      image = "gcr.io/${var.project_id}/hunt-ai-worker:latest"
      resources {
        limits = {
          cpu    = "4"
          memory = "4Gi"
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "QDRANT_HOST"
        value = var.qdrant_host
      }
      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }
      env {
        name  = "RERANKER_SERVICE_URL"
        value = google_cloud_run_v2_service.reranker.uri
      }
      env {
        name  = "VERIFIER_SERVICE_URL"
        value = google_cloud_run_v2_service.verifier.uri
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }
  }
  depends_on = [google_project_service.apis]
}

# ── Cloud Run: Reranker (GPU) ─────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "reranker" {
  name     = "hunt-ai-reranker"
  location = var.region

  template {
    service_account = google_service_account.worker_sa.email
    containers {
      image = "gcr.io/${var.project_id}/hunt-ai-reranker:latest"
      resources {
        limits = {
          cpu    = "4"
          memory = "8Gi"
          "nvidia.com/gpu" = "1"
        }
      }
    }
    node_selector {
      accelerator = "nvidia-l4"
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }
  depends_on = [google_project_service.apis]
}

# ── Cloud Run: Verifier (CPU) ─────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "verifier" {
  name     = "hunt-ai-verifier"
  location = var.region

  template {
    service_account = google_service_account.worker_sa.email
    containers {
      image = "gcr.io/${var.project_id}/hunt-ai-verifier:latest"
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }
  depends_on = [google_project_service.apis]
}

# ── Memorystore Redis ─────────────────────────────────────────────────────────
resource "google_redis_instance" "cache" {
  name           = "hunt-ai-cache"
  tier           = "BASIC"
  memory_size_gb = 2
  region         = var.region

  redis_version = "REDIS_7_0"
  display_name  = "Hunt AI Response Cache"

  depends_on = [google_project_service.apis]
}

# ── GKE Cluster for Qdrant ────────────────────────────────────────────────────
resource "google_container_cluster" "qdrant" {
  name     = "hunt-ai-qdrant"
  location = "${var.region}-a"

  initial_node_count = 3
  node_config {
    machine_type = "n2-standard-4"
    disk_size_gb = 100
    disk_type    = "pd-ssd"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  deletion_protection = false
  depends_on          = [google_project_service.apis]
}
