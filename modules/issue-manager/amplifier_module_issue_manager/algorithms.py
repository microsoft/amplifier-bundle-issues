"""Scheduling algorithms for issue management."""

import networkx as nx

from .index import IssueIndex
from .models import Issue


def get_ready_issues(
    index: IssueIndex,
    limit: int | None = None,
) -> list[Issue]:
    """Get issues ready to work (leaf-based scheduling).

    An issue is ready if:
    - Status is 'open' or 'in_progress'
    - Has no open blockers

    Results are sorted by priority (0=highest).

    Args:
        index: Issue index
        limit: Maximum number of issues to return

    Returns:
        List of ready issues sorted by priority
    """
    ready = []

    for issue in index.issues.values():
        if issue.status not in ("open", "in_progress"):
            continue

        blockers = index.get_blockers(issue.id)
        has_open_blocker = False

        for blocker_id in blockers:
            blocker = index.get_issue(blocker_id)
            if blocker and blocker.status != "closed":
                has_open_blocker = True
                break

        if not has_open_blocker:
            ready.append(issue)

    ready.sort(key=lambda i: i.priority)

    if limit is not None:
        return ready[:limit]
    return ready


def get_blocked_issues(index: IssueIndex) -> list[tuple[Issue, list[Issue]]]:
    """Get issues that are blocked with their blockers.

    Args:
        index: Issue index

    Returns:
        List of (blocked_issue, blocker_issues) tuples
    """
    blocked = []

    for issue in index.issues.values():
        if issue.status == "closed":
            continue

        blocker_ids = index.get_blockers(issue.id)
        open_blockers = []

        for blocker_id in blocker_ids:
            blocker = index.get_issue(blocker_id)
            if blocker and blocker.status != "closed":
                open_blockers.append(blocker)

        if open_blockers:
            blocked.append((issue, open_blockers))

    return blocked


def detect_cycle(index: IssueIndex, from_id: str, to_id: str) -> bool:
    """Detect if adding a dependency would create a cycle.

    Args:
        index: Issue index
        from_id: Blocked issue ID
        to_id: Blocking issue ID

    Returns:
        True if cycle would be created, False otherwise
    """
    graph = nx.DiGraph()

    for dep in index.get_all_dependencies():
        graph.add_edge(dep.from_id, dep.to_id)

    graph.add_edge(from_id, to_id)

    try:
        nx.find_cycle(graph)
        return True
    except nx.NetworkXNoCycle:
        return False
