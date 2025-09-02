# API Reference

This document provides comprehensive API documentation for all microservices in the Resolve Agent multimodal AI pipeline.

## Table of Contents

1. [Data Ingester API](#data-ingester-api)
2. [Historical Processor API](#historical-processor-api)
3. [Fusion Engine API](#fusion-engine-api)
4. [AI Planner API](#ai-planner-api)
5. [Common Response Formats](#common-response-formats)
6. [Error Handling](#error-handling)

## Data Ingester API

**Base URL**: `https://data-ingester-{hash}.{region}.run.app`

### POST /ingest

Processes multimodal data from Google Cloud Storage and publishes to Pub/Sub topics.

**Request Body**:
```json
{
  "json_files": ["data_31000.json", "data_32000.json"],
  "session_id": "optional-session-identifier"
}
```

**Parameters**:
- `json_files` (array): List of JSON file names in GCS bucket
- `session_id` (string, optional): Session identifier for tracking

**Response**:
```json
{
  "session_id": "ff-session-20250901-123456",
  "processed_records": 100,
  "published_telemetry": 100,
  "published_images": 200,
  "status": "success"
}
```

**Example**:
```bash
curl -X POST https://data-ingester-xxxxx.us-central1.run.app/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "json_files": ["data_31000.json"],
    "session_id": "demo-session"
  }'
```

### GET /health

Returns service health status and connectivity to dependencies.

**Response**:
```json
{
  "status": "healthy",
  "service": "data_ingester",
  "version": "2.0"
}
```

## Historical Processor API

**Base URL**: `https://historical-processor-{hash}.{region}.run.app`

### POST /process

Processes historical analog data from Excel files and builds statistical baselines.

**Request Body**:
```json
{
  "files": [
    "R01_Data.xlsx", "R02_Data.xlsx", "R03_Data.xlsx", "R04_Data.xlsx",
    "Conveyor_Signals.csv", "FFCellSafetyManagement.xlsx", "FFCell_CycleManagement.xlsx"
  ],
  "force_refresh": false
}
```

**Parameters**:
- `files` (array): List of Excel/CSV files to process
- `force_refresh` (boolean): Whether to reprocess existing baselines

**Response**:
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

**Example**:
```bash
curl -X POST https://historical-processor-xxxxx.us-central1.run.app/process \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["R01_Data.xlsx", "R02_Data.xlsx"],
    "force_refresh": true
  }'
```

### GET /baselines/{component}

Retrieves historical baselines for a specific component.

**Parameters**:
- `component` (path): Component identifier (e.g., "r01", "conveyor_system")

**Response**:
```json
{
  "component": "r01",
  "baselines": {
    "temperature": {
      "mean": 85.2,
      "std": 5.1,
      "percentile_95": 92.3,
      "sample_count": 10000
    },
    "speed": {
      "mean": 120.5,
      "std": 8.2,
      "percentile_95": 135.1,
      "sample_count": 10000
    }
  }
}
```

### GET /health

Returns service health status.

**Response**:
```json
{
  "status": "healthy",
  "service": "historical_processor",
  "version": "2.0"
}
```

## Fusion Engine API

**Base URL**: `https://fusion-engine-{hash}.{region}.run.app`

### POST /webhook/telemetry

Webhook endpoint for receiving telemetry data from Pub/Sub.

**Request Body** (Pub/Sub format):
```json
{
  "message": {
    "data": "base64-encoded-telemetry-record",
    "messageId": "message-id",
    "publishTime": "2025-09-01T23:00:00Z"
  }
}
```

**Response**:
```json
{
  "status": "processed",
  "message_id": "message-id"
}
```

### POST /webhook/images

Webhook endpoint for receiving image data from Pub/Sub.

**Request Body** (Pub/Sub format):
```json
{
  "message": {
    "data": "base64-encoded-image-record",
    "messageId": "message-id", 
    "publishTime": "2025-09-01T23:00:00Z"
  }
}
```

**Response**:
```json
{
  "status": "processed",
  "message_id": "message-id"
}
```

### GET /status

Returns fusion engine processing status.

**Response**:
```json
{
  "active_sessions": 2,
  "active_windows": 183,
  "fusion_window_seconds": 30,
  "status": "healthy"
}
```

**Fields**:
- `active_sessions`: Number of sessions currently being processed
- `active_windows`: Number of time windows with data
- `fusion_window_seconds`: Time window size for correlation

### GET /health

Returns service health status.

**Response**:
```json
{
  "status": "healthy",
  "service": "fusion_engine",
  "version": "2.0"
}
```

## AI Planner API

**Base URL**: `https://ai-planner-{hash}.{region}.run.app`

### POST /plan

Creates an action plan using multimodal AI analysis.

**Request Body**:
```json
{
  "fused_record": {
    "timestamp": "2025-09-01T23:00:00Z",
    "session_id": "demo-session",
    "trace_id": "trace-001",
    "telemetry_data": {
      "Q_VFD1_Temperature": 85.2,
      "Q_VFD2_Temperature": 88.1,
      "M_Conv1_Speed_mmps": 1200,
      "I_SafetyDoor1_Status": 1,
      "Q_Cell_CycleCount": 31045
    },
    "image_uris": [
      "gs://bucket/path/image_0.png",
      "gs://bucket/path/image_1.png"
    ]
  }
}
```

**Response**:
```json
{
  "plan_id": "plan-trace-001",
  "session_id": "demo-session",
  "trace_id": "trace-001",
  "timestamp": "2025-09-01T23:00:00Z",
  "actions": [
    {
      "action": "reduce_conveyor_speed",
      "priority": "medium",
      "reasoning": "VFD temperatures elevated above historical baseline",
      "parameters": {
        "target_speed": 95,
        "duration_minutes": 10
      }
    }
  ],
  "reasoning": "Temperature readings show 15% elevation above normal operating range",
  "confidence": 0.87,
  "historical_context": {
    "deviations": {
      "Q_VFD1_Temperature": {
        "current": 85.2,
        "baseline_mean": 74.1,
        "deviation_percent": 15.0
      }
    },
    "baselines_used": 4
  },
  "multimodal_analysis": {
    "visual_anomalies": "Excessive vibration visible in conveyor assembly",
    "sensor_correlations": "High temperature correlates with increased motor load",
    "risk_assessment": "Medium risk of equipment damage if conditions persist"
  },
  "status": "success"
}
```

**Action Types**:
- `reduce_conveyor_speed`: Slow down conveyor operation
- `increase_cooling`: Activate additional cooling systems
- `alert_maintenance`: Notify maintenance personnel
- `emergency_stop`: Immediate system shutdown
- `log_incident`: Record for historical analysis

**Priority Levels**:
- `critical`: Immediate action required
- `high`: Action needed within 5 minutes
- `medium`: Action needed within 30 minutes
- `low`: Action for next maintenance window

### POST /webhook/fused

Webhook endpoint for receiving fused records from Pub/Sub.

**Request Body** (Pub/Sub format):
```json
{
  "message": {
    "data": "base64-encoded-fused-record",
    "messageId": "message-id",
    "publishTime": "2025-09-01T23:00:00Z"
  }
}
```

**Response**:
```json
{
  "status": "processed",
  "trace_id": "trace-001"
}
```

### GET /health

Returns service health status with dependency connectivity.

**Response**:
```json
{
  "status": "healthy",
  "service": "ai_planner",
  "version": "2.0",
  "timestamp": "2025-09-01T23:00:00.123456",
  "project_id": "your-project-id",
  "region": "us-central1",
  "vertex_ai": "connected",
  "bigquery": "connected", 
  "gcs": "connected"
}
```

**Status Values**:
- `healthy`: All systems operational
- `degraded`: Some dependencies unavailable but core functionality works
- `unhealthy`: Critical dependencies unavailable

## Common Response Formats

### Success Response

All successful API calls return a response with at minimum:

```json
{
  "status": "success",
  "timestamp": "2025-09-01T23:00:00.123456Z"
}
```

### Error Response

All error responses follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Missing required field: sensor_values",
    "details": {
      "field": "sensor_values",
      "expected_type": "object"
    }
  },
  "status": "error",
  "timestamp": "2025-09-01T23:00:00.123456Z"
}
```

### Pagination Response

For endpoints that return multiple items:

```json
{
  "items": [...],
  "pagination": {
    "total_count": 150,
    "page_size": 50,
    "current_page": 1,
    "total_pages": 3,
    "next_page_token": "eyJ0aW1lc3RhbXAiOiIyMDI1LTA5LTAxVDIzOjAwOjAwWiJ9"
  },
  "status": "success"
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request format or missing required fields
- `401 Unauthorized`: Authentication required or invalid
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource or endpoint not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server-side error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Code Categories

**Validation Errors** (4xx):
- `VALIDATION_ERROR`: Request validation failed
- `SCHEMA_ERROR`: Data doesn't match expected schema
- `MISSING_FIELD`: Required field not provided
- `INVALID_FORMAT`: Data format incorrect

**Processing Errors** (5xx):
- `PROCESSING_ERROR`: Error during data processing
- `DEPENDENCY_ERROR`: External service unavailable
- `AI_ERROR`: AI analysis failed
- `STORAGE_ERROR`: Storage operation failed

### Rate Limiting

All APIs implement rate limiting:

**Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1693526400
```

**Rate Limit Response** (429):
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after": 60
  }
}
```

### Retryable Errors

These errors should be retried with exponential backoff:
- `500 Internal Server Error`
- `503 Service Unavailable`
- `429 Too Many Requests`

**Retry Strategy**:
```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError:
            if attempt == max_retries - 1:
                raise
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
```

## Authentication

All services use Google Cloud IAM for authentication:

**Service Account Authentication**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
```

**Request Headers**:
```
Authorization: Bearer $(gcloud auth print-access-token)
Content-Type: application/json
```

**Required IAM Roles**:
- Data Ingester: `pubsub.publisher`, `storage.objectViewer`
- Historical Processor: `bigquery.dataEditor`, `storage.objectViewer`
- Fusion Engine: `pubsub.subscriber`, `pubsub.publisher`
- AI Planner: `aiplatform.user`, `bigquery.dataViewer`, `storage.objectViewer`

## SDK Examples

### Python

```python
import requests
import json

class ResolveAgentClient:
    def __init__(self, base_urls):
        self.base_urls = base_urls
        
    def ingest_data(self, json_files, session_id=None):
        response = requests.post(
            f"{self.base_urls['data_ingester']}/ingest",
            json={
                "json_files": json_files,
                "session_id": session_id
            }
        )
        return response.json()
    
    def process_historical(self, files, force_refresh=False):
        response = requests.post(
            f"{self.base_urls['historical_processor']}/process",
            json={
                "files": files,
                "force_refresh": force_refresh
            }
        )
        return response.json()
    
    def create_action_plan(self, fused_record):
        response = requests.post(
            f"{self.base_urls['ai_planner']}/plan",
            json={"fused_record": fused_record}
        )
        return response.json()
```

### JavaScript/Node.js

```javascript
class ResolveAgentClient {
    constructor(baseUrls) {
        this.baseUrls = baseUrls;
    }

    async ingestData(jsonFiles, sessionId = null) {
        const response = await fetch(`${this.baseUrls.dataIngester}/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                json_files: jsonFiles,
                session_id: sessionId
            })
        });
        return response.json();
    }

    async createActionPlan(fusedRecord) {
        const response = await fetch(`${this.baseUrls.aiPlanner}/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fused_record: fusedRecord })
        });
        return response.json();
    }
}
```

For complete API testing examples and integration patterns, see the `examples/` directory in the repository.
