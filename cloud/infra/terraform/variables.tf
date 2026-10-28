variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "bigquery_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "force_destroy_buckets" {
  description = "Force destroy GCS buckets even if not empty"
  type        = bool
  default     = false
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Note: Cloud Run services deployed from source code, no Docker images needed

# Dataflow Configuration
variable "fusion_template_gcs_path" {
  description = "GCS path to the Dataflow template"
  type        = string
  default     = "gs://PROJECT_ID-resolve-binaries/templates/fusion"
}

variable "fusion_temp_location" {
  description = "GCS temp location for Dataflow"
  type        = string
  default     = "gs://PROJECT_ID-resolve-binaries/temp"
}

variable "fusion_staging_location" {
  description = "GCS staging location for Dataflow"
  type        = string
  default     = "gs://PROJECT_ID-resolve-binaries/staging"
}
