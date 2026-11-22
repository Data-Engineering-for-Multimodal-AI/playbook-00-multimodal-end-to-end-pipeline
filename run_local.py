#!/usr/bin/env python3
"""
Run the pipeline locally, with no cloud account: python run_local.py [--batches 1000 61000] [--llm]

It reads the Future Factories data from data/ (python download_data.py fetches it from Kaggle) or from
the folder in RESOLVE_DATA, and writes output/resolve.db and output/report.json (or RESOLVE_OUTPUT).
The Google Cloud version is unchanged: python deploy.py, then python run_pipeline.py.
"""
import sys

from resolve.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
