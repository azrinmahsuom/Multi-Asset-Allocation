.PHONY: all fetch refresh verify test lint

all:          ## Rebuild everything from raw data
	uv run python -m analysis.pipeline all

fetch:        ## Download any missing raw files
	uv run python -m analysis.pipeline fetch

refresh:      ## Re-download every source and accept updates into data/MANIFEST.yaml
	uv run python -m analysis.pipeline refresh

verify:       ## Check raw files against the hashes in data/MANIFEST.yaml
	uv run python -m analysis.pipeline verify

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
