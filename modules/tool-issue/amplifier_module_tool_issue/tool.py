"""
Issue management tool with embedded IssueManager.

Provides assistant interface to persistent issue queue with dependency management.
Pure-module implementation requiring zero kernel changes.
"""

import logging
from pathlib import Path
from typing import Any

from amplifier_core import ModuleCoordinator
from amplifier_core import ToolResult
from amplifier_module_issue_manager import IssueManager

logger = logging.getLogger(__name__)


class IssueTool:
    """Tool for issue management operations with embedded state."""

    name = "issue_manager"
    description = "Manage issues in the persistent issue queue with dependency tracking and session linking"

    def __init__(self, coordinator: ModuleCoordinator, data_dir: Path, actor: str, session_id: str | None = None):
        """Initialize issue tool with embedded IssueManager.

        Args:
            coordinator: Module coordinator (for hooks integration)
            data_dir: Directory for JSONL storage
            actor: Default actor for events
            session_id: Amplifier session ID for session linking
        """
        self.coordinator = coordinator
        self.session_id = session_id

        # Create embedded IssueManager instance with session tracking
        self.issue_manager = IssueManager(data_dir=data_dir, actor=actor, session_id=session_id)
        logger.debug(f"Created embedded IssueManager at {data_dir} with session_id={session_id}")

    @property
    def input_schema(self) -> dict:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "list", "get", "update", "close", "add_dependency", "get_ready", "get_blocked", "get_sessions"],
                    "description": "Operation to perform",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the operation. Use issue_id to identify issues.",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Execute issue operation using embedded manager."""
        operation = input.get("operation")
        if not operation:
            return ToolResult(success=False, error={"message": "Operation is required"})

        params = input.get("params", {})

        try:
            if operation == "create":
                result = await self._create_issue(params)
            elif operation == "list":
                result = await self._list_issues(params)
            elif operation == "get":
                result = await self._get_issue(params)
            elif operation == "update":
                result = await self._update_issue(params)
            elif operation == "close":
                result = await self._close_issue(params)
            elif operation == "add_dependency":
                result = await self._add_dependency(params)
            elif operation == "get_ready":
                result = await self._get_ready_issues(params)
            elif operation == "get_blocked":
                result = await self._get_blocked_issues(params)
            elif operation == "get_sessions":
                result = await self._get_sessions(params)
            else:
                return ToolResult(success=False, error={"message": f"Unknown operation: {operation}"})

            return ToolResult(success=True, output=result)

        except Exception as e:
            logger.error(f"Issue operation '{operation}' failed: {e}")
            return ToolResult(success=False, error={"message": f"Operation failed: {str(e)}"})

    async def _create_issue(self, params: dict) -> dict:
        """Create a new issue."""
        # Filter params to only those accepted by create_issue
        allowed_params = {
            "title",
            "description",
            "priority",
            "issue_type",
            "assignee",
            "parent_id",
            "discovered_from",
            "metadata",
        }
        filtered_params = {k: v for k, v in params.items() if k in allowed_params}

        # Convert priority string to int
        if "priority" in filtered_params and isinstance(filtered_params["priority"], str):
            priority_map = {"critical": 0, "high": 1, "medium": 2, "normal": 2, "low": 3, "deferred": 4}
            priority_str = filtered_params["priority"].lower()
            if priority_str in priority_map:
                filtered_params["priority"] = priority_map[priority_str]
            else:
                try:
                    filtered_params["priority"] = int(filtered_params["priority"])
                except ValueError:
                    raise ValueError(f"Invalid priority value: {filtered_params['priority']}")

        issue = self.issue_manager.create_issue(**filtered_params)
        return {"issue": issue.to_dict()}

    async def _list_issues(self, params: dict) -> dict:
        """List issues with optional filters."""
        issues = self.issue_manager.list_issues(**params)
        return {"issues": [i.to_dict() for i in issues], "count": len(issues)}

    async def _get_issue(self, params: dict) -> dict:
        """Get a specific issue by ID."""
        issue_id = params.get("issue_id")
        if not issue_id:
            raise ValueError("issue_id is required")

        issue = self.issue_manager.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        return {"issue": issue.to_dict()}

    async def _update_issue(self, params: dict) -> dict:
        """Update an issue."""
        issue_id = params.pop("issue_id", None)
        if not issue_id:
            raise ValueError("issue_id is required")

        # Convert priority if it's a string
        if "priority" in params and isinstance(params["priority"], str):
            priority_map = {"critical": 0, "high": 1, "medium": 2, "normal": 2, "low": 3, "deferred": 4}
            priority_str = params["priority"].lower()
            if priority_str in priority_map:
                params["priority"] = priority_map[priority_str]
            else:
                try:
                    params["priority"] = int(params["priority"])
                except ValueError:
                    raise ValueError(f"Invalid priority value: {params['priority']}")

        issue = self.issue_manager.update_issue(issue_id, **params)
        return {"issue": issue.to_dict()}

    async def _close_issue(self, params: dict) -> dict:
        """Close an issue."""
        issue = self.issue_manager.close_issue(**params)
        return {"issue": issue.to_dict()}

    async def _add_dependency(self, params: dict) -> dict:
        """Add a dependency between issues."""
        dep = self.issue_manager.add_dependency(**params)
        return {"dependency": dep.to_dict()}

    async def _get_ready_issues(self, params: dict) -> dict:
        """Get issues that are ready to work on (no blockers)."""
        issues = self.issue_manager.get_ready_issues(**params)
        return {"ready_issues": [i.to_dict() for i in issues], "count": len(issues)}

    async def _get_blocked_issues(self, params: dict) -> dict:
        """Get issues that are blocked and their blockers."""
        blocked = self.issue_manager.get_blocked_issues()
        return {
            "blocked_issues": [
                {"issue": issue.to_dict(), "blockers": [b.to_dict() for b in blockers]} for issue, blockers in blocked
            ],
            "count": len(blocked),
        }

    async def _get_sessions(self, params: dict) -> dict:
        """Get all Amplifier sessions that have touched an issue.

        This enables session linking - finding which sessions created, updated,
        claimed, or closed an issue, so users can resume sessions for follow-up
        questions with full context.

        Args:
            params: Must contain issue_id

        Returns:
            Dict with linked_sessions list and hint for resuming sessions
        """
        issue_id = params.get("issue_id")
        if not issue_id:
            raise ValueError("issue_id is required")

        return self.issue_manager.get_issue_sessions(issue_id)
