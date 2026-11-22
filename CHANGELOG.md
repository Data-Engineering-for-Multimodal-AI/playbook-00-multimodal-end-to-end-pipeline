# Changelog

## Unreleased (v1.1.0)

Not printed in the book. Nothing the book shows has changed.

Several fixes come from the `update-2026` branch (closed PR #1). They were copied into this
change from `main`. That branch's move of the Google Cloud files to `cloud/` was not copied, so
every existing path stays where it was.

### Added
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

### Fixed
- `services/data_ingester`, `services/historical_processor` and `services/ai_planner` hard-coded
  the bucket name. They now read `GCS_BUCKET`, with the old name as the default. The AI planner's
  health check uses the same setting. From `update-2026`.
- Two links in `TUTORIAL.md` returned 404. They now point to the current Cloud Run and Pub/Sub pages.

### Changed
- README opening: a title that says what you'll do, three sentences on why, the example and what you'll do, then the data engineering problem and what you'll work with.

