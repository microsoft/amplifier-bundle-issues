"""Issue session-start hook module.

Surfaces existing issues at session start and provides gentle reminders
during the session if issues exist but haven't been checked recently.
Follows the same pattern as the hooks-todo-reminder module.
"""

__amplifier_module_type__ = "hook"

import logging
from collections import deque
from typing import Any

from amplifier_core import HookResult
from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the issue session-start hook.

    Args:
        coordinator: Module coordinator
        config: Optional configuration
            - priority: Hook priority (default: 5, runs early)
            - nudge_interval: How many provider requests between nudges (default: 10)
            - inject_role: Role for context injection (default: "user")

    Returns:
        Optional cleanup function
    """
    config = config or {}
    hook = IssueSessionStartHook(coordinator, config)
    hook.register(coordinator.hooks)
    logger.info("Mounted hook-issue-session-start")
    return None


class IssueSessionStartHook:
    """Hook that surfaces existing issues at session start.

    Provides two behaviors:
    1. On session:start - shows summary of open issues in this project
    2. On provider:request - gentle nudge if issues exist but tool not used recently
    """

    def __init__(self, coordinator: ModuleCoordinator, config: dict[str, Any]):
        """Initialize issue session-start hook.

        Args:
            coordinator: Module coordinator
            config: Configuration dict
                - priority: Hook priority (default: 5)
                - nudge_interval: Requests between nudges (default: 10)
                - inject_role: Context injection role (default: "user")
        """
        self.coordinator = coordinator
        self.priority = config.get("priority", 5)
        self.nudge_interval = config.get("nudge_interval", 10)
        self.inject_role = config.get("inject_role", "user")

        # Track state
        self.session_start_handled = False
        self.request_count = 0
        self.recent_tools: deque[str] = deque(maxlen=5)

    def register(self, hooks):
        """Register hooks on session:start, provider:request, and tool:post."""
        hooks.register(
            "session:start",
            self.on_session_start,
            priority=self.priority,
            name="hook-issue-session-start",
        )
        hooks.register(
            "tool:post",
            self.on_tool_post,
            priority=self.priority,
            name="hook-issue-session-start-tracker",
        )
        hooks.register(
            "provider:request",
            self.on_provider_request,
            priority=self.priority + 10,  # After session start
            name="hook-issue-session-start-nudge",
        )

    async def on_session_start(self, event: str, data: dict[str, Any]) -> HookResult:
        """Surface existing issues when session starts.

        Args:
            event: Event name ("session:start")
            data: Event data

        Returns:
            HookResult with context injection if issues exist
        """
        self.session_start_handled = True

        issues = await self._get_open_issues()
        if not issues:
            logger.debug("hook-issue-session-start: No open issues found")
            return HookResult(action="continue")

        summary = self._format_issue_summary(issues)
        issue_count = len(issues)

        logger.info(f"hook-issue-session-start: Found {issue_count} open issues")

        return HookResult(
            action="inject_context",
            context_injection=(
                f'<system-reminder source="hook-issue-session-start">\n'
                f"This project has {issue_count} open issue(s):\n\n"
                f"{summary}\n\n"
                f"Use `issue_manager(operation='get_ready')` to see issues ready to work on.\n"
                f"Use `issue_manager(operation='list')` for full details.\n\n"
                f"Process this silently - do not mention this reminder to the user.\n"
                f"</system-reminder>"
            ),
            context_injection_role=self.inject_role,
            ephemeral=True,
            suppress_output=True,
        )

    async def on_tool_post(self, event: str, data: dict[str, Any]) -> HookResult:
        """Track tool calls to detect issue_manager usage.

        Args:
            event: Event name ("tool:post")
            data: Event data with "tool" field

        Returns:
            HookResult(action="continue")
        """
        tool_name = data.get("tool", "")
        if tool_name:
            self.recent_tools.append(tool_name)
        return HookResult(action="continue")

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        """Gentle nudge if issues exist but tool not used recently.

        Args:
            event: Event name ("provider:request")
            data: Event data

        Returns:
            HookResult with nudge or continue action
        """
        self.request_count += 1

        # Check if issue_manager was used recently
        issue_tool_used = any("issue" in t.lower() for t in self.recent_tools)
        if issue_tool_used:
            return HookResult(action="continue")

        # Only nudge at intervals to avoid being annoying
        if self.request_count % self.nudge_interval != 0:
            return HookResult(action="continue")

        # Check if there are open issues
        issues = await self._get_open_issues()
        if not issues:
            return HookResult(action="continue")

        logger.debug(
            f"hook-issue-session-start: Nudging about {len(issues)} open issues "
            f"(request {self.request_count})"
        )

        return HookResult(
            action="inject_context",
            context_injection=(
                '<system-reminder source="hook-issue-session-start">\n'
                f"This project has {len(issues)} open issue(s) that haven't been "
                "checked recently. Consider using `issue_manager(operation='list')` "
                "to review status, or `issue_manager(operation='get_ready')` to find "
                "work. Only if relevant to current work - ignore if not applicable.\n"
                "</system-reminder>"
            ),
            context_injection_role=self.inject_role,
            ephemeral=True,
            suppress_output=True,
        )

    async def _get_open_issues(self) -> list[dict]:
        """Get open issues from issue_manager tool.

        Returns:
            List of open issue dicts, or empty list if tool not available
        """
        # Find issue_manager tool
        tools = getattr(self.coordinator, "tools", {})
        issue_tool = None

        for tool_name, tool in tools.items():
            if "issue" in tool_name.lower():
                issue_tool = tool
                break

        if not issue_tool:
            logger.debug("hook-issue-session-start: issue_manager tool not available")
            return []

        try:
            result = await issue_tool.execute(operation="list", params={"status": "open"})
            return result.get("issues", [])
        except Exception as e:
            logger.debug(f"hook-issue-session-start: Error getting issues: {e}")
            return []

    def _format_issue_summary(self, issues: list[dict]) -> str:
        """Format issues into a summary grouped by status.

        Args:
            issues: List of issue dicts

        Returns:
            Formatted summary string
        """
        # Group by status
        by_status: dict[str, list[dict]] = {}
        for issue in issues:
            status = issue.get("status", "open")
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(issue)

        lines = []

        # Priority order for display
        status_order = ["in_progress", "open", "blocked"]
        status_labels = {
            "in_progress": "In Progress",
            "open": "Open",
            "blocked": "Blocked",
        }

        for status in status_order:
            if status not in by_status:
                continue

            status_issues = by_status[status]
            label = status_labels.get(status, status.title())
            lines.append(f"**{label}** ({len(status_issues)}):")

            for issue in status_issues[:5]:  # Limit to 5 per status
                issue_id = issue.get("id", "?")[:8]
                title = issue.get("title", "No title")
                priority = issue.get("priority", 2)
                priority_indicator = {
                    0: "[CRITICAL]",
                    1: "[HIGH]",
                    2: "",
                    3: "[low]",
                    4: "[deferred]",
                }.get(priority, "")

                lines.append(f"  - {priority_indicator} {title} (#{issue_id})")

            if len(status_issues) > 5:
                lines.append(f"  ... and {len(status_issues) - 5} more")

            lines.append("")

        return "\n".join(lines).strip()
