.PHONY: check format lint test clean

check: format lint

format:
	uv run ruff format amplifier_module_tool_issue/

lint:
	uv run ruff check amplifier_module_tool_issue/ --fix

test:
	uv run pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
