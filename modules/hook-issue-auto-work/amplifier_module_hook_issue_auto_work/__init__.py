"""Issue auto-work hook module.

Automatically checks for ready issues after each turn completes and keeps
the assistant working autonomously through the issue queue.
"""

import logging
from typing import Any

from amplifier_core import HookResult
from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the issue auto-work hook.

    Args:
        coordinator: Module coordinator
        config: Optional configuration
            - priority: Hook priority (default: 100, runs late to see full turn)
            - max_auto_iterations: Max iterations before requiring user input (default: 10)
            - inject_role: Role for context injection ("user" or "system", default: "system")

    Returns:
        Optional cleanup function
    """
    config = config or {}
    hook = IssueAutoWorkHook(coordinator, config)
    hook.register(coordinator.hooks)
    logger.info("Mounted hook-issue-auto-work")
    return


class IssueAutoWorkHook:
    """Hook that automatically continues work on ready issues.

    After each turn completes (prompt:complete event), checks if there are
    more ready issues to work on. If yes, injects context to keep assistant
    working autonomously through the issue queue.
    """

    def __init__(self, coordinator: ModuleCoordinator, config: dict[str, Any]):
        """Initialize issue auto-work hook.

        Args:
            coordinator: Module coordinator (for accessing issue state)
            config: Configuration dict
                - priority: Hook priority (default: 100)
                - max_auto_iterations: Max iterations before user check-in (default: 10)
                - inject_role: Context injection role (default: "system")
        """
        self.coordinator = coordinator
        self.priority = config.get("priority", 100)
        self.max_auto_iterations = config.get("max_auto_iterations", 10)
        self.inject_role = config.get("inject_role", "system")
        
        # Track auto-work iterations to prevent infinite loops
        self.auto_iteration_count = 0

    def register(self, hooks):
        """Register hook on PROMPT_COMPLETE event."""
        hooks.register("prompt:complete", self.on_prompt_complete, priority=self.priority, name="hook-issue-auto-work")

    async def on_prompt_complete(self, event: str, data: dict[str, Any]) -> HookResult:
        """Check for ready issues after each turn and continue working if found.

        Args:
            event: Event name ("prompt:complete")
            data: Event data

        Returns:
            HookResult with context injection to continue work, or continue action
        """
        # Check if issue_manager tool is available
        tools = getattr(self.coordinator, "tools", {})
        issue_manager_tool = None
        
        for tool_name, tool in tools.items():
            if "issue" in tool_name.lower():
                issue_manager_tool = tool
                break
        
        if not issue_manager_tool:
            logger.debug("hook-issue-auto-work: issue_manager tool not available, skipping")
            return HookResult(action="continue")

        # Check for iteration limit to prevent infinite loops
        self.auto_iteration_count += 1
        
        if self.auto_iteration_count >= self.max_auto_iterations:
            logger.info(
                f"hook-issue-auto-work: Reached max auto iterations ({self.max_auto_iterations}), "
                "requiring user check-in"
            )
            # Reset counter and let user decide what's next
            self.auto_iteration_count = 0
            return HookResult(action="continue")

        try:
            # Call issue_manager to get ready issues
            result = await issue_manager_tool.execute(
                operation="get_ready",
                params={"limit": 5}
            )
            
            ready_issues = result.get("issues", [])
            
            if not ready_issues:
                logger.debug("hook-issue-auto-work: No ready issues found")
                # Reset counter when no work left
                self.auto_iteration_count = 0
                return HookResult(action="continue")

            # Format ready issues for context injection
            issues_text = self._format_ready_issues(ready_issues)
            
            logger.info(
                f"hook-issue-auto-work: Found {len(ready_issues)} ready issues, "
                f"injecting context to continue work (iteration {self.auto_iteration_count}/{self.max_auto_iterations})"
            )
            
            # Inject context to tell assistant to keep working
            context_message = (
                f"<system-reminder>\n"
                f"You have {len(ready_issues)} ready issue(s) remaining in your work queue. "
                f"Continue working on the next ready issue. Use the issue_manager tool to get the next issue "
                f"and update its status to 'in_progress'.\n\n"
                f"Ready issues:\n{issues_text}\n\n"
                f"Do NOT ask the user what to do next - autonomously continue with the next issue. "
                f"Only stop and present to the user when ALL issues are completed or blocked.\n"
                f"</system-reminder>"
            )
            
            return HookResult(
                action="inject_context",
                context_injection=context_message,
                context_injection_role=self.inject_role,
                ephemeral=True,  # Don't store in history
                suppress_output=True,  # Don't show to user
            )
            
        except Exception as e:
            logger.error(f"hook-issue-auto-work: Error checking for ready issues: {e}")
            # Don't block on errors
            return HookResult(action="continue")

    def _format_ready_issues(self, issues: list[dict]) -> str:
        """Format ready issues for display.

        Args:
            issues: List of issue dicts

        Returns:
            Formatted string with issue summaries
        """
        lines = []
        for issue in issues:
            issue_id = issue.get("issue_id", "?")
            title = issue.get("title", "No title")
            priority = issue.get("priority", 2)
            issue_type = issue.get("issue_type", "task")
            
            # Priority indicators
            priority_indicator = {
                0: "🔴",  # Critical
                1: "🟠",  # High
                2: "🟡",  # Normal
                3: "🟢",  # Low
                4: "⚪",  # Deferred
            }.get(priority, "🟡")
            
            lines.append(f"{priority_indicator} #{issue_id} [{issue_type}] {title}")
        
        return "\n".join(lines)
