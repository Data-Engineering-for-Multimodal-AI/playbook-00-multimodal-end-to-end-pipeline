# Changelog

## v1.1.0 (2026-11-26)

Not printed in the book. Nothing the book shows has changed.

Several fixes come from the `update-2026` branch (closed PR #1). They were copied into this
change from `main`. That branch's move of the Google Cloud files to `cloud/` was not copied, so
every existing path stays where it was.

### Added
- `make query` (`scripts/query.py`): read-only SQL against the SQLite store.
- `make check-data DIR=...` and `make load DIR=...` (`scripts/own_data.py`): check a folder of your
  own data in the layout of `data/`, and run the local pipeline on it (`output/own/`). Tests in
  `tests/test_own_data.py`; `make smoke` still runs only `tests/test_pipeline.py`.
- Three measured experiments on synthetic data: `make try-fusion-timeout`, `make try-rate-limit`,
  `make try-bad-values` (`experiments/`).
- README: Run it, time tiers, Try this, Use your own data, What you end up with, Before production,
  What it costs.
- CI: the Run it steps with checks on their output, the own-data checks, the three experiments, and
  the time to first output in the devcontainer job.
- A local mode that needs no cloud account: `run_local.py` and the `resolve/` package (ingest
  with schema validation, historical baselines, fusion, rule-based planning, a safety check,
  SQLite). New schemas for it: `schemas/ff_reading_v1.json` and `schemas/ff_safety_policy_v1.yaml`.
  From `update-2026`.
- `download_data.py`: downloads a slice of the Future Factories data from Kaggle (needs a Kaggle
  API token). From `update-2026`.
- Tests on a synthetic fixture (`tests/`). From `update-2026`.
- `pyproject.toml` and `uv.lock` (Python 3.12+), and `requirements-local.txt` for the local mode.
  `requirements.txt` is unchanged.
- `make setup`, `make run`, `make run-real`, `make data`, `make smoke` and `make clean`.
  `make run` runs the local mode on the synthetic fixture. `make run-real` runs it on the
  Kaggle data.
- `.devcontainer/` so the repo opens in GitHub Codespaces with dependencies installed.
- CI (`.github/workflows/smoke.yml`) on Python 3.12 and 3.13, weekly as well: tests, `make run`,
  the `pip install -r requirements.txt` path with `deploy.py --help` and `run_pipeline.py --help`,
  and a job that builds the devcontainer and runs `make run` inside it. CI makes no Google Cloud
  or Kaggle calls.
- `DATA_SOURCES.md`: the datasets and models this playbook uses, with their licenses and citations.
- `make run` writes `.playbook-done` when it passes (ignored by git). `make card` in the
  organization's `.github` repository reads these files and draws a completion card.

### Fixed
- `services/data_ingester`, `services/historical_processor` and `services/ai_planner` hard-coded
  the bucket name. They now read `GCS_BUCKET`, with the old name as the default. The AI planner's
  health check uses the same setting. From `update-2026`.
- Two links in `TUTORIAL.md` returned 404. They now point to the current Cloud Run and Pub/Sub pages.

### Changed
- README: the local steps are now "Run it"; "Overview" is now "How it works"; the Google Cloud
  "Quick Start" is now "Run it the way the book does", with the same content.
- README opening: a title that says what you'll do, three sentences on why, the example and what you'll do, then the data engineering problem and what you'll work with.
- README: a header image (light and dark), badges for CI, Python, license and Codespaces, a diagram at
  the top of "How it works", and a footer that links the book, all playbooks, and the previous and
  next playbook.
- README: a Troubleshooting section with three common problems and their fixes.
- The AI planner (`services/ai_planner/main.py`) uses the `google-genai` SDK instead of the deprecated
  `vertexai.generative_models`. `requirements.txt` lists `google-genai` in place of
  `google-cloud-aiplatform` and `vertexai`.
- README: the clone URL and folder name, and the Python versions (3.12 or later locally; the Cloud Run
  images use `python:3.11-slim`).

