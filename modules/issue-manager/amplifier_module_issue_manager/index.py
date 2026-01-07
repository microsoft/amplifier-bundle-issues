"""In-memory index for fast issue lookups."""

from .models import Dependency
from .models import Issue


class IssueIndex:
    """In-memory index for issues and dependencies.

    Provides fast lookups by ID, status, priority, and relationships.
    """

    def __init__(self):
        """Initialize empty index."""
        self.issues: dict[str, Issue] = {}
        self.dependencies: dict[tuple[str, str], Dependency] = {}
        self.blockers: dict[str, set[str]] = {}
        self.dependents: dict[str, set[str]] = {}

    def add_issue(self, issue: Issue) -> None:
        """Add issue to index.

        Args:
            issue: Issue to add
        """
        self.issues[issue.id] = issue

    def remove_issue(self, issue_id: str) -> None:
        """Remove issue from index.

        Args:
            issue_id: ID of issue to remove
        """
        self.issues.pop(issue_id, None)

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get issue by ID.

        Args:
            issue_id: Issue ID

        Returns:
            Issue if found, None otherwise
        """
        return self.issues.get(issue_id)

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
        result = list(self.issues.values())

        if status is not None:
            result = [i for i in result if i.status == status]
        if priority is not None:
            result = [i for i in result if i.priority == priority]
        if issue_type is not None:
            result = [i for i in result if i.issue_type == issue_type]
        if assignee is not None:
            result = [i for i in result if i.assignee == assignee]

        return result

    def add_dependency(self, dep: Dependency) -> None:
        """Add dependency to index.

        Args:
            dep: Dependency to add
        """
        key = (dep.from_id, dep.to_id)
        self.dependencies[key] = dep

        if dep.from_id not in self.blockers:
            self.blockers[dep.from_id] = set()
        self.blockers[dep.from_id].add(dep.to_id)

        if dep.to_id not in self.dependents:
            self.dependents[dep.to_id] = set()
        self.dependents[dep.to_id].add(dep.from_id)

    def remove_dependency(self, from_id: str, to_id: str) -> None:
        """Remove dependency from index.

        Args:
            from_id: Blocked issue ID
            to_id: Blocking issue ID
        """
        key = (from_id, to_id)
        self.dependencies.pop(key, None)

        if from_id in self.blockers:
            self.blockers[from_id].discard(to_id)
            if not self.blockers[from_id]:
                del self.blockers[from_id]

        if to_id in self.dependents:
            self.dependents[to_id].discard(from_id)
            if not self.dependents[to_id]:
                del self.dependents[to_id]

    def get_blockers(self, issue_id: str) -> set[str]:
        """Get all issues blocking this issue.

        Args:
            issue_id: Issue ID

        Returns:
            Set of blocking issue IDs
        """
        return self.blockers.get(issue_id, set()).copy()

    def get_dependents(self, issue_id: str) -> set[str]:
        """Get all issues dependent on this issue.

        Args:
            issue_id: Issue ID

        Returns:
            Set of dependent issue IDs
        """
        return self.dependents.get(issue_id, set()).copy()

    def get_all_dependencies(self) -> list[Dependency]:
        """Get all dependencies.

        Returns:
            List of all dependencies
        """
        return list(self.dependencies.values())

    def clear(self) -> None:
        """Clear the index."""
        self.issues.clear()
        self.dependencies.clear()
        self.blockers.clear()
        self.dependents.clear()
