"""Issue session-end hook module.

Automatically marks issues when an Amplifier session ends, providing
continuity by recording session boundaries on in-progress issues.
"""

import logging
from typing import Any

from amplifier_core import HookResult
from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the issue session-end hook.

    Args:
        coordinator: Module coordinator
        config: Optional configuration
            - priority: Hook priority (default: 90, runs late to see full session)
            - enabled: Whether hook is active (default: True)

    Returns:
        Optional cleanup function
    """
    config = config or {}
    hook = IssueSessionEndHook(coordinator, config)
    hook.register(coordinator.hooks)
    logger.info("Mounted hook-issue-session-end")
    return


class IssueSessionEndHook:
    """Hook that marks issues when an Amplifier session ends.

    When a session ends with issues still in_progress, this hook emits
    session_ended events to provide continuity. This enables users to
    see which sessions were interrupted and resume context later.
    """

    def __init__(self, coordinator: ModuleCoordinator, config: dict[str, Any]):
        """Initialize issue session-end hook.

        Args:
            coordinator: Module coordinator (for accessing issue state)
            config: Configuration dict
                - priority: Hook priority (default: 90)
                - enabled: Whether hook is active (default: True)
        """
        self.coordinator = coordinator
        self.priority = config.get("priority", 90)
        self.enabled = config.get("enabled", True)

    def register(self, hooks):
        """Register hook on session:end event."""
        if self.enabled:
            hooks.register(
                "session:end",
                self.on_session_end,
                priority=self.priority,
                name="hook-issue-session-end",
            )

    async def on_session_end(self, event: str, data: dict[str, Any]) -> HookResult:
        """Mark in-progress issues when session ends.

        Args:
            event: Event name ("session:end")
            data: Event data with session_id

        Returns:
            HookResult - always continue (this is observational)
        """
        if not self.enabled:
            return HookResult(action="continue")

        session_id = data.get("session_id")
        if not session_id:
            logger.debug("hook-issue-session-end: No session_id in event data")
            return HookResult(action="continue")

        # Try to find the issue_manager tool
        tools = getattr(self.coordinator, "tools", {})
        issue_manager_tool = None

        for tool_name, tool in tools.items():
            if "issue" in tool_name.lower():
                issue_manager_tool = tool
                break

        if not issue_manager_tool:
            logger.debug("hook-issue-session-end: issue_manager tool not available")
            return HookResult(action="continue")

        # Get the embedded IssueManager
        issue_manager = getattr(issue_manager_tool, "issue_manager", None)
        if not issue_manager:
            logger.debug("hook-issue-session-end: No embedded IssueManager found")
            return HookResult(action="continue")

        try:
            # Find in-progress issues
            in_progress_issues = issue_manager.list_issues(status="in_progress")

            # For each in-progress issue, check if this session touched it
            # and emit session_ended event
            marked_count = 0
            for issue in in_progress_issues:
                # Get events for this issue
                events = issue_manager.get_issue_events(issue.id)

                # Check if this session touched this issue
                session_touched = any(
                    e.session_id == session_id for e in events
                )

                if session_touched:
                    issue_manager.emit_session_ended(issue.id)
                    marked_count += 1
                    logger.debug(
                        f"hook-issue-session-end: Marked session end on issue {issue.id}"
                    )

            if marked_count > 0:
                logger.info(
                    f"hook-issue-session-end: Marked {marked_count} issues with session end"
                )

        except Exception as e:
            logger.error(f"hook-issue-session-end: Error marking issues: {e}")

        return HookResult(action="continue")
