.PHONY: smoke data run fixture-run
smoke:        ## tests on a small synthetic fixture
	uv run pytest -q tests
data:         ## the Future Factories slice from Kaggle (needs a Kaggle API token)
	uv run python download_data.py
run:          ## the local pipeline on the downloaded data
	uv run python run_pipeline.py
fixture-run:  ## the local pipeline on the synthetic fixture (no download)
	uv run python tests/fixture.py /tmp/resolve-fixture && RESOLVE_DATA=/tmp/resolve-fixture RESOLVE_OUTPUT=/tmp/resolve-fixture-out uv run python run_pipeline.py
