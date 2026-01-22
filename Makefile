.PHONY: install install-dev lint type-check test check clean build publish chat chat-log chat-resume sessions

# Install the package
install:
	uv pip install -e .

# Install with dev dependencies
install-dev:
	uv pip install -e ".[dev]"

# Run linting
lint:
	uv run ruff check src/
	uv run ruff format --check src/

# Run type checking
type-check:
	uv run mypy src/ --ignore-missing-imports

# Run tests
test:
	uv run pytest tests/ -v

# Run all checks (lint + type-check + test)
check: lint type-check test

# Format code
format:
	uv run ruff format src/
	uv run ruff check --fix src/

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Build package
build: clean
	uv build

# Show current config
config:
	uv run standup config --show

# Generate standup
standup:
	uv run standup generate

# Interactive chat
chat:
	uv run standup chat

# Interactive chat with logging to log.txt
chat-log:
	script log.txt uv run standup chat

# Resume last chat session
chat-resume:
	uv run standup chat --resume

# List chat sessions
sessions:
	uv run standup sessions --list
