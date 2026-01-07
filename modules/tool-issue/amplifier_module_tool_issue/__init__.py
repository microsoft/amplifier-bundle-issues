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


def get_project_slug(project_path: Path) -> str:
    """Convert project path to slug for issue storage directory.

    Args:
        project_path: Path to the project directory

    Returns:
        A slug string suitable for use in directory names
    """
    # Convert absolute path to slug
    abs_path = project_path.resolve()
    slug = str(abs_path).replace("/", "-").replace("\\", "-")

    # Remove leading dash
    if slug.startswith("-"):
        slug = slug[1:]

    return slug


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the issue management tool with embedded state.

    Args:
        coordinator: Module coordinator
        config: Configuration dict with optional keys:
            - data_dir: Base directory for issue storage (default: ~/.amplifier/projects)
                       Supports ~ expansion and {project} placeholder for project slug.
                       Final path will be: data_dir/{project_slug}/issues
            - auto_create_dir: Auto-create directory if missing (default: True)
            - actor: Default actor for events (default: assistant)

    Returns:
        None - No cleanup needed for this module
    """
    config = config or {}
    actor = config.get("actor", "assistant")

    # Get base directory with ~ expansion
    base_dir = Path(config.get("data_dir", "~/.amplifier/projects")).expanduser()

    # Get project slug from current working directory
    project_path = Path.cwd()
    project_slug = get_project_slug(project_path)

    # Construct final data directory: base_dir / project_slug / issues
    data_dir = base_dir / project_slug / "issues"

    # Auto-create directory if configured
    if config.get("auto_create_dir", True):
        data_dir.mkdir(parents=True, exist_ok=True)

    # Create tool with embedded IssueManager
    tool = IssueTool(coordinator, data_dir=data_dir, actor=actor)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info(f"Mounted issue management tool with data_dir={data_dir}")
    return
