# Complete Tutorial: Building a Multimodal AI Pipeline

This tutorial will guide you through building and deploying a production-ready multimodal AI pipeline for manufacturing data analysis. You'll learn core concepts and execute each step with detailed explanations.

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Understanding the Architecture](#understanding-the-architecture)
3. [Step 1: Infrastructure Deployment](#step-1-infrastructure-deployment)
4. [Step 2: Service Deployment](#step-2-service-deployment)
5. [Step 3: Historical Context Setup](#step-3-historical-context-setup)
6. [Step 4: Real-time Data Processing](#step-4-real-time-data-processing)
7. [Step 5: AI Analysis Verification](#step-5-ai-analysis-verification)
8. [Understanding the Results](#understanding-the-results)
9. [Next Steps](#next-steps)

## Prerequisites & Setup

### Required Tools

Before starting, ensure you have:

- **Google Cloud Account**: With billing enabled
- **gcloud CLI**: Authenticated and configured
- **Python 3.11+**: For running deployment scripts
- **Terraform**: For infrastructure as code
- **Git**: For cloning the repository

### Concept: Why These Tools?

- **gcloud CLI**: Manages Google Cloud resources programmatically
- **Terraform**: Ensures reproducible infrastructure deployment
- **Python**: Provides deployment orchestration and service logic
- **Cloud Run**: Serverless container platform for microservices

### Setup Commands

```bash
# Verify gcloud authentication
gcloud auth list

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs (this may take 3-5 minutes)
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    pubsub.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com

# Clone the repository
git clone https://github.com/Data-Engineering-for-Multimodal-AI/playbook-00-multimodal-end-to-end-pipeline.git
cd playbook-00-multimodal-end-to-end-pipeline/cloud

# Install Python dependencies
pip install -r requirements.txt
```

**Expected Output**: 
- `gcloud auth list` shows your authenticated account
- APIs are enabled (you'll see "Operation finished successfully")
- Dependencies install without errors

## Understanding the Architecture

### Core Concept: Multimodal AI Pipeline

A multimodal AI pipeline processes different types of data simultaneously:

- **Sensor Data**: Numerical measurements (temperature, speed, pressure)
- **Visual Data**: Images from cameras or sensors
- **Historical Data**: Past patterns for context and anomaly detection

### Why This Architecture?

**Microservices Design**: Each component has a single responsibility
- **Scalability**: Services scale independently based on load
- **Reliability**: Failure in one service doesn't crash the entire system
- **Maintainability**: Easy to update or replace individual components

**Event-Driven Communication**: Uses Pub/Sub for loose coupling
- **Asynchronous**: Services don't wait for each other
- **Resilient**: Messages are queued if services are temporarily unavailable
- **Scalable**: Handles varying message volumes automatically

### Data Flow Explanation

```
1. Data Ingester reads raw data from Google Cloud Storage
2. Validates data against predefined schemas
3. Publishes telemetry and images to separate Pub/Sub topics
4. Fusion Engine subscribes to both topics
5. Correlates data by timestamp (within 30-second windows)
6. Creates "fused records" combining sensor + image data
7. AI Planner receives fused records
8. Downloads images and analyzes with Gemini
9. Compares against historical baselines
10. Generates action plans based on anomalies
```

## Step 1: Infrastructure Deployment

### Concept: Infrastructure as Code

Terraform defines your cloud infrastructure in code, making it:
- **Reproducible**: Same infrastructure every time
- **Version-controlled**: Track changes over time
- **Collaborative**: Team can review infrastructure changes

### Execute Infrastructure Deployment

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Review planned changes
terraform plan -var="project_id=YOUR_PROJECT_ID"

# Deploy infrastructure
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

**Expected Output**:
```
Apply complete! Resources: 12 added, 0 changed, 0 destroyed.

Outputs:
project_id = "your-project-id"
pubsub_topics = ["telemetry.v1", "images.v1", "fused.v1", "actions.v1"]
bigquery_dataset = "resolve"
```

### What Was Created?

**Pub/Sub Topics**: Message queues for service communication
- `telemetry.v1`: Sensor measurements
- `images.v1`: Image references and metadata
- `fused.v1`: Combined sensor + image records
- `actions.v1`: AI-generated action plans

**BigQuery Resources**:
- `resolve` dataset: Data warehouse for analytics
- `historical_baselines` table: Statistical patterns from historical data

**Service Accounts**: Identity and access management
- Each service gets its own account with minimal required permissions
- Follows principle of least privilege for security

**Code Deep Dive**: Look at `infra/terraform/main.tf`
- Resource blocks define each cloud component
- Variables allow customization without code changes
- Outputs provide information for other deployment steps

## Step 2: Service Deployment

### Concept: Containerized Microservices

Each service is packaged as a Docker container and deployed to Cloud Run:
- **Isolation**: Each service runs in its own environment
- **Portability**: Containers run consistently across environments
- **Auto-scaling**: Cloud Run scales containers based on request volume

### Execute Service Deployment

```bash
cd ../../  # Return to project root

# Deploy all services
python deploy.py --project-id YOUR_PROJECT_ID --region us-central1
```

**Expected Output**:
```
Building and deploying container to Cloud Run service [data-ingester]...
✓ Building Container... 
✓ Creating Revision...
✓ Routing traffic...
Service URL: https://data-ingester-xxxxx.us-central1.run.app

[Similar output for historical-processor, fusion-engine, ai-planner]

DEPLOYMENT COMPLETE
================================================================================
Project ID: your-project-id
Region: us-central1  
Services Deployed: 4
```

### What Was Deployed?

**Data Ingester Service** (`services/data_ingester/main.py`):
- Reads JSON files from Google Cloud Storage
- Validates sensor data against expected schema
- Publishes to Pub/Sub topics with rate limiting
- **Key Code**: FastAPI endpoints, GCS client, schema validation

**Historical Processor** (`services/historical_processor/main.py`):
- Processes Excel files with operational data
- Calculates statistical baselines (mean, std deviation)
- Stores results in BigQuery for historical context
- **Key Code**: Pandas for Excel processing, BigQuery integration

**Fusion Engine** (`services/fusion_engine/main.py`):
- Receives telemetry and images via Pub/Sub webhooks
- Groups data by session and time windows
- Creates fused records when both data types are available
- **Key Code**: Time-based correlation logic, webhook handling

**AI Planner** (`services/ai_planner/main.py`):
- Downloads images from Google Cloud Storage
- Calls Vertex AI Gemini for multimodal analysis
- Compares current data against historical baselines
- Generates bounded action plans with confidence scores
- **Key Code**: Vertex AI integration, image processing, prompt engineering

### Verify Deployment

```bash
# Check service health
curl https://data-ingester-xxxxx.us-central1.run.app/health
curl https://historical-processor-xxxxx.us-central1.run.app/health
curl https://fusion-engine-xxxxx.us-central1.run.app/health
curl https://ai-planner-xxxxx.us-central1.run.app/health
```

**Expected Output** (for each service):
```json
{
  "status": "healthy",
  "service": "data_ingester",
  "version": "2.0"
}
```

## Step 3: Historical Context Setup

### Concept: Historical Baselines

Manufacturing systems need historical context to detect anomalies:
- **Baselines**: Normal operating ranges for each measurement
- **Seasonality**: Patterns that repeat over time
- **Drift Detection**: Gradual changes in system behavior

### Execute Historical Processing

```bash
# Trigger historical data processing
curl -X POST https://historical-processor-xxxxx.us-central1.run.app/process \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      "R01_Data.xlsx", "R02_Data.xlsx", "R03_Data.xlsx", "R04_Data.xlsx",
      "Conveyor_Signals.csv", "FFCellSafetyManagement.xlsx", "FFCell_CycleManagement.xlsx"
    ],
    "force_refresh": true
  }'
```

**Expected Output**:
```json
{
  "processed_files": 7,
  "extracted_baselines": 32,
  "safety_incidents": 287954,
  "total_cycles": 287954,
  "status": "success",
  "timestamp": "2025-09-01T23:58:50.725447"
}
```

### What Happened?

**Data Processing**: 
- Excel files read from Google Cloud Storage
- Numerical columns analyzed for statistical patterns
- Safety incidents and cycle counts extracted

**Baseline Calculation**:
```python
# Simplified version of the calculation
for each_measurement in sensor_data:
    baseline = {
        'mean': data.mean(),
        'std': data.std(),
        'percentile_95': data.quantile(0.95),
        'sample_count': len(data)
    }
```

**BigQuery Storage**: Baselines stored for AI Planner to use

### Verify Historical Processing

```bash
# Check AI Planner health (should now show BigQuery connectivity)
curl https://ai-planner-xxxxx.us-central1.run.app/health
```

**Expected Output**:
```json
{
  "status": "healthy",
  "service": "ai_planner",
  "version": "2.0",
  "vertex_ai": "connected",
  "bigquery": "connected",
  "gcs": "connected"
}
```

## Step 4: Real-time Data Processing

### Concept: Event-Driven Data Pipeline

Real-time processing means data flows through the system automatically:
- **Publishers** send messages to topics
- **Subscribers** process messages asynchronously
- **Time-based correlation** aligns different data types

### Execute Data Ingestion

```bash
# Trigger multimodal data ingestion
curl -X POST https://data-ingester-xxxxx.us-central1.run.app/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "json_files": ["data_31000.json", "data_32000.json"],
    "session_id": "tutorial-demo"
  }'
```

**Expected Output**:
```json
{
  "session_id": "tutorial-demo",
  "processed_records": 100,
  "published_telemetry": 100,
  "published_images": 200,
  "status": "success"
}
```

### Understanding the Data Flow

**What the Data Ingester Did**:
1. Read JSON files from `gs://your-bucket/datasets/future-factories/`
2. Parsed each timestamped record
3. Validated sensor measurements against schema
4. Published 100 telemetry messages to `telemetry.v1` topic
5. Published 200 image references to `images.v1` topic

**Sample Processed Record**:
```json
{
  "timestamp": "2023-12-11T16:03:03.372569Z",
  "sensor_values": {
    "Q_VFD1_Temperature": 90.13,
    "Q_VFD2_Temperature": 87.13,
    "M_Conv1_Speed_mmps": 111,
    "I_R01_Gripper_Load": 480
  },
  "images": [
    "gs://bucket/path/image_0.png",
    "gs://bucket/path/image_1.png"
  ]
}
```

### Verify Fusion Processing

```bash
# Wait for Pub/Sub delivery and check fusion status
sleep 10
curl https://fusion-engine-xxxxx.us-central1.run.app/status
```

**Expected Output**:
```json
{
  "active_sessions": 1,
  "active_windows": 90,
  "fusion_window_seconds": 30,
  "status": "healthy"
}
```

**What This Means**:
- **Active Sessions**: 1 session (`tutorial-demo`) being processed
- **Active Windows**: 90 time windows (30-second intervals) with data
- **Fusion Logic**: Correlating sensor data with images by timestamp

## Step 5: AI Analysis Verification

### Concept: Multimodal AI Analysis

The AI Planner combines multiple data types for intelligent analysis:
- **Sensor Analysis**: Detects numerical anomalies vs historical baselines
- **Visual Analysis**: Processes images for visual anomalies
- **Contextual Reasoning**: Uses historical patterns for better decisions

### Monitor AI Processing

```bash
# Check Cloud Run logs for AI analysis
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="ai-planner" AND textPayload:"Creating action plan"' \
  --limit=5 --format="value(timestamp,textPayload)"
```

**Expected Output**:
```
2025-09-01T23:31:27.776859Z    Creating action plan for trace 34dd577c-48a9-4c9c-9fb5-07b9048baa61
2025-09-01T23:31:26.956884Z    Creating action plan for trace eb410c7a-6a5b-4ce7-92bf-e3ff60865e3c
```

### Understanding AI Analysis Process

**What Happens in the AI Planner**:

1. **Receive Fused Record**: Gets sensor data + image references
2. **Historical Context**: Queries BigQuery for relevant baselines
3. **Deviation Analysis**: Compares current vs historical values
4. **Image Download**: Retrieves images from Google Cloud Storage
5. **Multimodal Prompt**: Creates structured prompt for Gemini
6. **AI Analysis**: Calls Vertex AI for intelligent reasoning
7. **Action Generation**: Creates bounded action plans
8. **Safety Validation**: Ensures actions are within safe parameters

**Sample AI Prompt Structure**:
```
MANUFACTURING CELL ANALYSIS

Current Sensor Data:
- VFD1 Temperature: 90.13°C (Historical avg: 85.2°C)
- Conveyor Speed: 111 mm/s (Historical avg: 120.5 mm/s)

Historical Context:
- Temperature deviations: 15% above normal
- Speed deviations: 8% below normal

Images: [Manufacturing cell images for visual analysis]

Task: Analyze for anomalies and recommend actions.
```

### Verify End-to-End Success

```bash
# Run the complete pipeline verification
python run_pipeline_cloud.py
```

**Expected Output**:
```
Starting complete Future Factories pipeline...
Processing historical data to build baselines...
Historical processing complete:
   Extracted 32 baselines
   Safety incidents: 287954
   Total cycles: 287954

Data ingestion complete:
   Processed 100 timestamped records
   Published 100 telemetry messages
   Published 200 image references

Pipeline processing complete
Pipeline execution complete!

Summary:
   Historical baselines extracted from Excel files
   Multimodal data ingested (JSON + images)
   Data fused with time synchronization
   AI analysis with historical context
   Safety validation and action planning
```

## Understanding the Results

### AI-Generated Action Plans

The pipeline generates intelligent action plans based on multimodal analysis:

**Example Action Plan**:
```json
{
  "plan_id": "plan-trace-001",
  "session_id": "tutorial-demo",
  "actions": [
    {
      "action": "reduce_conveyor_speed",
      "priority": "medium", 
      "reasoning": "VFD temperatures elevated 15% above baseline",
      "parameters": {"target_speed": 95}
    },
    {
      "action": "alert_maintenance",
      "priority": "low",
      "reasoning": "Visual inspection shows normal operation"
    }
  ],
  "confidence": 0.87,
  "multimodal_analysis": {
    "temperature_trend": "increasing",
    "visual_anomalies": "none detected",
    "correlation": "high temperature correlates with increased load"
  }
}
```

### Data Analytics

**BigQuery Analysis**: Query your results
```sql
-- Check historical baselines
SELECT component, metric, mean, std, sample_count 
FROM `your-project.resolve.historical_baselines`
ORDER BY component, metric;

-- Analyze processed records (if stored)
SELECT session_id, COUNT(*) as record_count
FROM `your-project.resolve.processed_records` 
GROUP BY session_id;
```

**Cloud Console**: Monitor in real-time
- **Cloud Run Logs**: See detailed service execution
- **Pub/Sub Monitoring**: Track message flow and latency
- **BigQuery**: Analyze processed data and results

### Performance Insights

**Scalability Demonstrated**:
- Processed 100 records with 200 images automatically
- Services auto-scaled based on load
- Total processing time: ~2-3 minutes for complete pipeline

**Cost Optimization**:
- Gemini 2.5 Flash-Lite: Cost-effective multimodal analysis
- Cloud Run: Pay only for actual usage
- Pub/Sub: Efficient message queuing with minimal overhead

## Next Steps

### Extend the Pipeline

**Add More Data Types**:
```python
# In data_ingester/main.py, add audio processing
async def process_audio_data(audio_files):
    for audio_file in audio_files:
        # Process audio with speech-to-text
        # Extract audio features
        # Publish to audio.v1 topic
        pass
```

**Custom AI Analysis**:
```python
# In ai_planner/main.py, add custom models
def analyze_with_custom_model(sensor_data):
    # Load your trained model
    # Perform custom analysis
    # Return predictions
    pass
```

**Real-time Dashboards**:
- Connect BigQuery to Data Studio
- Create real-time monitoring dashboards
- Set up alerting for critical issues

### Production Deployment

**Enhanced Security**:
- Enable VPC for private networking
- Use Cloud Armor for DDoS protection
- Implement proper IAM with service account keys

**Monitoring & Alerting**:
- Cloud Monitoring for metrics
- Error Reporting for exception tracking
- Custom alerts for business logic failures

**CI/CD Pipeline**:
- GitHub Actions for automated testing
- Cloud Build for container builds
- Terraform for infrastructure updates

### Learning Resources

**Google Cloud Documentation**:
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/best-practices)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Pub/Sub Patterns](https://cloud.google.com/pubsub/docs/patterns)

**Sample Datasets**:
- Explore more Future Factories data
- Adapt pipeline for your own manufacturing data
- Test with different data formats and schemas

Congratulations! You've successfully built and deployed a production-ready multimodal AI pipeline. The system can now process real manufacturing data, detect anomalies, and generate intelligent action plans using state-of-the-art AI technology.
