.PHONY: install dev lint format fix check type clean

install:
	uv sync

dev:
	uv sync --extra dev

lint:
	uv run -- ruff check ghai

format:
	uv run -- ruff format ghai

fix:
	uv run -- ruff check --fix ghai
	uv run -- ruff format ghai

check:
	uv run -- ruff check ghai
	uv run -- ruff format --check ghai

type:
	uv run -- mypy ghai

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
