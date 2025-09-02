# Architecture Overview

This document provides a comprehensive technical overview of the Resolve Agent multimodal AI pipeline architecture.

## System Architecture

### High-Level Design

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│  Google Cloud   │    │   Pub/Sub        │    │  Cloud Run      │
│  Storage        │────▶  Message Queue   │────▶  Microservices │
│                 │    │                  │    │                 │
│ - JSON Data     │    │ - telemetry.v1   │    │ - Data Ingester │
│ - Images        │    │ - images.v1      │    │ - Fusion Engine │
│ - Excel Files   │    │ - fused.v1       │    │ - AI Planner    │
│                 │    │ - actions.v1     │    │ - Historical    │
└─────────────────┘    └──────────────────┘    │   Processor     │
                                               └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│  BigQuery       │    │   Vertex AI      │    │  Cloud          │
│  Data Warehouse │    │   AI Platform    │    │  Monitoring     │
│                 │    │                  │    │                 │
│ - Baselines     │    │ - Gemini 2.5     │    │ - Logs          │
│ - Analytics     │    │   Flash-Lite     │    │ - Metrics       │
│ - Results       │    │ - Multimodal     │    │ - Alerts        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Service Communication Pattern

```
Data Flow: Event-Driven Architecture

1. Data Ingester ──┬─► telemetry.v1 ──┐
                   └─► images.v1 ─────┤
                                      ├─► Fusion Engine ─► fused.v1 ─► AI Planner ─► actions.v1
                                      │
2. Historical Processor ─────────────► BigQuery ──────────────────────┘
                                       (baselines)
```

## Component Architecture

### 1. Data Ingester Service

**Responsibility**: Multimodal data ingestion and validation

```python
# Core functionality
class DataIngester:
    def read_from_gcs(bucket: str, file_path: str) -> Dict
    def validate_schema(data: Dict) -> bool  
    def publish_to_pubsub(topic: str, message: Dict) -> str
    def rate_limit(max_records: int = 100) -> bool
```

**Key Design Patterns**:
- **Schema Validation**: Ensures data quality before processing
- **Rate Limiting**: Prevents system overload
- **Error Handling**: Graceful degradation with detailed logging
- **Batch Processing**: Optimizes throughput vs latency

**Technology Stack**:
- FastAPI for REST endpoints
- Google Cloud Storage client
- Pub/Sub publisher
- Pydantic for data validation

### 2. Historical Processor Service

**Responsibility**: Historical context and baseline establishment

```python
# Core functionality  
class HistoricalProcessor:
    def read_excel_from_gcs(file_path: str) -> pd.DataFrame
    def calculate_baselines(data: pd.DataFrame) -> List[Baseline]
    def store_in_bigquery(baselines: List[Baseline]) -> bool
    def analyze_safety_incidents(data: pd.DataFrame) -> Dict
```

**Statistical Analysis**:
- **Descriptive Statistics**: Mean, standard deviation, percentiles
- **Trend Analysis**: Long-term pattern identification  
- **Seasonality Detection**: Cyclical pattern recognition
- **Anomaly Thresholds**: Dynamic threshold calculation

**Technology Stack**:
- Pandas for data analysis
- OpenPyXL for Excel processing
- BigQuery client for storage
- Tenacity for retry logic

### 3. Fusion Engine Service

**Responsibility**: Time-synchronized multimodal data correlation

```python
# Core functionality
class FusionEngine:
    def receive_webhook(data_type: str, message: Dict) -> bool
    def correlate_by_time(window_seconds: int = 30) -> List[FusedRecord]
    def handle_late_arrivals(max_delay: int = 60) -> bool
    def publish_fused_records(records: List[FusedRecord]) -> bool
```

**Fusion Algorithm**:
```python
def fuse_records(telemetry_records, image_records, window_size=30):
    """
    Time-based correlation algorithm:
    1. Group records by session_id
    2. Create time windows (30-second intervals)
    3. Match telemetry and images within each window
    4. Create fused record if both types present
    5. Handle late-arriving data (up to 60 seconds)
    """
    fused_records = []
    for session in sessions:
        windows = create_time_windows(session.records, window_size)
        for window in windows:
            if has_telemetry(window) and has_images(window):
                fused_record = FusedRecord(
                    timestamp=window.start_time,
                    telemetry_data=window.telemetry,
                    image_uris=window.images,
                    session_id=session.id
                )
                fused_records.append(fused_record)
    return fused_records
```

**Technology Stack**:
- FastAPI for webhook endpoints
- In-memory time window management
- Pub/Sub for input/output messaging

### 4. AI Planner Service

**Responsibility**: Intelligent multimodal analysis and action planning

```python
# Core functionality
class AIPlanner:
    def analyze_deviations(current: Dict, baselines: Dict) -> List[Deviation]
    def download_images_for_analysis(uris: List[str]) -> List[Part]
    def generate_multimodal_prompt(fused_record: FusedRecord) -> str
    def call_gemini_analysis(prompt: str, images: List[Part]) -> str
    def extract_action_plan(ai_response: str) -> ActionPlan
```

**AI Analysis Pipeline**:
```python
def analyze_fused_record(fused_record: FusedRecord) -> ActionPlan:
    """
    Multimodal AI analysis process:
    1. Query historical baselines from BigQuery
    2. Calculate statistical deviations
    3. Download and prepare images
    4. Construct enhanced prompt with context
    5. Call Gemini 2.5 Flash-Lite for analysis
    6. Parse AI response for structured output
    7. Validate and bound action recommendations
    """
    # Historical context
    baselines = get_historical_baselines()
    deviations = analyze_deviations(fused_record.telemetry_data, baselines)
    
    # Multimodal preparation
    images = download_images_for_analysis(fused_record.image_uris)
    prompt = generate_enhanced_prompt(fused_record, deviations)
    
    # AI analysis
    content_parts = [prompt] + images
    response = gemini_model.generate_content(content_parts)
    
    # Action plan extraction
    action_plan = extract_action_plan(response.text)
    return validate_and_bound_actions(action_plan)
```

**Prompt Engineering**:
```
MANUFACTURING CELL MULTIMODAL ANALYSIS

HISTORICAL CONTEXT:
{statistical_baselines}

CURRENT SENSOR DATA:
{timestamped_measurements}

DEVIATION ANALYSIS:
{statistical_deviations}

VISUAL INPUT:
{manufacturing_cell_images}

TASK: Analyze the manufacturing cell state using both sensor data and visual information. Consider:
1. Statistical deviations from historical baselines
2. Visual anomalies in manufacturing equipment
3. Correlation between sensor readings and visual observations
4. Safety implications of current state
5. Preventive maintenance opportunities

OUTPUT: JSON action plan with reasoning, confidence, and bounded recommendations.
```

**Technology Stack**:
- Vertex AI Gemini 2.5 Flash-Lite
- Google Cloud Storage for image access
- BigQuery for historical context
- Custom prompt engineering

## Data Models

### Core Data Structures

```python
# Sensor measurement record
class TelemetryRecord(BaseModel):
    timestamp: str
    session_id: str
    sensor_values: Dict[str, float]
    trace_id: str

# Image reference record  
class ImageRecord(BaseModel):
    timestamp: str
    session_id: str
    image_uris: List[str]
    trace_id: str

# Time-correlated multimodal record
class FusedRecord(BaseModel):
    timestamp: str
    session_id: str
    trace_id: str
    telemetry_data: Dict[str, Any]
    image_uris: List[str]
    historical_context: Optional[Dict[str, Any]] = None

# AI-generated action plan
class ActionPlan(BaseModel):
    plan_id: str
    session_id: str
    trace_id: str
    timestamp: str
    actions: List[Action]
    reasoning: str
    confidence: float
    multimodal_analysis: Dict[str, Any]

class Action(BaseModel):
    action: str
    priority: str  # critical, high, medium, low
    reasoning: str
    parameters: Dict[str, Any] = {}
```

### Schema Validation

**Sensor Data Schema**:
```json
{
  "type": "object",
  "required": ["timestamp", "sensor_values"],
  "properties": {
    "timestamp": {"type": "string", "format": "date-time"},
    "sensor_values": {
      "type": "object",
      "required": ["Q_VFD1_Temperature", "M_Conv1_Speed_mmps"],
      "properties": {
        "Q_VFD1_Temperature": {"type": "number", "minimum": 0, "maximum": 200},
        "M_Conv1_Speed_mmps": {"type": "number", "minimum": 0, "maximum": 2000}
      }
    }
  }
}
```

## Infrastructure Architecture

### Google Cloud Platform Services

**Compute Layer**:
- **Cloud Run**: Serverless container hosting
  - Auto-scaling from 0 to N instances
  - Pay-per-request pricing model
  - Built-in HTTPS and load balancing

**Storage Layer**:
- **Cloud Storage**: Raw data and images
  - Multi-regional for availability
  - Lifecycle management for cost optimization
- **BigQuery**: Analytics and baselines
  - Serverless data warehouse
  - SQL interface for analysis

**Messaging Layer**:
- **Pub/Sub**: Asynchronous communication
  - At-least-once delivery guarantee
  - Auto-scaling message processing
  - Dead letter queues for error handling

**AI/ML Layer**:
- **Vertex AI**: Managed AI platform
  - Gemini 2.5 Flash-Lite for multimodal analysis
  - Built-in scaling and optimization
  - Cost-effective inference pricing

### Security Architecture

**Identity and Access Management (IAM)**:
```yaml
Service Accounts:
  data-ingester-sa:
    permissions:
      - storage.objects.get
      - pubsub.messages.publish
  
  fusion-engine-sa:
    permissions:
      - pubsub.messages.receive
      - pubsub.messages.publish
  
  ai-planner-sa:
    permissions:
      - aiplatform.endpoints.predict
      - bigquery.jobs.create
      - storage.objects.get
```

**Network Security**:
- HTTPS-only communication
- Service-to-service authentication
- VPC-native when required
- Cloud Armor for DDoS protection

**Data Security**:
- Encryption at rest (default)
- Encryption in transit (TLS 1.2+)
- Audit logging for compliance
- Data retention policies

## Performance Characteristics

### Scalability Metrics

**Throughput**:
- Data Ingester: 1000+ records/minute
- Fusion Engine: 500+ fused records/minute  
- AI Planner: 50+ analyses/minute (limited by AI API)

**Latency**:
- End-to-end pipeline: 30-60 seconds
- Individual service response: <5 seconds
- AI analysis: 10-30 seconds per request

**Cost Optimization**:
- Cloud Run: Pay only for actual usage
- Gemini: Cost-effective multimodal model
- BigQuery: Serverless with automatic optimization
- Pub/Sub: Minimal overhead for messaging

### Reliability Features

**Error Handling**:
- Exponential backoff with jitter
- Circuit breaker patterns
- Dead letter queues
- Comprehensive logging

**Monitoring**:
- Health check endpoints
- Custom metrics and alerts
- Distributed tracing
- Performance dashboards

## Deployment Architecture

### Infrastructure as Code

**Terraform Modules**:
```
infra/
├── terraform/
│   ├── main.tf           # Core infrastructure
│   ├── variables.tf      # Configuration parameters
│   ├── outputs.tf        # Resource information
│   └── terraform.tfstate # State management
```

**Container Strategy**:
- Multi-stage Docker builds
- Security scanning
- Minimal base images
- Non-root execution

### CI/CD Integration

**Deployment Pipeline**:
```
1. Code Commit → GitHub
2. Automated Testing → GitHub Actions
3. Container Build → Cloud Build
4. Infrastructure Update → Terraform
5. Service Deployment → Cloud Run
6. Integration Testing → Automated verification
7. Production Release → Traffic routing
```

## Extension Points

### Adding New Data Types

```python
# Example: Adding audio data support
class AudioProcessor:
    def process_audio_file(self, audio_uri: str) -> AudioFeatures:
        # 1. Download audio from GCS
        # 2. Extract features (speech-to-text, audio classification)
        # 3. Publish to audio.v1 topic
        pass

# Update fusion engine
def correlate_multimodal_data(telemetry, images, audio):
    # Extend time window correlation to include audio
    pass
```

### Custom AI Models

```python
# Example: Adding custom ML model
class CustomAnalyzer:
    def load_model(self, model_path: str):
        # Load trained model from Vertex AI Model Registry
        pass
    
    def predict_anomalies(self, sensor_data: Dict) -> List[Anomaly]:
        # Run custom prediction logic
        pass
```

### Real-time Dashboards

```python
# Example: Streaming to monitoring dashboard
class DashboardStreamer:
    def stream_to_dashboard(self, metrics: Dict):
        # Stream real-time metrics to Data Studio
        # Or custom dashboard via WebSocket
        pass
```

This architecture provides a robust, scalable foundation for multimodal AI analysis in manufacturing environments while maintaining flexibility for future enhancements and customizations.
