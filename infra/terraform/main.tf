terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "pubsub.googleapis.com",
    "storage.googleapis.com", 
    "bigquery.googleapis.com",
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com"
  ])
  
  project = var.project_id
  service = each.value
  
  disable_dependent_services = false
  disable_on_destroy         = false
}

# Pub/Sub Topics
resource "google_pubsub_topic" "topics" {
  for_each = toset([
    "telemetry.v1",
    "images.v1", 
    "fused.v1",
    "actions.v1"
  ])
  
  name = each.value
  depends_on = [google_project_service.apis]
}

# BigQuery Dataset
resource "google_bigquery_dataset" "resolve" {
  dataset_id  = "resolve"
  description = "Resolve Agent pipeline data"
  location    = var.bigquery_location

  depends_on = [google_project_service.apis]
}

# BigQuery Table for Historical Baselines
resource "google_bigquery_table" "historical_baselines" {
  dataset_id = google_bigquery_dataset.resolve.dataset_id
  table_id   = "historical_baselines"

  schema = jsonencode([
    {
      name = "component"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "metric"
      type = "STRING" 
      mode = "REQUIRED"
    },
    {
      name = "mean"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "std"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "min_value"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "max_value"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "percentile_95"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "sample_count"
      type = "INTEGER"
      mode = "REQUIRED"
    },
    {
      name = "last_updated"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    }
  ])
}

# Service Accounts
resource "google_service_account" "services" {
  for_each = toset([
    "data-ingester",
    "historical-processor", 
    "ai-planner",
    "fusion-engine"
  ])
  
  account_id   = each.value
  display_name = "Resolve Agent ${replace(title(each.value), "-", " ")} Service"
}

# IAM Bindings
resource "google_project_iam_member" "service_permissions" {
  for_each = {
    "data-ingester-pubsub"     = { service = "data-ingester", role = "roles/pubsub.publisher" }
    "data-ingester-storage"    = { service = "data-ingester", role = "roles/storage.objectViewer" }
    "historical-bigquery"      = { service = "historical-processor", role = "roles/bigquery.dataEditor" }
    "historical-storage"       = { service = "historical-processor", role = "roles/storage.objectViewer" }
    "planner-vertex"          = { service = "ai-planner", role = "roles/aiplatform.user" }
    "planner-storage"         = { service = "ai-planner", role = "roles/storage.objectViewer" }
    "planner-bigquery"        = { service = "ai-planner", role = "roles/bigquery.dataViewer" }
    "planner-pubsub"          = { service = "ai-planner", role = "roles/pubsub.publisher" }
    "fusion-pubsub"           = { service = "fusion-engine", role = "roles/pubsub.publisher" }
  }
  
  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.services[each.value.service].email}"
}