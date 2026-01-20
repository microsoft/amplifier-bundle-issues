"""Test configuration and fixtures for tool-issue tests.

This module sets up mocks for amplifier dependencies that aren't available in the test environment.
"""

import sys
from typing import Any
from unittest.mock import MagicMock


# Create a simple ToolResult class for testing
class ToolResult:
    """Mock ToolResult for testing."""

    def __init__(self, success: bool, output: Any = None, error: Any = None):
        self.success = success
        self.output = output
        self.error = error


# Create mock modules
mock_amplifier_core = MagicMock()
mock_amplifier_core.ToolResult = ToolResult

# Mock amplifier-core modules before they're imported by the tool
sys.modules["amplifier_core"] = mock_amplifier_core
sys.modules["amplifier_module_issue_manager"] = MagicMock()

# Import after mocking dependencies
from amplifier_module_tool_issue.tool import IssueTool  # noqa: E402


# Make IssueTool available for tests
__all__ = ["IssueTool", "ToolResult"]
