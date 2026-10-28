# End-to-End Multimodal Pipeline for a Robotic Assembly Cell

A companion project for *Data Engineering for Multimodal AI* (O'Reilly, 2026). It isn't printed in the book; it builds the book's end-to-end pattern (ingest, validate, fuse, plan, check, act, store) on real factory data.
Book: https://oreil.ly/data-engineering-multimodal

> The version before the 2026 update is tagged `first-edition`; see [Differences from the first edition](#differences-from-the-first-edition).

## What you'll build

A pipeline that watches the Future Factories assembly cell at the University of South Carolina (four robots and a conveyor that build and take apart a small rocket), using its sensor readings and the two cameras over the cell, and proposes safe actions.

It runs on a laptop by default. The same stages also exist as a Google Cloud version (Cloud Run services, Pub/Sub, BigQuery, Gemini) in [`cloud/`](cloud/), kept as the optional path.

| Stage | Local (default) | Google Cloud (`cloud/`) |
|---|---|---|
| 1. Ingest | Read the multimodal batches; validate every reading against `schemas/ff_reading_v1.json`; publish telemetry and image messages to in-process topics | Data ingester (Cloud Run) → Pub/Sub |
| 2. Baselines | Per-sensor statistics over the 30-hour analog recording, implausible values left out | Historical processor → BigQuery |
| 3. Fusion | Each reading joined with both camera images | Fusion engine |
| 4. Planning | Deviations from the baselines; the rules in `schemas/safety_policy.yaml`; optionally an OpenAI-compatible model (for example a local Ollama server) with the images | AI planner with Gemini |
| 5. Safety | Each action checked against `schemas/tool_registry.json` and rate-limited | A Safety API (called, not included) |
| 6. Store | SQLite (`output/resolve.db`) and `output/report.json` | BigQuery |

What it shows, on real data (below):

- **A policy has to fit the data.** The drives run at 85-93 °C. The first edition's rule, "emergency stop above 85 °C", would have stopped the line during 94% of the 30-hour recording. The policy now acts on what matters in this data: a safety door opened while the conveyor runs.
- **Real sensors fail.** Three drive-temperature sensors sometimes report about 3 × 10³⁸ °C (13,256 such values in the recording). Validation keeps them out of the baselines and rejects such readings.
- **A sustained condition is one alert a minute, not one per reading.** Door 2 was open for 4 minutes 22 seconds (510 readings). The safety check let one emergency stop through per minute and blocked the 505 repeats.

## Quick start

You need Python 3.12 or newer and a Kaggle account for the data (an API token in `~/.kaggle/kaggle.json`, or `KAGGLE_USERNAME` and `KAGGLE_KEY`, see `.env.example`). No cloud account is needed.

```bash
git clone https://github.com/Data-Engineering-for-Multimodal-AI/playbook-00-multimodal-end-to-end-pipeline.git
cd playbook-00-multimodal-end-to-end-pipeline

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

python download_data.py     # about 840 MB: the analog CSVs, three multimodal batches, 122 camera images
python run_pipeline.py      # a few seconds
```

With [uv](https://docs.astral.sh/uv/): `uv sync`, then prefix commands with `uv run`; `make data`, `make run`, `make smoke`. Without a Kaggle account, `make fixture-run` runs the pipeline on a small synthetic stand-in (the one CI uses).

What `download_data.py` gets: the analog dataset (every sensor at 10 Hz for 30 hours, 61 MB zipped) for the baselines, and three batches of the multimodal dataset, about 1,000 synchronized readings each, with every 50th reading's two camera images (1.7 MB each; the whole multimodal dataset is 560 GB). The batches: 1000 (the cold start, 11:50 local time on 11 December), 61000 (mid-run, 20:17) and 157000 (10:00 the next morning, when safety door 2 was opened while the conveyor ran). `--batches` and `--image-every` choose others.

The optional LLM step reviews each reading that has images: `LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_MODEL=<a vision model> python run_pipeline.py --llm`. Its actions go through the same safety check. It was not run for this update; all output below is from the rules.

### The Google Cloud version (optional)

[`cloud/`](cloud/) holds the first edition's Cloud Run version, updated but not run for this update (it needs a billed Google Cloud project):

```bash
cd cloud
pip install -r requirements.txt
python deploy.py --project-id YOUR_PROJECT_ID --region us-central1
python run_pipeline_cloud.py
```

See [cloud/TUTORIAL.md](cloud/TUTORIAL.md) and [cloud/docs/](cloud/docs/). It reads the data from your own Cloud Storage bucket (`GCS_BUCKET`, default `<project>-resolve-binaries`; `cloud/cloudbuild-download.yaml` copies it from Kaggle). Cloud Run, Pub/Sub, BigQuery, Cloud Storage and Gemini are billed while they run; delete the services and the dataset when you're done.

## Tested on

| Date | OS | Python | What |
|---|---|---|---|
| 2026-10-27 | macOS 26.5.1 (Apple M3) | 3.13.16 | `make smoke` (4 tests); `python download_data.py` (the default slice) and `python run_pipeline.py` (output below) |
| 2026-10-27 | macOS 26.5.1 (Apple M3) | 3.12.15 | Fresh clone: `pip install -r requirements.txt` (15 s), the tests, the pipeline on the synthetic fixture |
| 2026-10-27 | Ubuntu (GitHub Actions) | 3.12, 3.13 | The tests; `pip install -r requirements.txt` and the pipeline on the fixture; `cloud/requirements.txt` installs and the cloud code compiles |

Versions are pinned in `uv.lock`, `requirements.txt` and `cloud/requirements.txt` (pandas 3.1, jsonschema, PyYAML; for the cloud version google-genai 2.33 and the Google Cloud clients).

## Differences from the first edition

| First edition | Now | Why |
|---|---|---|
| Google Cloud only (Cloud Run, Pub/Sub, BigQuery, Vertex AI, Terraform) | Local by default; the cloud version in `cloud/` | Runs on a laptop without a billed account |
| Data in a private Cloud Storage bucket | `download_data.py` from Kaggle, where the dataset's authors publish it | Readers can get it |
| Reading schema and safety policy for temperature_c, vibration_rms, rpm, torque_nm and audio commands | `schemas/ff_reading_v1.json` and a policy for the data's real signals | None of those fields is in the data |
| Emergency stop above 85 °C | Rules for doors, overheating (above 100 °C), unusual drive temperature (3 standard deviations) and gripper overload | The drives run at 85-93 °C; the old rule would fire 94% of the time |
| Fusion published a record when the first camera image arrived | Waits for both images (or 5 s) | The second camera's image was dropped |
| Drive temperatures compared with robot baselines | With the conveyor's | They are conveyor drives |
| Actions sent to a Safety API that isn't in the repository | `resolve/safety.py`: tool registry, parameters, rate limit | |
| Vertex AI SDK generative module (`vertexai.generative_models`) | google-genai, model set by `GEMINI_MODEL` | Google removed the module in June 2026 |
| Audio, thermal and video schemas | Removed | The data has no such modalities |
| README "Sample Output" with an action called `reduce_conveyor_speed` and "vibration visible" | Output from real runs, below | The example wasn't from a run; the data has no vibration sensor |
| Terraform state committed (with personal details); `.DS_Store` | Removed from the files and the history; `.gitignore` excludes them | Personal data |
| `git clone <repository-url>` / `cd resolve-agent`, Python 3.11+, unpinned | This repository, Python 3.12+, pinned | |

Full list: [CHANGELOG.md](CHANGELOG.md).

## Data and licenses

| Data | Source | License |
|---|---|---|
| Analog dataset (`data/analog/`, downloaded): 974,836 samples of every sensor at 10 Hz, 2023-12-11 13:04 to 2023-12-12 18:07 UTC | R. Harik, F. El Kalach, J. Samaha, D. Clark, D. Sander, P. Samaha, L. Burns, I. Yousif, V. Gadow, T. Tarekegne, N. Saha, "Analog and Multi-modal Manufacturing Datasets Acquired on the Future Factories Platform", [arXiv:2401.15544](https://arxiv.org/abs/2401.15544). [Kaggle](https://www.kaggle.com/datasets/ramyharik/ff-2023-12-12-analog-dataset) | CC BY-SA 4.0 |
| Multimodal batches and camera images (`data/multimodal/`, downloaded) | The same authors; Kaggle, ff-2023-12-12-multi-modal-dataset-16 to -66 | CC BY-SA 4.0 |
| `tests/fixture.py`'s synthetic stand-in | Made up for the tests | MIT, like the code |

Nothing from the dataset is committed. The multimodal batches' timestamps are local time (US Eastern, UTC−5); the analog dataset's are UTC. Matching batch 157000's open door with the analog recording's (15:04 UTC) confirms the offset.

## Expected output

`python run_pipeline.py` on 2026-10-27, macOS 26.5.1 (Apple M3), Python 3.13.16, after `python download_data.py`. This is the output of this version.

```
Batches: data_1000, data_61000, data_157000
1. Ingest:    3001 readings, 0 rejected by the schema
              published: telemetry 3001, images 6002
2. Baselines: 36 sensors over 974,836 analog samples; hottest drive 88.9 +- 2.9 C (99th percentile 93.1)
              implausible values left out: Q_VFD2_Temperature 4,771, Q_VFD3_Temperature 4,224, Q_VFD4_Temperature 4,261
3. Fusion:    3001 records, 3001 with both camera images (122 images downloaded)
4. Planning:  hottest drive 73.2-93.7 C; readings over 3 std from the usual: max_vfd_temperature below 956, Q_VFD1_Temperature below 944, I_R03_Gripper_Load above 141, I_R01_Gripper_Load below 12, I_R02_Gripper_Load below 5, I_R02_Gripper_Load above 4, I_R01_Gripper_Load above 3
              actions proposed: {'door2_open_while_moving': 510}; LLM: not configured
5. Safety:    approved {'emergency_stop': 5}; blocked {'same action within 60 s': 505}
6. Store:     output/resolve.db; report in output/report.json (4.0 s in all)

The first edition's rule (emergency_stop when temperature_c > 85) would fire on 67% of these readings and 94% of the analog recording.
```

The approved actions, from the local store:

```
sqlite3 output/resolve.db "SELECT ts, action, rule, status FROM action_plans WHERE status = 'approved'"
2023-12-12 10:04:26.539215|emergency_stop|door2_open_while_moving|approved
2023-12-12 10:05:26.861180|emergency_stop|door2_open_while_moving|approved
2023-12-12 10:06:26.932108|emergency_stop|door2_open_while_moving|approved
2023-12-12 10:07:27.152478|emergency_stop|door2_open_while_moving|approved
2023-12-12 10:08:27.223935|emergency_stop|door2_open_while_moving|approved
```

Readings "below" the usual drive temperature are batch 1000's cold start (73 °C). R03's gripper load is above 3 standard deviations whenever it holds a piece; the policy acts only above 6. The cameras don't show the open door or anyone in the cell, so the safety door sensor is the evidence.

## License

MIT; see [LICENSE](LICENSE). The Future Factories data is CC BY-SA 4.0 and is downloaded, not included.
