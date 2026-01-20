"""
Issue management tool with embedded IssueManager.

Provides assistant interface to persistent issue queue with dependency management.
Pure-module implementation requiring zero kernel changes.
"""

import logging
import re
import subprocess
from datetime import datetime
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

    def __init__(
        self,
        coordinator: ModuleCoordinator,
        data_dir: Path,
        actor: str,
        session_id: str | None = None,
    ):
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
        self.issue_manager = IssueManager(
            data_dir=data_dir, actor=actor, session_id=session_id
        )
        logger.debug(
            f"Created embedded IssueManager at {data_dir} with session_id={session_id}"
        )

    @property
    def input_schema(self) -> dict:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "create",
                        "list",
                        "get",
                        "update",
                        "close",
                        "add_dependency",
                        "get_ready",
                        "get_blocked",
                        "get_sessions",
                        "sync_to_github",
                    ],
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
            elif operation == "sync_to_github":
                result = await self._sync_to_github(params)
            else:
                return ToolResult(
                    success=False, error={"message": f"Unknown operation: {operation}"}
                )

            return ToolResult(success=True, output=result)

        except Exception as e:
            logger.error(f"Issue operation '{operation}' failed: {e}")
            return ToolResult(
                success=False, error={"message": f"Operation failed: {str(e)}"}
            )

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
        if "priority" in filtered_params and isinstance(
            filtered_params["priority"], str
        ):
            priority_map = {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "normal": 2,
                "low": 3,
                "deferred": 4,
            }
            priority_str = filtered_params["priority"].lower()
            if priority_str in priority_map:
                filtered_params["priority"] = priority_map[priority_str]
            else:
                try:
                    filtered_params["priority"] = int(filtered_params["priority"])
                except ValueError:
                    raise ValueError(
                        f"Invalid priority value: {filtered_params['priority']}"
                    )

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
            priority_map = {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "normal": 2,
                "low": 3,
                "deferred": 4,
            }
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
                {"issue": issue.to_dict(), "blockers": [b.to_dict() for b in blockers]}
                for issue, blockers in blocked
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

    async def _verify_github_permissions(self, repo: str) -> dict:
        """Verify user has permissions to create issues in the GitHub repo.

        Args:
            repo: GitHub repo in org/name format

        Returns:
            Dict with success status and error message if failed
        """
        # Check if gh CLI is installed
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": "GitHub CLI (gh) is not installed. Install with: brew install gh (macOS) or see https://cli.github.com/",
                }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "GitHub CLI (gh) is not installed. Install with: brew install gh (macOS) or see https://cli.github.com/",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "GitHub CLI check timed out. Please verify gh is working correctly.",
            }

        # Check if authenticated
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": "Not authenticated with GitHub. Run: gh auth login",
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "GitHub authentication check timed out. Please verify gh is working correctly.",
            }

        # Check if user has write access to the repo
        try:
            # Try to list issues - this requires read access at minimum
            result = subprocess.run(
                ["gh", "issue", "list", "--repo", repo, "--limit", "1", "--json", "number"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()

                # Parse common error scenarios
                if "404" in error_msg or "not found" in error_msg.lower():
                    return {
                        "success": False,
                        "error": f"Repository '{repo}' not found or you don't have access. Please verify:\n"
                        f"  1. The repository exists\n"
                        f"  2. You have access to it\n"
                        f"  3. You may need to request access from the repository owner",
                    }
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    return {
                        "success": False,
                        "error": f"Access forbidden to repository '{repo}'. You don't have permission to access this repository.\n"
                        f"Please request access from the repository owner.",
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to access repository '{repo}': {error_msg}\n"
                        f"You may need to request access from the repository owner.",
                    }

            # We can read issues, but we need write access to create them
            # Try to get repo info to check permissions
            result = subprocess.run(
                ["gh", "repo", "view", repo, "--json", "viewerPermission"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                import json

                try:
                    repo_info = json.loads(result.stdout)
                    permission = repo_info.get("viewerPermission", "").lower()

                    # Check if user has write, maintain, or admin permission
                    if permission in ["write", "maintain", "admin"]:
                        return {"success": True}
                    else:
                        return {
                            "success": False,
                            "error": f"You have '{permission}' access to '{repo}', but 'write' access is required to create issues.\n"
                            f"Please request write access from the repository owner.",
                        }
                except (json.JSONDecodeError, KeyError):
                    # If we can't parse permissions, assume they have access
                    # (they were able to list issues)
                    logger.warning(
                        f"Could not parse repo permissions for {repo}, assuming access is OK"
                    )
                    return {"success": True}

            # If repo view failed but we could list issues, assume it's OK
            return {"success": True}

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "GitHub repository access check timed out. Please verify your connection and try again.",
            }
        except Exception as e:
            logger.error(f"Unexpected error checking GitHub permissions: {e}")
            return {
                "success": False,
                "error": f"Could not verify repository access: {str(e)}",
            }

    async def _sync_to_github(self, params: dict) -> dict:
        """Sync local issues to GitHub.

        For each local issue not yet synced:
        1. Create GitHub issue with structured labels
        2. Store GitHub issue number in local metadata
        3. Return summary of synced issues

        Args:
            params: Optional filters and config
                - repo: GitHub repo (default: microsoft-amplifier/amplifier-shared)
                - include_closed: Sync closed issues (default: False)

        Returns:
            Dict with synced issues, counts, and any errors
        """
        # Get repo from config or params
        repo = params.get("repo", "microsoft-amplifier/amplifier-shared")

        # Verify permissions before attempting sync
        permission_check = await self._verify_github_permissions(repo)
        if not permission_check["success"]:
            return {
                "synced": [],
                "synced_count": 0,
                "skipped_count": 0,
                "errors": [{"error": permission_check["error"]}],
                "error_count": 1,
                "permission_denied": True,
            }

        # Get issues to sync (default: all non-synced)
        all_issues = self.issue_manager.list_issues()

        synced = []
        skipped = []
        errors = []

        for issue in all_issues:
            # Skip if already synced
            if issue.metadata and issue.metadata.get("github_issue_number"):
                skipped.append(issue.issue_id)
                continue

            # Skip closed issues unless explicitly requested
            if issue.status == "closed" and not params.get("include_closed", False):
                skipped.append(issue.issue_id)
                continue

            try:
                gh_number = await self._create_github_issue(issue, repo)

                # Update local issue with GitHub metadata
                updated_metadata = issue.metadata.copy() if issue.metadata else {}
                updated_metadata.update(
                    {
                        "github_issue_number": gh_number,
                        "github_repo": repo,
                        "synced_at": datetime.now().isoformat(),
                    }
                )

                self.issue_manager.update_issue(
                    issue.issue_id, metadata=updated_metadata
                )

                synced.append(
                    {
                        "issue_id": issue.issue_id,
                        "github_number": gh_number,
                        "github_url": f"https://github.com/{repo}/issues/{gh_number}",
                    }
                )

            except Exception as e:
                logger.error(f"Failed to sync issue {issue.issue_id}: {e}")
                errors.append({"issue_id": issue.issue_id, "error": str(e)})

        return {
            "synced": synced,
            "synced_count": len(synced),
            "skipped_count": len(skipped),
            "errors": errors,
            "error_count": len(errors),
        }

    async def _create_github_issue(self, issue, repo: str) -> int:
        """Create GitHub issue from local issue.

        Args:
            issue: Local Issue object
            repo: GitHub repo in org/name format

        Returns:
            GitHub issue number

        Raises:
            ValueError: If issue number cannot be parsed
            subprocess.CalledProcessError: If gh command fails
        """

        # Map priority to label
        priority_labels = {
            0: "priority:critical",
            1: "priority:high",
            2: "priority:normal",
            3: "priority:low",
            4: "priority:deferred",
        }

        # Map status to label
        status_labels = {
            "open": "status:open",
            "in_progress": "status:in-progress",
            "blocked": "status:blocked",
            "closed": "status:closed",
        }

        # Build labels
        labels = [
            status_labels.get(issue.status, "status:open"),
            priority_labels.get(issue.priority, "priority:normal"),
        ]

        # Add area label if in metadata
        if issue.metadata and "area" in issue.metadata:
            labels.append(f"area:{issue.metadata['area']}")

        # Format body
        body = f"""**Description**
{issue.description or "No description provided"}

**Created**: {issue.created_at}
**Session**: {issue.session_id or "N/A"}
**Local Issue ID**: {issue.issue_id}

---
*Synced from Amplifier local issue tracker*
"""

        # Build gh command
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            issue.title,
            "--body",
            body,
            "--label",
            ",".join(labels),
        ]

        if issue.assignee:
            cmd.extend(["--assignee", issue.assignee])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse issue number from URL
        # Format: "https://github.com/org/repo/issues/42"
        match = re.search(r"/issues/(\d+)", result.stdout)
        if match:
            return int(match.group(1))
        else:
            raise ValueError(f"Could not parse issue number from: {result.stdout}")
