# Testing tool-issue Module

This directory contains tests for the GitHub sync and permission verification features.

## Running Tests

### Option 1: Using uv (Recommended)

```bash
cd modules/tool-issue

# Install test dependencies
uv pip install -e ".[test]"

# Run tests
uv run pytest tests/ -v
```

### Option 2: Using a Virtual Environment

```bash
cd modules/tool-issue

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install pytest pytest-asyncio
pip install -e .

# Run tests
pytest tests/ -v
```

### Option 3: System-wide (if permitted)

```bash
# Install pytest-asyncio
pip install --user pytest-asyncio

# Run tests
cd modules/tool-issue
pytest tests/ -v
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Test configuration and mocks
├── test_github_sync.py      # 15 tests for sync operations
└── test_github_permissions.py  # 17 tests for permission checks
```

## What's Tested

### GitHub Sync (`test_github_sync.py`)
- ✅ Skipping already-synced issues
- ✅ Skipping closed issues by default
- ✅ Including closed issues when requested
- ✅ Updating local metadata after sync
- ✅ Error handling and recovery
- ✅ GitHub URL generation
- ✅ Label mapping (status, area, priority)
- ✅ Issue body formatting
- ✅ Missing field handling

### Permission Verification (`test_github_permissions.py`)
- ✅ gh CLI not installed
- ✅ gh CLI installation check fails
- ✅ Not authenticated with GitHub
- ✅ Repository not found (404)
- ✅ Access forbidden (403)
- ✅ Write permission granted
- ✅ Admin permission granted
- ✅ Maintain permission granted
- ✅ Read-only access (insufficient)
- ✅ Permission parsing fallback
- ✅ Timeout handling
- ✅ Integration with sync operation
- ✅ Command construction validation

## Test Coverage

**32 total tests** covering:
- Happy path scenarios
- Error conditions
- Edge cases
- Permission variations
- Timeout handling

## CI/CD Integration

These tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install pytest pytest-asyncio
    cd modules/tool-issue
    pytest tests/ -v --tb=short
```

## Troubleshooting

### "async def functions are not natively supported"
**Solution**: Install `pytest-asyncio`:
```bash
pip install pytest-asyncio
```

### "No module named 'amplifier_core'"
**Solution**: The tests use mocks (see `conftest.py`). This is expected and handled automatically.

### Tests are skipped
**Solution**: Make sure `pytest-asyncio` is installed. Check with:
```bash
python3 -c "import pytest_asyncio; print('OK')"
```

### Permission denied when installing
**Solution**: Use `--user` flag or a virtual environment:
```bash
pip install --user pytest-asyncio
```

## Writing New Tests

When adding new tests:

1. **Use async test pattern**:
   ```python
   @pytest.mark.asyncio
   async def test_my_feature(issue_tool):
       result = await issue_tool.my_method()
       assert result["success"] is True
   ```

2. **Mock external dependencies**:
   ```python
   with patch("subprocess.run") as mock_run:
       mock_run.return_value = MagicMock(returncode=0)
       # Your test code
   ```

3. **Test both success and failure paths**

4. **Include descriptive docstrings**

## Running Specific Tests

```bash
# Run single test file
pytest tests/test_github_sync.py -v

# Run single test class
pytest tests/test_github_permissions.py::TestVerifyGitHubPermissions -v

# Run single test
pytest tests/test_github_sync.py::TestSyncToGitHub::test_sync_skips_already_synced_issues -v

# Run with coverage
pytest tests/ --cov=amplifier_module_tool_issue --cov-report=html
```
