# Development Setup Guide

This guide helps developers set up a local development environment for the Resolve Agent multimodal AI pipeline.

## Table of Contents

1. [Development Environment](#development-environment)
2. [Local Development Setup](#local-development-setup)
3. [Running Services Locally](#running-services-locally)
4. [Testing](#testing)
5. [Debugging](#debugging)
6. [Contributing Guidelines](#contributing-guidelines)

## Development Environment

### Prerequisites

**Required Tools**:
- Python 3.11+ (pyenv recommended for version management)
- Docker Desktop
- Google Cloud SDK (gcloud)
- Terraform 1.0+
- Git
- VS Code or PyCharm (recommended IDEs)

**Google Cloud Setup**:
```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set project and region
gcloud config set project YOUR_DEV_PROJECT_ID
gcloud config set compute/region us-central1
```

### Python Environment

```bash
# Install pyenv (macOS)
brew install pyenv

# Install Python 3.11
pyenv install 3.11.5
pyenv global 3.11.5

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

### IDE Configuration

**VS Code Extensions**:
- Python
- Docker
- Terraform
- Google Cloud Code
- REST Client (for API testing)

**VS Code Settings** (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/venv": true
    }
}
```

## Local Development Setup

### 1. Environment Variables

Create `.env` file in project root:
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-dev-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Service Configuration
GCS_BUCKET=your-dev-bucket
PUBSUB_TOPIC_PREFIX=dev
BIGQUERY_DATASET=resolve_dev

# Development Settings
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### 2. Local Google Cloud Emulators

**Pub/Sub Emulator**:
```bash
# Install emulator
gcloud components install pubsub-emulator

# Start emulator
gcloud beta emulators pubsub start --project=test-project

# Set environment variables (in another terminal)
$(gcloud beta emulators pubsub env-init)
```

**BigQuery Emulator** (Alternative: Use Cloud BigQuery with dev dataset):
```bash
# Create development dataset
bq mk --dataset --location=US your-project:resolve_dev
```

### 3. Docker Compose for Local Development

Create `docker-compose.dev.yml`:
```yaml
version: '3.8'
services:
  pubsub-emulator:
    image: google/cloud-sdk:latest
    command: gcloud beta emulators pubsub start --host-port=0.0.0.0:8085
    ports:
      - "8085:8085"
    environment:
      - CLOUDSDK_CORE_PROJECT=test-project

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: resolve_dev
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start local services:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Running Services Locally

### 1. Data Ingester Service

```bash
cd services/data_ingester

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_CLOUD_PROJECT=your-dev-project
export GCS_BUCKET=your-dev-bucket
export PUBSUB_EMULATOR_HOST=localhost:8085

# Run service
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

Test endpoint:
```bash
curl http://localhost:8081/health
```

### 2. Historical Processor Service

```bash
cd services/historical_processor

# Run service
uvicorn main:app --host 0.0.0.0 --port 8082 --reload
```

### 3. Fusion Engine Service

```bash
cd services/fusion_engine

# Run service  
uvicorn main:app --host 0.0.0.0 --port 8083 --reload
```

### 4. AI Planner Service

```bash
cd services/ai_planner

# Run service
uvicorn main:app --host 0.0.0.0 --port 8084 --reload
```

### 5. Development Script

Create `run_dev.py` for easy local development:
```python
#!/usr/bin/env python
import subprocess
import time
import sys
from pathlib import Path

def start_service(service_name, port):
    """Start a service in development mode"""
    service_path = Path(f"services/{service_name}")
    if not service_path.exists():
        print(f"Service {service_name} not found")
        return None
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "main:app", 
        "--host", "0.0.0.0", 
        "--port", str(port),
        "--reload"
    ]
    
    print(f"Starting {service_name} on port {port}")
    return subprocess.Popen(cmd, cwd=service_path)

def main():
    services = [
        ("data_ingester", 8081),
        ("historical_processor", 8082), 
        ("fusion_engine", 8083),
        ("ai_planner", 8084)
    ]
    
    processes = []
    try:
        for service_name, port in services:
            proc = start_service(service_name, port)
            if proc:
                processes.append(proc)
                time.sleep(2)  # Stagger startup
        
        print("All services started. Press Ctrl+C to stop.")
        for proc in processes:
            proc.wait()
            
    except KeyboardInterrupt:
        print("Stopping services...")
        for proc in processes:
            proc.terminate()

if __name__ == "__main__":
    main()
```

Run all services:
```bash
python run_dev.py
```

## Testing

### Unit Tests

**Test Structure**:
```
tests/
├── unit/
│   ├── test_data_ingester.py
│   ├── test_historical_processor.py
│   ├── test_fusion_engine.py
│   └── test_ai_planner.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_pubsub_flow.py
└── fixtures/
    ├── sample_data.json
    └── sample_baselines.json
```

**Example Unit Test**:
```python
# tests/unit/test_data_ingester.py
import pytest
from unittest.mock import Mock, patch
from services.data_ingester.main import validate_sensor_data, app
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    return TestClient(app)

def test_validate_sensor_data():
    valid_data = {
        "Q_VFD1_Temperature": 85.0,
        "M_Conv1_Speed_mmps": 120,
        "I_SafetyDoor1_Status": 1
    }
    assert validate_sensor_data(valid_data) == True

def test_validate_sensor_data_missing_field():
    invalid_data = {
        "Q_VFD1_Temperature": 85.0
        # Missing required fields
    }
    assert validate_sensor_data(invalid_data) == False

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@patch('services.data_ingester.main.storage_client')
@patch('services.data_ingester.main.publisher')
def test_ingest_endpoint(mock_publisher, mock_storage, client):
    # Mock GCS and Pub/Sub
    mock_blob = Mock()
    mock_blob.download_as_text.return_value = '{"timestamp": "2023-01-01T00:00:00Z", "sensor_values": {"Q_VFD1_Temperature": 85.0}}'
    
    mock_bucket = Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_storage.bucket.return_value = mock_bucket
    
    response = client.post("/ingest", json={
        "json_files": ["test_data.json"],
        "session_id": "test"
    })
    
    assert response.status_code == 200
    assert "processed_records" in response.json()
```

**Run Tests**:
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html

# Run specific test file
pytest tests/unit/test_data_ingester.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Integration Tests

**Example Integration Test**:
```python
# tests/integration/test_end_to_end.py
import pytest
import asyncio
import json
from pathlib import Path

@pytest.mark.asyncio
async def test_complete_pipeline():
    """Test complete pipeline flow"""
    
    # 1. Upload test data to GCS
    test_data = {
        "2023-01-01T00:00:00Z": {
            "Sensor_values": {
                "Q_VFD1_Temperature": 95.0,  # High temperature
                "M_Conv1_Speed_mmps": 120
            },
            "Images": ["test_image.png"]
        }
    }
    
    # 2. Trigger data ingestion
    ingestion_response = await call_data_ingester(["test_data.json"])
    assert ingestion_response["status"] == "success"
    
    # 3. Wait for fusion processing
    await asyncio.sleep(10)
    
    # 4. Check fusion status
    fusion_status = await get_fusion_status()
    assert fusion_status["active_windows"] > 0
    
    # 5. Wait for AI analysis
    await asyncio.sleep(30)
    
    # 6. Verify action plan was generated
    action_plans = await get_action_plans()
    assert len(action_plans) > 0
    assert any("temperature" in plan["reasoning"].lower() for plan in action_plans)
```

### Load Testing

**Using Locust**:
```python
# locustfile.py
from locust import HttpUser, task, between

class ResolveAgentUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def health_check(self):
        self.client.get("/health")
    
    @task(1)
    def ingest_data(self):
        self.client.post("/ingest", json={
            "json_files": ["data_31000.json"],
            "session_id": f"load-test-{self.client.session_id}"
        })
```

Run load test:
```bash
pip install locust
locust -f locustfile.py --host=http://localhost:8081
```

## Debugging

### Local Debugging with VS Code

**Launch Configuration** (`.vscode/launch.json`):
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Data Ingester",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/venv/bin/uvicorn",
            "args": ["services.data_ingester.main:app", "--host", "0.0.0.0", "--port", "8081", "--reload"],
            "cwd": "${workspaceFolder}",
            "env": {
                "GOOGLE_CLOUD_PROJECT": "your-dev-project",
                "PUBSUB_EMULATOR_HOST": "localhost:8085"
            }
        }
    ]
}
```

### Logging Configuration

**Development Logging** (`logging_config.py`):
```python
import logging
import sys

def setup_logging(level=logging.DEBUG):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('debug.log')
        ]
    )
    
    # Set specific loggers
    logging.getLogger('google.cloud').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
```

### Debugging Pub/Sub Messages

**Message Inspector** (`debug_pubsub.py`):
```python
import base64
import json
from google.cloud import pubsub_v1

def inspect_messages(subscription_name, max_messages=10):
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(
        "test-project", subscription_name
    )
    
    def callback(message):
        try:
            data = json.loads(message.data.decode('utf-8'))
            print(f"Message ID: {message.message_id}")
            print(f"Data: {json.dumps(data, indent=2)}")
            print("-" * 50)
        except Exception as e:
            print(f"Error processing message: {e}")
        
        message.ack()
    
    print(f"Listening for messages on {subscription_name}...")
    flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)
    streaming_pull_future = subscriber.subscribe(
        subscription_path, callback=callback, flow_control=flow_control
    )
    
    try:
        streaming_pull_future.result(timeout=30)
    except KeyboardInterrupt:
        streaming_pull_future.cancel()

if __name__ == "__main__":
    inspect_messages("fusion-telemetry-sub")
```

### API Testing with REST Client

**VS Code REST Client** (`.vscode/api-tests.http`):
```http
### Health Check - Data Ingester
GET http://localhost:8081/health

### Ingest Data
POST http://localhost:8081/ingest
Content-Type: application/json

{
  "json_files": ["data_31000.json"],
  "session_id": "debug-session"
}

### Health Check - AI Planner
GET http://localhost:8084/health

### Create Action Plan
POST http://localhost:8084/plan
Content-Type: application/json

{
  "fused_record": {
    "timestamp": "2023-01-01T00:00:00Z",
    "session_id": "debug-session",
    "trace_id": "debug-trace-001",
    "telemetry_data": {
      "Q_VFD1_Temperature": 95.0,
      "M_Conv1_Speed_mmps": 120
    },
    "image_uris": []
  }
}
```

## Contributing Guidelines

### Code Style

**Python Style**:
- Follow PEP 8
- Use Black for formatting
- Use isort for import sorting
- Maximum line length: 88 characters

**Pre-commit Hooks** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

Install pre-commit:
```bash
pip install pre-commit
pre-commit install
```

### Git Workflow

**Branch Naming**:
- `feature/description`: New features
- `bugfix/description`: Bug fixes
- `hotfix/description`: Critical fixes
- `refactor/description`: Code refactoring

**Commit Messages**:
```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Process

1. Create feature branch from `main`
2. Implement changes with tests
3. Ensure all tests pass
4. Update documentation if needed
5. Create pull request with description
6. Request code review
7. Address review feedback
8. Merge after approval

### Development Checklist

**Before Committing**:
- [ ] All tests pass locally
- [ ] Code is formatted with Black
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Environment variables documented
- [ ] Error handling implemented
- [ ] Logging added for debugging

**Before Pull Request**:
- [ ] Integration tests pass
- [ ] Performance impact considered
- [ ] Security implications reviewed
- [ ] Breaking changes documented
- [ ] Migration path provided (if applicable)

### Local Development Tips

**Faster Development Cycle**:
```bash
# Use file watching for auto-restart
pip install watchdog
watchmedo auto-restart --patterns="*.py" --recursive -- python -m uvicorn services.data_ingester.main:app --reload

# Use pytest-watch for continuous testing
pip install pytest-watch
ptw tests/ -- --testmon
```

**Mock External Services**:
```python
# Use responses library for HTTP mocking
import responses

@responses.activate
def test_external_api():
    responses.add(
        responses.GET,
        "https://api.external.com/data",
        json={"result": "mocked"},
        status=200
    )
    # Test code here
```

This development setup provides a comprehensive environment for local development, testing, and debugging of the Resolve Agent multimodal AI pipeline.
