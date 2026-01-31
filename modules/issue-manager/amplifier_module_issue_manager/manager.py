"""Issue manager implementation.

Uses file-as-source-of-truth pattern with file locking for multi-process safety.
The IssueIndex is rebuilt fresh on each operation rather than cached.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import TypeVar

from filelock import FileLock

from .algorithms import detect_cycle
from .algorithms import get_blocked_issues
from .algorithms import get_ready_issues
from .index import IssueIndex
from .models import Dependency
from .models import Issue
from .models import IssueEvent
from .storage import Storage

T = TypeVar("T")


class IssueManager:
    """Issue manager with CRUD, dependencies, scheduling, and session linking.

    Uses file-based locking for multi-process safety. The index is rebuilt
    fresh on each operation to ensure consistency across processes.
    """

    def __init__(
        self, data_dir: Path, actor: str = "system", session_id: str | None = None
    ):
        """Initialize issue manager.

        Args:
            data_dir: Directory for JSONL storage
            actor: Default actor for events
            session_id: Amplifier session ID for linking issues to sessions
        """
        self.data_dir = data_dir
        self.actor = actor
        self.session_id = session_id
        self.storage = Storage(data_dir)
        self._lock_path = data_dir / ".issues.lock"

        # Ensure data directory exists for lock file
        data_dir.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self) -> FileLock:
        """Get file lock for exclusive access.

        Returns:
            FileLock context manager with 10 second timeout
        """
        return FileLock(self._lock_path, timeout=10)

    def _load_fresh(self) -> IssueIndex:
        """Load fresh index from disk.

        Returns:
            New IssueIndex populated from current file state
        """
        index = IssueIndex()

        issues = self.storage.load_issues()
        for issue in issues:
            index.add_issue(issue)

        deps = self.storage.load_dependencies()
        for dep in deps:
            index.add_dependency(dep)

        return index

    def _save_issues(self, index: IssueIndex) -> None:
        """Save all issues to storage.

        Args:
            index: The index containing issues to save
        """
        issues = list(index.issues.values())
        self.storage.save_issues(issues)

    def _save_dependencies(self, index: IssueIndex) -> None:
        """Save all dependencies to storage.

        Args:
            index: The index containing dependencies to save
        """
        deps = index.get_all_dependencies()
        self.storage.save_dependencies(deps)

    def _with_lock(self, mutation_fn: Callable[[IssueIndex], T]) -> T:
        """Execute a mutation under lock with fresh state.

        Pattern: lock -> load fresh -> mutate -> save -> unlock

        Args:
            mutation_fn: Function that takes an IssueIndex and returns a result.
                        The function should mutate the index as needed.

        Returns:
            Result from the mutation function
        """
        with self._acquire_lock():
            index = self._load_fresh()
            result = mutation_fn(index)
            self._save_issues(index)
            return result

    def _emit_event(
        self, issue_id: str, event_type: str, changes: dict[str, Any]
    ) -> None:
        """Emit an issue event with session tracking.

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
            session_id=self.session_id,
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

        def do_create(index: IssueIndex) -> Issue:
            index.add_issue(issue)
            return issue

        result = self._with_lock(do_create)
        self._emit_event(issue.id, "created", {"issue": issue.to_dict()})
        return result

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get issue by ID.

        Args:
            issue_id: Issue ID

        Returns:
            Issue if found, None otherwise
        """
        with self._acquire_lock():
            index = self._load_fresh()
            return index.get_issue(issue_id)

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
            status: New status (open|in_progress|blocked|closed|completed|pending_user_input)
            priority: New priority (0-4)
            assignee: New assignee
            blocking_notes: Notes about what's blocking
            metadata: New metadata (merged with existing)

        Returns:
            Updated issue

        Raises:
            ValueError: If issue not found or invalid values
        """
        changes: dict[str, Any] = {}

        def do_update(index: IssueIndex) -> Issue:
            nonlocal changes
            issue = index.get_issue(issue_id)
            if not issue:
                raise ValueError(f"Issue not found: {issue_id}")

            if title is not None:
                changes["title"] = {"old": issue.title, "new": title}
                issue.title = title

            if description is not None:
                changes["description"] = {"old": issue.description, "new": description}
                issue.description = description

            if status is not None:
                # Normalize status aliases for compatibility with other systems (e.g., foreman)
                status_aliases = {"done": "completed", "waiting": "pending_user_input"}
                normalized_status = status_aliases.get(status, status)
                valid_statuses = (
                    "open",
                    "in_progress",
                    "blocked",
                    "closed",
                    "completed",
                    "pending_user_input",
                )
                if normalized_status not in valid_statuses:
                    raise ValueError(
                        f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                    )
                changes["status"] = {"old": issue.status, "new": normalized_status}
                issue.status = normalized_status

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
            return issue

        result = self._with_lock(do_update)
        self._emit_event(issue_id, "updated", changes)
        return result

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

        def do_close(index: IssueIndex) -> Issue:
            issue = index.get_issue(issue_id)
            if not issue:
                raise ValueError(f"Issue not found: {issue_id}")

            issue.status = "closed"
            issue.closed_at = datetime.now()
            issue.updated_at = datetime.now()
            return issue

        result = self._with_lock(do_close)
        self._emit_event(issue_id, "closed", {"reason": reason})
        return result

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
        with self._acquire_lock():
            index = self._load_fresh()
            return index.list_issues(status, priority, issue_type, assignee)

    def add_dependency(
        self, from_id: str, to_id: str, dep_type: str = "blocks"
    ) -> Dependency:
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
        if dep_type not in ("blocks", "related", "parent-child", "discovered-from"):
            raise ValueError("Invalid dep_type")

        dep: Dependency | None = None

        def do_add_dep(index: IssueIndex) -> Dependency:
            nonlocal dep
            if not index.get_issue(from_id):
                raise ValueError(f"Issue not found: {from_id}")
            if not index.get_issue(to_id):
                raise ValueError(f"Issue not found: {to_id}")

            if detect_cycle(index, from_id, to_id):
                raise ValueError("Dependency would create a cycle")

            dep = Dependency(
                from_id=from_id,
                to_id=to_id,
                dep_type=dep_type,
                created_at=datetime.now(),
            )

            index.add_dependency(dep)
            return dep

        # Use separate lock scope for dependencies
        with self._acquire_lock():
            index = self._load_fresh()
            result = do_add_dep(index)
            self._save_dependencies(index)

        self._emit_event(
            from_id,
            "dependency_added",
            {"from_id": from_id, "to_id": to_id, "dep_type": dep_type},
        )

        return result

    def remove_dependency(self, from_id: str, to_id: str) -> None:
        """Remove a dependency.

        Args:
            from_id: Blocked issue ID
            to_id: Blocking issue ID

        Raises:
            ValueError: If dependency not found
        """

        def do_remove_dep(index: IssueIndex) -> None:
            if (from_id, to_id) not in index.dependencies:
                raise ValueError(f"Dependency not found: {from_id} -> {to_id}")

            index.remove_dependency(from_id, to_id)

        with self._acquire_lock():
            index = self._load_fresh()
            do_remove_dep(index)
            self._save_dependencies(index)

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
        with self._acquire_lock():
            index = self._load_fresh()
            blocker_ids = index.get_blockers(issue_id)
            result = []
            for bid in blocker_ids:
                issue = index.get_issue(bid)
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
        with self._acquire_lock():
            index = self._load_fresh()
            dependent_ids = index.get_dependents(issue_id)
            result = []
            for did in dependent_ids:
                issue = index.get_issue(did)
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
        with self._acquire_lock():
            index = self._load_fresh()
            return get_ready_issues(index, limit)

    def get_blocked_issues(self) -> list[tuple[Issue, list[Issue]]]:
        """Get blocked issues with their blockers.

        Returns:
            List of (blocked_issue, blocker_issues) tuples
        """
        with self._acquire_lock():
            index = self._load_fresh()
            return get_blocked_issues(index)

    def get_issue_events(self, issue_id: str) -> list[IssueEvent]:
        """Get all events for an issue.

        Args:
            issue_id: Issue ID

        Returns:
            List of events for this issue
        """
        all_events = self.storage.load_events()
        return [e for e in all_events if e.issue_id == issue_id]

    def get_issue_sessions(self, issue_id: str) -> dict[str, Any]:
        """Get all Amplifier sessions that have touched an issue.

        This enables session linking - finding which sessions created, updated,
        claimed, or closed an issue, so users can resume sessions for follow-up
        questions with full context.

        Args:
            issue_id: Issue ID

        Returns:
            Dict with:
                - issue_id: The issue ID
                - linked_sessions: List of unique session IDs
                - session_count: Number of sessions
                - events_by_session: Dict mapping session_id to list of event types
                - hint: How to resume a session

        Raises:
            ValueError: If issue not found
        """
        with self._acquire_lock():
            index = self._load_fresh()
            if not index.get_issue(issue_id):
                raise ValueError(f"Issue not found: {issue_id}")

        events = self.get_issue_events(issue_id)

        # Collect sessions and their event types
        sessions: dict[str, list[str]] = {}
        for event in events:
            if event.session_id:
                if event.session_id not in sessions:
                    sessions[event.session_id] = []
                sessions[event.session_id].append(event.event_type)

        return {
            "issue_id": issue_id,
            "linked_sessions": sorted(sessions.keys()),
            "session_count": len(sessions),
            "events_by_session": sessions,
            "hint": "Use 'amplifier session resume <session_id>' to revive context for follow-up questions",
        }

    def emit_session_ended(self, issue_id: str) -> None:
        """Emit a session_ended event for an issue.

        Called when an Amplifier session ends with an issue still in_progress.
        This provides continuity by recording session boundaries.

        Args:
            issue_id: Issue ID
        """
        with self._acquire_lock():
            index = self._load_fresh()
            if not index.get_issue(issue_id):
                return  # Silently ignore if issue doesn't exist

        self._emit_event(issue_id, "session_ended", {"reason": "session terminated"})
