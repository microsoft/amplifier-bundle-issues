"""Data models for issue management."""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any


@dataclass
class Issue:
    """Issue data model.

    Represents a work item with status, priority, and relationships.
    """

    id: str
    title: str
    description: str
    status: str  # open|in_progress|blocked|closed
    priority: int  # 0-4 (0=highest)
    issue_type: str  # bug|feature|task|epic|chore
    assignee: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    parent_id: str | None = None
    discovered_from: str | None = None
    blocking_notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "issue_type": self.issue_type,
            "assignee": self.assignee,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "parent_id": self.parent_id,
            "discovered_from": self.discovered_from,
            "blocking_notes": self.blocking_notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Issue":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            status=data["status"],
            priority=data["priority"],
            issue_type=data["issue_type"],
            assignee=data.get("assignee"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            parent_id=data.get("parent_id"),
            discovered_from=data.get("discovered_from"),
            blocking_notes=data.get("blocking_notes"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Dependency:
    """Dependency relationship between issues.

    Represents a directional relationship where from_id is blocked by to_id.
    """

    from_id: str  # Blocked issue
    to_id: str  # Blocking issue
    dep_type: str  # blocks|related|parent-child|discovered-from
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "dep_type": self.dep_type,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dependency":
        """Create from dictionary."""
        return cls(
            from_id=data["from_id"],
            to_id=data["to_id"],
            dep_type=data["dep_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class IssueEvent:
    """Event record for issue changes.

    Tracks all modifications to issues for audit and observability.
    """

    id: str
    issue_id: str
    event_type: str  # created|updated|closed|blocked|unblocked
    actor: str
    changes: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "changes": self.changes,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueEvent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            issue_id=data["issue_id"],
            event_type=data["event_type"],
            actor=data["actor"],
            changes=data["changes"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
