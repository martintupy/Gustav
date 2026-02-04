.PHONY: install dev lint format fix check type clean

install:
	uv sync

dev:
	uv sync --extra dev

lint:
	uv run -- ruff check gustav

format:
	uv run -- ruff format gustav

fix:
	uv run -- ruff check --fix gustav
	uv run -- ruff format gustav

check:
	uv run -- ruff check gustav
	uv run -- ruff format --check gustav

type:
	uv run -- mypy gustav

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
