"""Issue manager implementation."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .algorithms import detect_cycle
from .algorithms import get_blocked_issues
from .algorithms import get_ready_issues
from .index import IssueIndex
from .models import Dependency
from .models import Issue
from .models import IssueEvent
from .storage import Storage


class IssueManager:
    """Issue manager with CRUD, dependencies, and scheduling.

    Provides a simple interface for managing issues with dependencies,
    priority-based scheduling, and event tracking.
    """

    def __init__(self, data_dir: Path, actor: str = "system"):
        """Initialize issue manager.

        Args:
            data_dir: Directory for JSONL storage
            actor: Default actor for events
        """
        self.data_dir = data_dir
        self.actor = actor
        self.storage = Storage(data_dir)
        self.index = IssueIndex()

        self._load_all()

    def _load_all(self) -> None:
        """Load all data from storage into index."""
        issues = self.storage.load_issues()
        for issue in issues:
            self.index.add_issue(issue)

        deps = self.storage.load_dependencies()
        for dep in deps:
            self.index.add_dependency(dep)

    def _save_issues(self) -> None:
        """Save all issues to storage."""
        issues = list(self.index.issues.values())
        self.storage.save_issues(issues)

    def _save_dependencies(self) -> None:
        """Save all dependencies to storage."""
        deps = self.index.get_all_dependencies()
        self.storage.save_dependencies(deps)

    def _emit_event(self, issue_id: str, event_type: str, changes: dict[str, Any]) -> None:
        """Emit an issue event.

        Args:
            issue_id: Issue ID
            event_type: Event type
            changes: Changes made
        """
        event = IssueEvent(
            id=str(uuid.uuid4()),
            issue_id=issue_id,
            event_type=event_type,
            actor=self.actor,
            changes=changes,
            timestamp=datetime.now(),
        )
        self.storage.append_event(event)

    def create_issue(
        self,
        title: str,
        description: str = "",
        priority: int = 2,
        issue_type: str = "task",
        assignee: str | None = None,
        parent_id: str | None = None,
        discovered_from: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Issue:
        """Create a new issue.

        Args:
            title: Issue title
            description: Issue description
            priority: Priority (0-4, 0=highest)
            issue_type: Type (bug|feature|task|epic|chore)
            assignee: Assignee name
            parent_id: Parent issue ID
            discovered_from: Issue this was discovered from
            metadata: Additional metadata

        Returns:
            Created issue

        Raises:
            ValueError: If priority or issue_type is invalid
        """
        if priority < 0 or priority > 4:
            raise ValueError("Priority must be 0-4")

        if issue_type not in ("bug", "feature", "task", "epic", "chore"):
            raise ValueError("Invalid issue_type")

        now = datetime.now()
        issue = Issue(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status="open",
            priority=priority,
            issue_type=issue_type,
            assignee=assignee,
            created_at=now,
            updated_at=now,
            parent_id=parent_id,
            discovered_from=discovered_from,
            metadata=metadata or {},
        )

        self.index.add_issue(issue)
        self._save_issues()
        self._emit_event(issue.id, "created", {"issue": issue.to_dict()})

        return issue

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get issue by ID.

        Args:
            issue_id: Issue ID

        Returns:
            Issue if found, None otherwise
        """
        return self.index.get_issue(issue_id)

    def update_issue(
        self,
        issue_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        assignee: str | None = None,
        blocking_notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Issue:
        """Update an issue.

        Args:
            issue_id: Issue ID
            title: New title
            description: New description
            status: New status (open|in_progress|blocked|closed)
            priority: New priority (0-4)
            assignee: New assignee
            blocking_notes: Notes about what's blocking
            metadata: New metadata (merged with existing)

        Returns:
            Updated issue

        Raises:
            ValueError: If issue not found or invalid values
        """
        issue = self.index.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue not found: {issue_id}")

        changes = {}

        if title is not None:
            changes["title"] = {"old": issue.title, "new": title}
            issue.title = title

        if description is not None:
            changes["description"] = {"old": issue.description, "new": description}
            issue.description = description

        if status is not None:
            if status not in ("open", "in_progress", "blocked", "closed"):
                raise ValueError("Invalid status")
            changes["status"] = {"old": issue.status, "new": status}
            issue.status = status

        if priority is not None:
            if priority < 0 or priority > 4:
                raise ValueError("Priority must be 0-4")
            changes["priority"] = {"old": issue.priority, "new": priority}
            issue.priority = priority

        if assignee is not None:
            changes["assignee"] = {"old": issue.assignee, "new": assignee}
            issue.assignee = assignee

        if blocking_notes is not None:
            changes["blocking_notes"] = {
                "old": issue.blocking_notes,
                "new": blocking_notes,
            }
            issue.blocking_notes = blocking_notes

        if metadata is not None:
            issue.metadata.update(metadata)
            changes["metadata"] = metadata

        issue.updated_at = datetime.now()

        self._save_issues()
        self._emit_event(issue_id, "updated", changes)

        return issue

    def close_issue(self, issue_id: str, reason: str = "Completed") -> Issue:
        """Close an issue.

        Args:
            issue_id: Issue ID
            reason: Reason for closing

        Returns:
            Closed issue

        Raises:
            ValueError: If issue not found
        """
        issue = self.index.get_issue(issue_id)
        if not issue:
            raise ValueError(f"Issue not found: {issue_id}")

        issue.status = "closed"
        issue.closed_at = datetime.now()
        issue.updated_at = datetime.now()

        self._save_issues()
        self._emit_event(issue_id, "closed", {"reason": reason})

        return issue

    def list_issues(
        self,
        status: str | None = None,
        priority: int | None = None,
        issue_type: str | None = None,
        assignee: str | None = None,
    ) -> list[Issue]:
        """List issues with optional filters.

        Args:
            status: Filter by status
            priority: Filter by priority
            issue_type: Filter by issue type
            assignee: Filter by assignee

        Returns:
            List of matching issues
        """
        return self.index.list_issues(status, priority, issue_type, assignee)

    def add_dependency(self, from_id: str, to_id: str, dep_type: str = "blocks") -> Dependency:
        """Add a dependency between issues.

        Args:
            from_id: Blocked issue ID
            to_id: Blocking issue ID
            dep_type: Dependency type (blocks|related|parent-child|discovered-from)

        Returns:
            Created dependency

        Raises:
            ValueError: If issues not found, cycle detected, or invalid dep_type
        """
        if not self.index.get_issue(from_id):
            raise ValueError(f"Issue not found: {from_id}")
        if not self.index.get_issue(to_id):
            raise ValueError(f"Issue not found: {to_id}")

        if dep_type not in ("blocks", "related", "parent-child", "discovered-from"):
            raise ValueError("Invalid dep_type")

        if detect_cycle(self.index, from_id, to_id):
            raise ValueError("Dependency would create a cycle")

        dep = Dependency(
            from_id=from_id,
            to_id=to_id,
            dep_type=dep_type,
            created_at=datetime.now(),
        )

        self.index.add_dependency(dep)
        self._save_dependencies()
        self._emit_event(
            from_id,
            "dependency_added",
            {"from_id": from_id, "to_id": to_id, "dep_type": dep_type},
        )

        return dep

    def remove_dependency(self, from_id: str, to_id: str) -> None:
        """Remove a dependency.

        Args:
            from_id: Blocked issue ID
            to_id: Blocking issue ID

        Raises:
            ValueError: If dependency not found
        """
        if (from_id, to_id) not in self.index.dependencies:
            raise ValueError(f"Dependency not found: {from_id} -> {to_id}")

        self.index.remove_dependency(from_id, to_id)
        self._save_dependencies()
        self._emit_event(
            from_id,
            "dependency_removed",
            {"from_id": from_id, "to_id": to_id},
        )

    def get_dependencies(self, issue_id: str) -> list[Issue]:
        """Get all issues blocking this issue.

        Args:
            issue_id: Issue ID

        Returns:
            List of blocking issues
        """
        blocker_ids = self.index.get_blockers(issue_id)
        result = []
        for bid in blocker_ids:
            issue = self.index.get_issue(bid)
            if issue:
                result.append(issue)
        return result

    def get_dependents(self, issue_id: str) -> list[Issue]:
        """Get all issues dependent on this issue.

        Args:
            issue_id: Issue ID

        Returns:
            List of dependent issues
        """
        dependent_ids = self.index.get_dependents(issue_id)
        result = []
        for did in dependent_ids:
            issue = self.index.get_issue(did)
            if issue:
                result.append(issue)
        return result

    def get_ready_issues(self, limit: int | None = None) -> list[Issue]:
        """Get issues ready to work.

        Args:
            limit: Maximum number of issues

        Returns:
            List of ready issues sorted by priority
        """
        return get_ready_issues(self.index, limit)

    def get_blocked_issues(self) -> list[tuple[Issue, list[Issue]]]:
        """Get blocked issues with their blockers.

        Returns:
            List of (blocked_issue, blocker_issues) tuples
        """
        return get_blocked_issues(self.index)

    def get_issue_events(self, issue_id: str) -> list[IssueEvent]:
        """Get all events for an issue.

        Args:
            issue_id: Issue ID

        Returns:
            List of events for this issue
        """
        all_events = self.storage.load_events()
        return [e for e in all_events if e.issue_id == issue_id]
