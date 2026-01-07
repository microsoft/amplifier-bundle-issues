"""
Issue management tool module for Amplifier.

Provides issue management with embedded IssueManager instance.
Pure-module implementation requiring zero kernel changes.
"""

import logging
from pathlib import Path
from typing import Any

from amplifier_core import ModuleCoordinator

from .tool import IssueTool

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the issue management tool with embedded state.

    Args:
        coordinator: Module coordinator
        config: Configuration dict with optional keys:
            - data_dir: Directory for JSONL storage (default: .amplifier/issues)
            - auto_create_dir: Auto-create directory if missing (default: True)
            - actor: Default actor for events (default: assistant)

    Returns:
        None - No cleanup needed for this module
    """
    config = config or {}
    data_dir = Path(config.get("data_dir", ".amplifier/issues"))
    actor = config.get("actor", "assistant")

    # Auto-create directory if configured
    if config.get("auto_create_dir", True):
        data_dir.mkdir(parents=True, exist_ok=True)

    # Create tool with embedded IssueManager
    tool = IssueTool(coordinator, data_dir=data_dir, actor=actor)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info(f"Mounted issue management tool with data_dir={data_dir}")
    return
