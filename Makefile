.PHONY: setup run query check-data load try-fusion-timeout try-rate-limit try-bad-values run-real data smoke clean

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
	@echo "playbook-00-multimodal-end-to-end-pipeline" > .playbook-done

# After make run: query the SQLite store yourself (default: the action plans).
#   make query SQL="SELECT * FROM rejected_readings"
query:
	uv run --frozen python scripts/query.py $(if $(SQL),"$(SQL)",) $(if $(DB),--db "$(DB)",)

# Your own data, in the layout of data/ (see README, "Use your own data").
# check-data checks every file and writes nothing; load runs the local pipeline on it (output/own/).
#   make check-data DIR=my_cell
#   make load DIR=my_cell
check-data: setup
	@test -n "$(DIR)" || { echo "Usage: make check-data DIR=path/to/folder"; exit 2; }
	uv run --frozen python scripts/own_data.py --dir "$(DIR)" --check-only

load: setup
	@test -n "$(DIR)" || { echo "Usage: make load DIR=path/to/folder"; exit 2; }
	uv run --frozen python scripts/own_data.py --dir "$(DIR)"

# Try this: three measured experiments on synthetic data (see README, "Try this"). No cloud.
try-fusion-timeout: setup
	uv run --frozen python experiments/fusion_timeout.py

try-rate-limit: setup
	uv run --frozen python experiments/rate_limit.py

try-bad-values: setup
	uv run --frozen python experiments/bad_values.py

# Download a slice of the Future Factories data from Kaggle into data/ (needs a Kaggle API token:
# ~/.kaggle/kaggle.json, or KAGGLE_USERNAME and KAGGLE_KEY).
data: setup
	uv run --frozen python download_data.py

# The local pipeline on the real data in data/. Downloads it first if it is missing.
run-real: setup
	@if [ ! -f data/SOURCE.json ]; then $(MAKE) data; fi
	uv run --frozen python run_local.py

# Tests on the synthetic fixture (CPU, no network calls after install).
# The own-data tests: uv run pytest tests/test_own_data.py
smoke: setup
	uv run --frozen pytest -q tests/test_pipeline.py

# Remove generated files: pipeline output (output/, including output/own/), test caches and the deploy log.
# The downloaded data in data/ is kept.
clean:
	rm -rf output .pytest_cache deployment.log
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +
