# Resolve Agent: Multimodal AI Pipeline for Manufacturing

A production-ready multimodal AI pipeline for manufacturing that ingests sensor data, images, and historical records to generate intelligent action plans using Google Cloud Platform and Vertex AI.

## Overview

This pipeline processes multimodal data from manufacturing systems (Future Factories dataset) and provides intelligent analysis using:

- **Real-time sensor data** (temperatures, speeds, gripper loads)
- **Manufacturing cell images** (camera feeds from production floor)
- **Historical baselines** (Excel files with operational patterns)
- **AI-powered analysis** (Gemini 2.5 Flash-Lite for multimodal understanding)

## Architecture

The system consists of four main microservices deployed on Google Cloud Run:

```
GCS (Future Factories Data) 
    ↓
Data Ingester → Pub/Sub → Fusion Engine → AI Planner → Action Plans
    ↓                                           ↑
Historical Processor → BigQuery Baselines ──────┘
```

### Core Components

1. **Data Ingester**: Reads JSON sensor data and image references from GCS
2. **Historical Processor**: Analyzes Excel files to build operational baselines 
3. **Fusion Engine**: Correlates sensor data with images using time windows
4. **AI Planner**: Uses Gemini for multimodal analysis with historical context

## Quick Start

### Prerequisites

- Google Cloud Project with billing enabled
- Terraform installed
- Python 3.11+
- gcloud CLI authenticated

### One-Command Deployment

```bash
git clone <repository-url>
cd resolve-agent

# Install dependencies
pip install -r requirements.txt

# Deploy complete pipeline
python deploy.py --project-id YOUR_PROJECT_ID --region us-central1

# Run pipeline
python run_pipeline.py
```

## Tutorial Guide

For detailed step-by-step instructions, see [TUTORIAL.md](TUTORIAL.md)

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md) 
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Development Setup](docs/DEVELOPMENT.md)

## Key Features

### Production-Ready Infrastructure
- Containerized microservices on Cloud Run
- Auto-scaling with demand
- Comprehensive health checks
- Production logging and monitoring

### Enhanced AI Capabilities  
- True multimodal analysis (sensor data + images)
- Historical context for anomaly detection
- Safety validation and bounded action planning
- Cost-effective LLM usage (Gemini 2.5 Flash-Lite)

### Data Processing
- Schema validation for all data types
- Time-synchronized data fusion
- Rate limiting and error handling
- BigQuery integration for analytics

## Sample Output

The pipeline processes real manufacturing data and generates intelligent action plans:

```json
{
  "plan_id": "plan-trace-001",
  "actions": [
    {
      "action": "reduce_conveyor_speed",
      "priority": "medium",
      "reasoning": "VFD temperatures elevated above historical baseline"
    }
  ],
  "confidence": 0.87,
  "multimodal_analysis": {
    "visual_anomalies": "Excessive vibration visible in conveyor assembly",
    "sensor_deviations": "Temperature readings 15% above normal"
  }
}
```

## Data Sources

The pipeline is designed for the **Future Factories** multimodal dataset:
- **Sensor Data**: JSON files with timestamped measurements
- **Images**: Manufacturing cell camera feeds  
- **Historical Data**: Excel files with operational baselines

## Technology Stack

- **Cloud Platform**: Google Cloud Platform
- **Containerization**: Docker + Cloud Run
- **AI/ML**: Vertex AI (Gemini 2.5 Flash-Lite)
- **Data Storage**: Cloud Storage, BigQuery
- **Messaging**: Cloud Pub/Sub
- **Infrastructure**: Terraform
- **Languages**: Python 3.11, FastAPI

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality  
5. Submit a pull request

## Support

For questions and support:
- Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review [Architecture Documentation](docs/ARCHITECTURE.md)
- Open an issue on GitHub

## Acknowledgments

We thank the original dataset creators and the UCI Machine Learning Repository for making these valuable datasets available for research and development.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note**: This is a prototype implementation for demonstration purposes. Production deployment requires additional security hardening, compliance validation, and regulatory approval.