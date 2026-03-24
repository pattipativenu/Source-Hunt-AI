variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (asia-south1 = Mumbai)"
  type        = string
  default     = "asia-south1"
}

variable "qdrant_host" {
  description = "Internal IP or hostname of Qdrant GKE service"
  type        = string
}

variable "redis_host" {
  description = "Internal IP of Memorystore Redis instance"
  type        = string
}
