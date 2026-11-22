.PHONY: setup run run-real data smoke clean

# Uniform targets for The Playbooks. The Google Cloud commands in the README
# (pip install -r requirements.txt, python deploy.py --project-id YOUR_PROJECT_ID --region us-central1,
# python run_pipeline.py) still work as documented. Nothing here calls Google Cloud.

FIXTURE := output/fixture

# Install the locked dependencies of the local pipeline into .venv.
setup:
	uv sync --frozen

# The local pipeline on a small synthetic fixture: no account, no download.
# Prints the six stages and writes output/fixture/out/resolve.db and report.json.
run: setup
	uv run --frozen python tests/fixture.py $(FIXTURE)/data > /dev/null
	@echo "Synthetic fixture in $(FIXTURE)/data (a stand-in for the Future Factories data)"
	RESOLVE_DATA=$(FIXTURE)/data RESOLVE_OUTPUT=$(FIXTURE)/out uv run --frozen python run_local.py

# Download a slice of the Future Factories data from Kaggle into data/ (needs a Kaggle API token:
# ~/.kaggle/kaggle.json, or KAGGLE_USERNAME and KAGGLE_KEY).
data: setup
	uv run --frozen python download_data.py

# The local pipeline on the real data in data/. Downloads it first if it is missing.
run-real: setup
	@if [ ! -f data/SOURCE.json ]; then $(MAKE) data; fi
	uv run --frozen python run_local.py

# Tests on the synthetic fixture (CPU, no network calls after install).
smoke: setup
	uv run --frozen pytest -q tests

# Remove generated files: pipeline output, test caches and the deploy log.
# The downloaded data in data/ is kept.
clean:
	rm -rf output .pytest_cache deployment.log
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +
