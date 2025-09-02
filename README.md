# End to End Multimodal Pipeline

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

## Lab Data: The Future Factories Dataset

To build and validate the Resolve Agent, we use a real-world dataset from the Future Factories Lab at the University of South Carolina. This dataset is a rare commodity in manufacturing AI—open-source, high-fidelity, and purpose-built for developing intelligent systems.

**What It Contains:**

Two industry-grade datasets collected during continuous assembly-line runs, using industrial-grade robots, conveyors, actuators, sensors, and cameras.

One dataset is analog, time-series sensor telemetry, capturing every nuance of the manufacturing process over a sustained runtime.

The other is multi-modal, aligning those sensor readings with synchronized images. This pairing simulates how a smart system "sees and feels" what's happening.

**Why It Matters:**

Anomalies are injected deliberately—parts are removed during assembly (e.g., missing nose cone), creating ground truth defects to train AI fault detection.

Data is realistic and structured: Sensor data in CSV or JSON logs; images batch-organized and precisely aligned.

Addresses a critical gap—public industrial datasets with both anomalies and multimodal signals are rare. This dataset fills that gap and serves as a robust foundation for building and testing AI-driven manufacturing pipelines.

In our playbook, this dataset becomes the lab testbed to prove the pipeline works—not just on paper, but in real-world aligned data. It allows us to skip the fusion engine when inputs are already synchronized, but still execute agentic, bounded decision-making with full safety observability.

**Citation:** Harik, R., El Kalach, F., Samaha, J., Clark, D., Sander, D., Samaha, P., Burns, L., Yousif, I., Gadow, V., Tarekegne, T., & Saha, N. (2024). Analog and Multi-modal Manufacturing Datasets Acquired on the Future Factories Platform. *arXiv:2401.15544 [cs.LG]*. https://doi.org/10.48550/arXiv.2401.15544

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

Special acknowledgment to the Future Factories Lab at the University of South Carolina for providing the industry-grade multimodal manufacturing datasets that serve as the foundation for this pipeline.

We thank the research team led by Ramy Harik for making these valuable datasets available for research and development in manufacturing AI.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**MIT License**  
Copyright (c) 2025 Data Engineering for Multimodal AI

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**Note**: This is a prototype implementation for demonstration purposes. Production deployment requires additional security hardening, compliance validation, and regulatory approval.