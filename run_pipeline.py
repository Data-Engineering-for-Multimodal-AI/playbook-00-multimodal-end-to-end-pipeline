#!/usr/bin/env python3
"""
Run the pipeline locally (no cloud account): python run_pipeline.py [--batches 1000 61000] [--llm]
The Google Cloud version is in cloud/ (see the README).
"""
import sys

from resolve.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
