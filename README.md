# Playbook 00: Turn factory sensor and camera data into an action plan
**How to build an end-to-end multimodal pipeline on Google Cloud.** A companion playbook for [*Data Engineering for Multimodal AI*](https://oreil.ly/data-engineering-multimodal) (O'Reilly, 2026). Not printed in the book.

A factory produces sensor readings, camera images and historical records, and an operator needs one plan of action from all of them. In this repo, we explore this with the Future Factories dataset. Follow along to run four services that ingest the data and ask Gemini for an action plan, locally with mocks or on Google Cloud.

**The problem.** Sensors, images and history each tell part of the story, and one decision needs all three.

**What you'll work with.** You'll split the pipeline into services, ingest each modality, ask an LLM (Gemini) to analyze them together, and use local mocks in place of the cloud services.

> The original Google Cloud steps are under [Run it the way the book does](#run-it-the-way-the-book-does) and are unchanged; they create paid resources. Want the repository as it was first published? Use the `first-edition` tag.

## Run it

You need [uv](https://docs.astral.sh/uv/) and `make`. No Docker, no cloud account. Or open the repo in a GitHub Codespace, where both are ready. On Windows without `make`, use a Codespace or run the commands shown in each step.

This runs the local mode: the same six stages as the cloud version in one process, with in-process topics in place of Pub/Sub, SQLite in place of BigQuery and rules in place of Gemini. Nothing calls Google Cloud.

**1. Get the code.** The clone is about 1 MB.

```bash
git clone https://github.com/Data-Engineering-for-Multimodal-AI/playbook-00-multimodal-end-to-end-pipeline.git
cd playbook-00-multimodal-end-to-end-pipeline
```

**2. Run the pipeline on the synthetic fixture.** Installs the locked dependencies (`uv sync --frozen`), writes a small stand-in for the Future Factories data (`python tests/fixture.py`), then runs the six stages on it (`python run_local.py`). On a fresh clone this took 39 s on a busy Mac, most of it installing the dependencies; the pipeline itself takes well under a second.

```bash
make run
```

You should see one line per stage:

```
1. Ingest:    10 readings, 1 rejected by the schema (sensor_values/Q_VFD1_Temperature: 1, ...)
2. Baselines: 8 sensors over 2,000 analog samples; hottest drive 90.0 +- 0.7 C (99th percentile 91.7)
3. Fusion:    9 records, 9 with both camera images (4 images downloaded)
4. Planning:  hottest drive 89.0-89.0 C; readings over 3 std from the usual: I_R03_Gripper_Load above 1
              actions proposed: {'door2_open_while_moving': 4, 'gripper_overload_r03': 1}; LLM: not configured
5. Safety:    approved {'emergency_stop': 2, 'alert_maintenance': 1}; blocked {'same action within 60 s': 2}
6. Store:     output/fixture/out/resolve.db; report in output/fixture/out/report.json (0.1 s in all)
```

The fixture has a reading with a broken drive temperature (rejected at ingest), safety door 2 open for four readings, and one reading where R03's gripper load is far above its usual range. The rules propose five actions; the safety check lets one emergency stop a minute through.

**3. Look at the store yourself.** Runs any SQL against the SQLite store, read-only (`python scripts/query.py`). With no `SQL=` it lists the action plans.

```bash
make query
```

```
ts                          action             rule                     status    detail
2023-12-11 10:01:00.000000  emergency_stop     door2_open_while_moving  approved
2023-12-11 10:01:20.000000  emergency_stop     door2_open_while_moving  blocked   same action within 60 s
2023-12-11 10:01:40.000000  emergency_stop     door2_open_while_moving  blocked   same action within 60 s
2023-12-11 10:02:00.000000  emergency_stop     door2_open_while_moving  approved
2023-12-11 10:03:00.000000  alert_maintenance  gripper_overload_r03     approved
(5 rows)
```

Try `make query SQL="SELECT * FROM rejected_readings"` or `SQL="SELECT metric, mean, std, implausible_count FROM historical_baselines"`. The tables are `historical_baselines`, `rejected_readings`, `fused_records` and `action_plans`.

**4. Run the tests.** The four tests on the fixture (`pytest tests/test_pipeline.py`).

```bash
make smoke
```

You should see `4 passed`.

**5. The real data (optional, Kaggle account).** Downloads a slice of the Future Factories data into `data/` (`python download_data.py`, about 830 MB), then runs the same pipeline on it (`python run_local.py`). Kaggle needs a free account and an API token in `~/.kaggle/kaggle.json` (or `KAGGLE_USERNAME` and `KAGGLE_KEY`). We didn't run this step for this update.

```bash
make run-real
```

**6. Clean up.**

```bash
make clean
```

This deletes `output/` (the fixture, the store and the reports, including `output/own/` from your own data), the test caches and `deployment.log`. A downloaded `data/` folder and the installed packages stay.

## How much time do you have?

| Time | What to do |
|---|---|
| 15 minutes | [Run it](#run-it), steps 1 to 4. On a Mac, step 2 took 39 s on a fresh clone. |
| 1 hour | The three [Try this](#try-this) experiments (a few seconds each), then change the rules in `schemas/ff_safety_policy_v1.yaml` and rerun `make run`. |
| 1 day | Download the real data (step 5), [use your own data](#use-your-own-data), and work through [Before production](#before-production). |

## Try this

Each experiment changes one thing and measures the effect, on synthetic data the script builds (so the numbers show the mechanism, not the real line). The numbers below are from a Mac on 2026-11-21. No cloud, no download.

**1. How long should fusion wait for the camera images?** Stage 3 fuses a reading without its images if they haven't arrived `FUSION_TIMEOUT_S` (5 s) after it. This replays 2,000 readings, one a second, with camera 1's images arriving after a random delay (2 s on average) and 5% of them lost.

```bash
make try-fusion-timeout
```

```
 timeout  both images  one image  image came later  wait p50  wait p95
    0.5s          768      1,232             1,131      1.0s      1.0s
      1s        1,178        822               721      1.5s      2.0s
      2s        1,469        531               430      1.5s      3.0s
      5s        1,791        209               108      1.5s      6.0s
     10s        1,889        111                10      1.5s     11.0s
     30s        1,899        101                 0      1.5s     31.0s
```

A short timeout fuses most records with one image, though the second one arrives soon after. A long one waits for every image that will ever come, and the slowest 5% of records wait half a minute. The timeout only fires when a later message arrives, so 0.5 s behaves like 1 s here. Change `CAMERA1_MEAN_DELAY_S` or `CAMERA1_LOSS` in `experiments/fusion_timeout.py` and see where the trade-off moves.

**2. How many emergency stops should one incident raise?** The safety check lets the same action for the same zone through once per `min_seconds_between_same_action` (60 s). This runs 20 minutes of readings in which safety door 2 is open twice while the conveyor runs: 180 s from minute 2, and 30 s from minute 8.

```bash
make try-rate-limit
```

```
interval  approved  blocked  first incident  second incident
      0s       210        0             180               30
     10s        21      189              18                3
     60s         4      206               3                1  (the policy)
    300s         2      208               1                1
    600s         1      209               1                0
```

Without a limit, one open door raises 180 stops. With 600 s, the second incident gets no stop at all, because the first one is less than 10 minutes old. Edit `OPEN` to move the second incident and see when 300 s starts to miss it too.

**3. What do a few broken sensor values do to the baselines?** The real drive temperature sensors sometimes report about 3e38. Stage 2 leaves values outside -40 to 150 C out of the baselines. This computes the baselines with and without that step, with more and more broken values in 2,000 samples, and checks whether a drive at 95 C still raises the "drive_hotter_than_usual" alert (z above 3).

```bash
make try-bad-values
```

```
broken values   raw mean   raw z  alert  cleaned mean  cleaned z  alert
            0         90    7.08    yes          90.0        7.1    yes
            1   1.49e+35   -0.02     no          90.0        7.1    yes
            5   7.45e+35   -0.05     no          90.0        7.1    yes
           20   2.98e+36   -0.10     no          90.0        7.1    yes
          100   1.49e+37   -0.23     no          90.0        7.1    yes
```

One broken value in 2,000 is enough to switch the alert off for good, without any error. Try a value that is wrong but plausible, such as 0 or 140, in `BROKEN` in `experiments/bad_values.py`: the range check no longer catches it.

## Use your own data

Put your data in a folder with the layout `download_data.py` writes into `data/`:

```
my_cell/
  analog/       Conveyor_Signals.csv  R01_Data.csv  R02_Data.csv  R03_Data.csv  R04_Data.csv
  multimodal/   data_<N>.json                    one batch: {"<timestamp>": {"Sensor_values": {...}, "Images": [...]}}
                BATCH<N>/<image>.png              optional: the images the batches reference
```

- The analog CSVs have a `_time` column (ISO 8601) and numeric sensor columns; `Conveyor_Signals.csv` needs `Q_VFD1_Temperature` to `Q_VFD4_Temperature`. They are the historical baselines.
- Each reading in a batch is checked against `schemas/ff_reading_v1.json` (the drive temperatures, conveyor speeds, safety doors and cycle count).

Check it first. This reads every file and writes nothing:

```bash
make check-data DIR=my_cell
```

It reports every file the pipeline can't use, and why: a missing analog file, a Git LFS pointer, text that isn't UTF-8, a CSV without `_time` or with timestamps it can't parse, missing drive temperature columns, a batch that isn't `data_<number>.json` or isn't valid JSON, a timestamp that appears twice (JSON would silently keep only the last reading), timestamps the pipeline can't parse or that go back in time (fusion's timeout needs them in order). Readings that fail the schema, broken temperatures in the analog files and images that aren't there are reported as notes: the pipeline handles them. On a folder with five problems:

```
5 problems in my_cell; nothing was written:
  analog/R02_Data.csv: missing
  analog/R04_Data.csv: a Git LFS pointer, not the file (run git lfs pull)
  multimodal/batch4.json: name must be data_<number>.json
  multimodal/data_2000.json: timestamp '2023-12-11 10:00:00' appears 2 times; only the last reading would be kept
  multimodal/data_3000.json: 1 timestamps the pipeline can't read (first '12/11/2023 10:00:00'); use ISO 8601, like 2023-12-11 13:00:00.000
```

When everything passes, run the pipeline on it:

```bash
make load DIR=my_cell
```

```
my_cell: OK, 10 readings
  note: analog/Conveyor_Signals.csv: 5 drive temperatures outside -40 to 150 C; the baselines leave them out
  note: multimodal/data_1.json: 1 of 10 readings fail schemas/ff_reading_v1.json and will be rejected (first: ...)
  note: multimodal/data_1.json: 16 image references with no file next to it; those records fuse without local images
...
6. Store:     output/own/resolve.db; report in output/own/report.json (0.0 s in all)
```

(This was the fixture, written with `uv run python tests/fixture.py my_cell`.) Query the result with `make query DB=output/own/resolve.db`.

## What you end up with

A local version of a four-service multimodal pipeline that turns sensor readings and camera images into checked action plans, with a SQLite store you can query and a loader for your own data.

Skills you'll practice:
- Validating each reading against a schema at ingest, and keeping the rejects
- Building baselines from history, and keeping bad values out of them
- Joining two streams by ID with a timeout (windowed fusion)
- Turning rules and deviations into proposed actions, and checking each one before it runs
- Choosing timeouts and rate limits by measuring their effect
- Replacing cloud services with local stand-ins to test a pipeline

## Before production

This playbook runs locally on a fixture. Before you run something like it on a real line:

1. **Fuse by event time, with a deliberate timeout.** `Fusion` waits 5 s of data time and only checks for expired records when a new message arrives. On the synthetic stream, 5 s fused 209 of 2,000 records with one image, and 108 of those second images arrived later ([Try this 1](#try-this)). The cloud `fusion_engine` fuses on the first image, so the second camera is always dropped there. *Chapter 7, "Windowed Fusion" (page 224) and "Event-Time Alignment" (page 218).*
2. **Keep bad values out of the baselines, and alert on them.** `baselines.compute` leaves temperatures outside -40 to 150 C out; without that, one broken value in 2,000 switched the overheating alert off ([Try this 3](#try-this)). Count the excluded values over time and alert when a sensor starts sending them. *Chapter 4, "What Happens When Validation Fails" (page 120).*
3. **Choose the rate limit per action.** One `min_seconds_between_same_action` (60 s) covers every action. 600 s missed a second door-open incident entirely ([Try this 2](#try-this)). An emergency stop may need a shorter limit, or none, than a maintenance alert. *Chapter 12, "Pattern 3: Back-Pressure and Fault Handling" (page 459).*
4. **Treat the LLM's actions like any other input.** With `--llm`, the model's reply is parsed from the first `{...}` in the text and goes through the same safety check. Log every prompt and reply, cap the calls, and keep the rules running when the model fails, as `run` already does. *Chapter 10, "Tiered Routing" (page 395) and "Causal Attribution and Adversarial Resilience" (page 388).*
5. **Version the schemas and policies.** `schemas/ff_reading_v1.json` and `ff_safety_policy_v1.yaml` are read from disk on every run, and the cloud version uses a different policy (`schemas/safety_policy.yaml`, a fixed 85 C stop that fires on 100% of the fixture's readings). Record which policy produced each action. *Chapter 12, "Pattern 1: On-the-Wire Contracts" (page 455); Chapter 8, "Data Versioning and Experiment Tracking for Multimodal AI" (page 276).*
6. **Keep the store across runs.** `Store` deletes `resolve.db` at the start of every run, so there is no history of actions. Append, and give each run an ID. *Chapter 6, "Hybrid Storage and Retrieval" (page 189).*
7. **Watch the pipeline.** The report has counts for one run. Export rejected readings, timeouts, proposed and blocked actions as metrics, per batch and per stage. *Chapter 12, "Signal Granularity: Instrument Each Lane" (page 474).*
8. **Lock down the cloud services before deploying.** `deploy.py` deploys four Cloud Run services, and `fusion-engine` keeps one instance running all the time (`min_instances: 1`). Check who can call each service and what an idle day costs before you deploy. *Chapter 11, "Protecting Data Across the Pipeline" (page 421); Chapter 9, "Cost Optimization for Cloud-Based Multimodal AI Infrastructure" (page 342).*
9. **Keep the data's license with it.** The Future Factories data is CC BY-SA 4.0. Record source, license and version for every batch you load (`download_data.py` writes `data/SOURCE.json`). *Chapter 11, "Lineage and Provenance Tracking" (page 416).*

## What it costs

| Where you run it | Cost |
|---|---|
| Your machine | $0. The local mode needs no API keys and calls no paid service. The clone is about 1 MB; the real data (step 5) about 830 MB, with a free Kaggle account. |
| A GitHub Codespace (2 cores, 8 GB, the default size; this repo doesn't ask for more) | Estimated $0.18 per hour at GitHub's list price (November 2026). A free personal account includes 120 core-hours a month, about 60 hours on this machine. In CI, `make run` in a freshly built devcontainer printed its first output after 2 s, because the dependencies are installed when the container is created. |
| Google Cloud (`python deploy.py`) | Not estimated yet. The local mode never calls Gemini, so we have no measured token counts per action plan, and we couldn't read the current prices from the [Cloud Run](https://cloud.google.com/run/pricing) and [Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing) pricing pages for this update. Note that `fusion-engine` is deployed with one instance always running. |

## How it works

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

## Run it the way the book does

The book doesn't print this repository; these are the original Google Cloud steps, unchanged. They deploy paid services to your Google Cloud project. The three services that read Cloud Storage take the bucket name from `GCS_BUCKET` (default `your-project-id-resolve-binaries`).

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