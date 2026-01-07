"""Issue manager module for Amplifier.

Provides issue management with dependencies, priority-based scheduling,
and event tracking.
"""

from .manager import IssueManager
from .models import Dependency
from .models import Issue
from .models import IssueEvent

__all__ = ["IssueManager", "Issue", "Dependency", "IssueEvent", "mount"]


async def mount(coordinator, config: dict | None = None):
    """Mount issue manager module.

    Args:
        coordinator: Module coordinator
        config: Configuration dict with optional keys:
            - data_dir: Directory for JSONL storage (default: .amplifier/issues)
            - auto_create_dir: Auto-create directory if missing (default: True)
            - actor: Default actor for events (default: system)

    Returns:
        None (issue manager registered with coordinator)
    """
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)

    config = config or {}
    data_dir = Path(config.get("data_dir", ".amplifier/issues"))
    actor = config.get("actor", "system")

    logger.info(f"DEBUG mount(): Creating IssueManager with data_dir={data_dir}")

    if config.get("auto_create_dir", True):
        data_dir.mkdir(parents=True, exist_ok=True)

    issue_manager = IssueManager(data_dir, actor=actor)
    logger.info(f"DEBUG mount(): IssueManager instance created: {issue_manager}")
    logger.info("DEBUG mount(): About to call coordinator.mount('issue-manager', issue_manager)")
    await coordinator.mount("issue-manager", issue_manager)
    logger.info("DEBUG mount(): After coordinator.mount, checking result...")
    logger.info(f"DEBUG mount(): coordinator.get('issue-manager') = {coordinator.get('issue-manager')}")

    return
