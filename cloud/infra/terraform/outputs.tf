output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP region"
  value       = var.region
}

output "pubsub_topics" {
  description = "Created Pub/Sub topics"
  value       = [for topic in google_pubsub_topic.topics : topic.name]
}

output "bigquery_dataset" {
  description = "BigQuery dataset"
  value       = google_bigquery_dataset.resolve.dataset_id
}

output "service_accounts" {
  description = "Service account emails"
  value = {
    for sa in google_service_account.services : sa.account_id => sa.email
  }
}