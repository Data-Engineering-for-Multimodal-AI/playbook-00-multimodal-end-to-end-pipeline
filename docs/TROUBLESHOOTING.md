# Troubleshooting Guide

This guide helps diagnose and resolve common issues when deploying and running the Resolve Agent multimodal AI pipeline.

## Table of Contents

1. [Prerequisites Issues](#prerequisites-issues)
2. [Infrastructure Deployment](#infrastructure-deployment)
3. [Service Deployment](#service-deployment)  
4. [Data Processing Issues](#data-processing-issues)
5. [AI Analysis Problems](#ai-analysis-problems)
6. [Performance Issues](#performance-issues)
7. [Monitoring and Debugging](#monitoring-and-debugging)

## Prerequisites Issues

### Problem: gcloud authentication fails

**Symptoms**:
```bash
ERROR: (gcloud.auth.login) There was a problem with the web browser
```

**Solution**:
```bash
# Use service account authentication instead
gcloud auth activate-service-account --key-file=path/to/service-account.json

# Or use application default credentials
gcloud auth application-default login
```

**Verification**:
```bash
gcloud auth list
# Should show active account with asterisk
```

### Problem: Project not found or access denied

**Symptoms**:
```
ERROR: (gcloud.projects.describe) User does not have permission to access project
```

**Solution**:
```bash
# Verify project ID
gcloud projects list

# Set correct project
gcloud config set project YOUR_CORRECT_PROJECT_ID

# Verify billing is enabled
gcloud billing accounts list
gcloud billing projects link YOUR_PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

### Problem: Required APIs not enabled

**Symptoms**:
```
PERMISSION_DENIED: Cloud Run API has not been used in project
```

**Solution**:
```bash
# Enable all required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    pubsub.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com

# Wait 2-3 minutes for API activation
sleep 180
```

**Verification**:
```bash
gcloud services list --enabled | grep -E "(run|build|pubsub|bigquery|storage|aiplatform)"
```

## Infrastructure Deployment

### Problem: Terraform initialization fails

**Symptoms**:
```
Error: Failed to query available provider packages
```

**Solution**:
```bash
cd infra/terraform

# Clear terraform cache
rm -rf .terraform/

# Re-initialize with verbose output
terraform init -upgrade

# If using corporate network, configure proxy
export HTTPS_PROXY=your-proxy:port
terraform init
```

### Problem: Insufficient permissions for Terraform

**Symptoms**:
```
Error: Error creating Topic: googleapi: Error 403: Permission denied
```

**Solution**:
```bash
# Grant required IAM roles to your account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@domain.com" \
    --role="roles/editor"

# Or use a service account with required permissions
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
terraform apply
```

### Problem: Resource already exists errors

**Symptoms**:
```
Error: Error creating Topic "telemetry.v1": Topic already exists
```

**Solution**:
```bash
# Import existing resources into Terraform state
terraform import google_pubsub_topic.telemetry projects/YOUR_PROJECT_ID/topics/telemetry.v1

# Or destroy and recreate (data loss warning!)
terraform destroy -target=google_pubsub_topic.telemetry
terraform apply
```

### Problem: BigQuery dataset deletion protection

**Symptoms**:
```
Error: Cannot destroy table without setting deletion_protection=false
```

**Solution**:
```bash
# Manually disable deletion protection
bq update --set_deletion_protection=false YOUR_PROJECT_ID:resolve.historical_baselines

# Then run terraform
terraform apply
```

## Service Deployment

### Problem: Cloud Run deployment timeout

**Symptoms**:
```
ERROR: Revision failed to start within allocated timeout
```

**Solution**:
```bash
# Increase timeout and memory
gcloud run deploy SERVICE_NAME \
    --source=services/SERVICE_NAME/ \
    --timeout=900 \
    --memory=2Gi \
    --cpu=2

# Check build logs for errors
gcloud logging read "resource.type=build" --limit=10
```

### Problem: Container fails to start

**Symptoms**:
```
ERROR: The user-provided container failed to start and listen on the port
```

**Solution**:
```bash
# Check if port is correctly configured
# Ensure Dockerfile exposes correct port
EXPOSE 8080

# Check if application binds to 0.0.0.0, not localhost
uvicorn main:app --host 0.0.0.0 --port $PORT

# Test container locally
docker build -t test-service services/SERVICE_NAME/
docker run -p 8080:8080 -e PORT=8080 test-service
```

### Problem: Service health check failures

**Symptoms**:
```json
{
  "status": "unhealthy",
  "error": "Connection timeout"
}
```

**Solution**:
```bash
# Check service logs
gcloud logging read \
    'resource.type="cloud_run_revision" AND resource.labels.service_name="SERVICE_NAME"' \
    --limit=20

# Verify dependencies are accessible
curl SERVICE_URL/health

# Check IAM permissions
gcloud run services get-iam-policy SERVICE_NAME --region=REGION
```

## Data Processing Issues

### Problem: Data ingestion returns 404 errors

**Symptoms**:
```json
{
  "error": "404 Resource not found (resource=images.v1)"
}
```

**Solution**:
```bash
# Verify Pub/Sub topics exist
gcloud pubsub topics list

# Create missing topics
gcloud pubsub topics create images.v1
gcloud pubsub topics create telemetry.v1

# Check service account permissions
gcloud pubsub topics get-iam-policy TOPIC_NAME
```

### Problem: No data in GCS bucket

**Symptoms**:
```
ERROR: 404 No such object: bucket/path/data_31000.json
```

**Solution**:
```bash
# Verify bucket exists and has data
gsutil ls gs://your-project-id-resolve-binaries/datasets/

# Check bucket permissions
gsutil iam get gs://BUCKET_NAME

# Upload sample data if missing
gsutil cp local-data/* gs://BUCKET_NAME/datasets/future-factories/
```

### Problem: Schema validation failures

**Symptoms**:
```json
{
  "error": "Validation failed: Missing required field Q_VFD1_Temperature"
}
```

**Solution**:
```python
# Check data format
import json
with open('data_31000.json') as f:
    data = json.load(f)
    
# Verify structure matches expected schema
required_fields = [
    "Q_VFD1_Temperature", "Q_VFD2_Temperature", 
    "M_Conv1_Speed_mmps", "I_SafetyDoor1_Status"
]

for timestamp, record in data.items():
    sensor_values = record.get("Sensor_values", {})
    missing_fields = [f for f in required_fields if f not in sensor_values]
    if missing_fields:
        print(f"Missing fields: {missing_fields}")
```

## AI Analysis Problems

### Problem: Vertex AI authentication errors

**Symptoms**:
```
ERROR: Failed to call Vertex AI: 401 Unauthorized
```

**Solution**:
```bash
# Verify Vertex AI API is enabled
gcloud services list --enabled | grep aiplatform

# Check service account has AI Platform permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:ai-planner-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Test Vertex AI access
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    "https://us-central1-aiplatform.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/endpoints"
```

### Problem: Gemini model not found

**Symptoms**:
```
ERROR: Model gemini-2.5-flash-lite not found in region us-central1
```

**Solution**:
```bash
# List available models
gcloud ai models list --region=us-central1

# Use correct model name
# Update ai_planner/main.py:
model = GenerativeModel("gemini-1.5-pro")  # or available model

# Check region availability
gcloud ai locations list
```

### Problem: Image download failures

**Symptoms**:
```
ERROR: Failed to download image: 404 No such object
```

**Solution**:
```python
# Debug image URI parsing
def debug_image_uri(image_uri):
    print(f"Original URI: {image_uri}")
    
    if image_uri.startswith("gs://"):
        parts = image_uri.replace("gs://", "").split("/", 1)
        bucket_name = parts[0]
        blob_path = parts[1] if len(parts) > 1 else ""
        
        print(f"Bucket: {bucket_name}")
        print(f"Path: {blob_path}")
        
        # Test if blob exists
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        print(f"Exists: {blob.exists()}")

# Check actual image paths in data
gsutil ls "gs://bucket/datasets/future-factories/multimodal-2024-data/Batch 1/BATCH31000/" | head -5
```

### Problem: AI analysis timeout

**Symptoms**:
```
ERROR: Request timeout after 120 seconds
```

**Solution**:
```bash
# Increase Cloud Run timeout
gcloud run services update ai-planner \
    --timeout=900 \
    --region=us-central1

# Reduce image count for analysis
# In ai_planner/main.py:
for image_uri in request.fused_record.image_uris[:1]:  # Process only 1 image

# Use async processing for large batches
# Implement background tasks
```

## Performance Issues

### Problem: Slow data processing

**Symptoms**:
- Pipeline takes >10 minutes to process 100 records
- High latency in service responses

**Solution**:
```bash
# Scale up Cloud Run services
gcloud run services update SERVICE_NAME \
    --max-instances=10 \
    --cpu=2 \
    --memory=2Gi \
    --region=us-central1

# Enable concurrency
gcloud run services update SERVICE_NAME \
    --concurrency=100 \
    --region=us-central1

# Monitor resource usage
gcloud logging read \
    'resource.type="cloud_run_revision" AND jsonPayload.severity="INFO"' \
    --limit=50
```

### Problem: High AI analysis costs

**Symptoms**:
- Unexpected charges from Vertex AI usage
- Many AI API calls

**Solution**:
```python
# Implement request caching
import hashlib
import json

def cache_ai_request(request_data):
    cache_key = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
    # Check if result exists in cache (Redis/Memcache)
    # Return cached result if available
    
# Reduce image resolution
def resize_image(image_data):
    from PIL import Image
    img = Image.open(image_data)
    img = img.resize((512, 512))  # Reduce from high resolution
    return img

# Batch multiple records
def batch_ai_analysis(fused_records):
    # Analyze multiple records in single AI call
    pass
```

### Problem: Pub/Sub message backlog

**Symptoms**:
```bash
# Check message backlog
gcloud pubsub subscriptions describe SUBSCRIPTION_NAME
# Shows large undelivered message count
```

**Solution**:
```bash
# Scale subscriber services
gcloud run services update fusion-engine \
    --max-instances=20 \
    --concurrency=1000

# Increase acknowledgment deadline
gcloud pubsub subscriptions update SUBSCRIPTION_NAME \
    --ack-deadline=600

# Implement dead letter queue
gcloud pubsub topics create dlq-topic
gcloud pubsub subscriptions update SUBSCRIPTION_NAME \
    --dead-letter-topic=dlq-topic \
    --max-delivery-attempts=5
```

## Monitoring and Debugging

### Problem: Can't find service logs

**Solution**:
```bash
# List available logs
gcloud logging logs list | grep cloud_run

# View specific service logs
gcloud logging read \
    'resource.type="cloud_run_revision" AND resource.labels.service_name="ai-planner"' \
    --limit=50 \
    --format="value(timestamp,textPayload)"

# Filter by severity
gcloud logging read \
    'resource.type="cloud_run_revision" AND severity>=ERROR' \
    --limit=20

# Tail logs in real-time
gcloud logging tail \
    'resource.type="cloud_run_revision" AND resource.labels.service_name="fusion-engine"'
```

### Problem: Understanding system state

**Solution**:
```bash
# Check all service health
for service in data-ingester historical-processor fusion-engine ai-planner; do
    echo "=== $service ==="
    curl -s "https://$service-PROJECT_HASH.us-central1.run.app/health" | python -m json.tool
done

# Monitor Pub/Sub topics
for topic in telemetry.v1 images.v1 fused.v1 actions.v1; do
    echo "=== $topic ==="
    gcloud pubsub topics describe $topic
done

# Check BigQuery data
bq query --use_legacy_sql=false \
    'SELECT component, COUNT(*) as baseline_count 
     FROM `PROJECT_ID.resolve.historical_baselines` 
     GROUP BY component'
```

### Problem: Performance analysis

**Solution**:
```bash
# Create monitoring dashboard queries
# CPU usage
gcloud logging read \
    'resource.type="cloud_run_revision" AND jsonPayload.message:"CPU utilization"' \
    --format="csv(timestamp,jsonPayload.cpu_utilization)"

# Memory usage  
gcloud logging read \
    'resource.type="cloud_run_revision" AND jsonPayload.message:"Memory usage"' \
    --format="csv(timestamp,jsonPayload.memory_mb)"

# Request latency
gcloud logging read \
    'resource.type="cloud_run_revision" AND httpRequest.latency' \
    --format="csv(timestamp,httpRequest.latency)"
```

## Common Error Patterns

### Pattern: Service can't connect to dependencies

**Symptoms**: 
- Connection timeout errors
- 503 Service Unavailable

**Debug Steps**:
```bash
# 1. Check service status
gcloud run services list --region=us-central1

# 2. Verify IAM permissions
gcloud run services get-iam-policy SERVICE_NAME --region=us-central1

# 3. Test connectivity
curl -v SERVICE_URL/health

# 4. Check network configuration
gcloud compute networks list
```

### Pattern: Data validation failures

**Symptoms**:
- 400 Bad Request errors
- Schema validation messages

**Debug Steps**:
```python
# 1. Validate data format
import json
with open('sample_data.json') as f:
    data = json.load(f)
    print(json.dumps(data, indent=2)[:500])

# 2. Check schema requirements
# Compare against schemas/ directory

# 3. Test with minimal valid record
test_record = {
    "timestamp": "2023-12-11T16:03:03.372569Z",
    "sensor_values": {
        "Q_VFD1_Temperature": 85.0,
        "M_Conv1_Speed_mmps": 120
    }
}
```

### Pattern: AI analysis inconsistencies

**Symptoms**:
- Different results for same input
- Confidence scores vary widely

**Debug Steps**:
```python
# 1. Check prompt consistency
def debug_prompt(fused_record):
    prompt = generate_enhanced_prompt(fused_record, deviations)
    print("=== PROMPT ===")
    print(prompt)
    print("=== END PROMPT ===")

# 2. Verify image quality
def check_image_quality(image_uri):
    blob = storage_client.bucket(bucket).blob(path)
    size = blob.size
    print(f"Image size: {size} bytes")
    if size < 1000:
        print("WARNING: Image too small")

# 3. Test with known good data
test_cases = [
    {"description": "normal operation", "expected": "no actions"},
    {"description": "high temperature", "expected": "cooling action"},
]
```

If you continue to experience issues not covered in this guide, please:

1. Check the [Architecture Documentation](ARCHITECTURE.md) for system design details
2. Review service logs for specific error messages
3. Verify all prerequisites are properly configured
4. Test components individually to isolate the problem
5. Open an issue on GitHub with detailed error logs and steps to reproduce
