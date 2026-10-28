# Changelog

## 2026.10 (2026-10-27)

The version before this update is tagged `first-edition`. Personal details (committed Terraform state
with an e-mail address and a project ID, and a `.DS_Store`) were removed from the repository's history
before that tag was made.

### Added
- A local version (`run_pipeline.py`, `resolve/`): ingest with schema validation, historical baselines,
  fusion, rule-based planning (an OpenAI-compatible model optionally), a safety check, SQLite and a
  report. No cloud account needed.
- `download_data.py`: a laptop-sized slice of the Future Factories data from Kaggle.
- Tests on a synthetic fixture, a Makefile, CI on Python 3.12 and 3.13.

### Changed
- The Google Cloud version moved to `cloud/`: google-genai instead of the Vertex AI SDK's removed
  generative module, fusion waits for both camera images, drive temperatures compared with the
  conveyor's baselines, the bucket comes from the project.
- `schemas/ff_reading_v1.json` and `schemas/safety_policy.yaml` describe the data's real signals; the
  first edition's policy would have stopped the line during 94% of the recording.
- Pinned dependencies (`uv.lock`, `requirements.txt`, `cloud/requirements.txt`), Python 3.12+.
- README: measured results; the invented sample output is gone.

### Removed
- Audio, thermal and video schemas (the data has no such modalities); Terraform state; `.DS_Store`.
