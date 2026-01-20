"""Test configuration and fixtures for tool-issue tests.

This module sets up mocks for amplifier dependencies that aren't available in the test environment.
"""

import sys
from unittest.mock import MagicMock

# Mock amplifier-core modules before they're imported by the tool
sys.modules["amplifier_core"] = MagicMock()
sys.modules["amplifier_module_issue_manager"] = MagicMock()

# Import after mocking dependencies
from amplifier_module_tool_issue.tool import IssueTool  # noqa: E402


# Make IssueTool available for tests
__all__ = ["IssueTool"]
