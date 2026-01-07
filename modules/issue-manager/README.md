# Issue Manager Module

Issue management module for Amplifier with dependencies, priority-based scheduling, and event tracking.

## Purpose

Provides a simple, text-first issue management system for tracking work with:

- CRUD operations for issues
- Dependency management with cycle detection
- Priority-based scheduling (leaf-based algorithm)
- Event tracking for audit and observability
- JSONL storage with defensive file I/O

## Installation

```bash
cd amplifier-module-issue-manager
uv pip install -e .
```

## Module Contract

### Public Interface

```python
from amplifier_module_issue_manager import IssueManager, Issue, Dependency, IssueEvent

# Create manager
manager = IssueManager(data_dir=Path(".amplifier/issues"))

# Issue CRUD
issue = manager.create_issue(title="Implement feature", priority=1, issue_type="feature")
issue = manager.get_issue(issue_id)
issue = manager.update_issue(issue_id, status="in_progress")
issue = manager.close_issue(issue_id, reason="Completed")
issues = manager.list_issues(status="open", priority=1)

# Dependency management
dep = manager.add_dependency(from_id, to_id, dep_type="blocks")
manager.remove_dependency(from_id, to_id)
blockers = manager.get_dependencies(issue_id)
dependents = manager.get_dependents(issue_id)

# Scheduling
ready = manager.get_ready_issues(limit=10)
blocked = manager.get_blocked_issues()

# Events
events = manager.get_issue_events(issue_id)
```

### Data Models

**Issue:**
```python
@dataclass
class Issue:
    id: str
    title: str
    description: str
    status: str  # open|in_progress|blocked|closed
    priority: int  # 0-4 (0=highest)
    issue_type: str  # bug|feature|task|epic|chore
    assignee: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    parent_id: str | None
    discovered_from: str | None
    blocking_notes: str | None
    metadata: dict[str, Any]
```

**Dependency:**
```python
@dataclass
class Dependency:
    from_id: str  # Blocked issue
    to_id: str    # Blocking issue
    dep_type: str  # blocks|related|parent-child|discovered-from
    created_at: datetime
```

**IssueEvent:**
```python
@dataclass
class IssueEvent:
    id: str
    issue_id: str
    event_type: str  # created|updated|closed|blocked|unblocked
    actor: str
    changes: dict[str, Any]
    timestamp: datetime
```

## Storage Format

All data stored as JSONL (JSON Lines) for human readability and inspectability:

- `issues.jsonl` - One issue per line
- `dependencies.jsonl` - One dependency per line
- `events.jsonl` - One event per line (append-only)

Example issue:
```json
{"id": "uuid", "title": "Fix bug", "status": "open", "priority": 1, ...}
```

## Scheduling Algorithm

Uses **leaf-based scheduling** - simple and efficient:

1. Find all issues with status `open` or `in_progress`
2. Filter out issues that have open blockers
3. Sort by priority (0=highest)
4. Return top N issues

Time complexity: O(n) for n issues
Memory usage: O(n) for index

Much simpler than topological sort while providing the same practical results.

## Cycle Detection

Uses NetworkX to detect dependency cycles before adding edges. Raises `ValueError` if cycle would be created.

## Defensive File I/O

Implements retry logic with exponential backoff for cloud-synced filesystems (OneDrive, Dropbox, etc.):

- Max 3 retries
- Exponential backoff (0.1s, 0.2s, 0.4s)
- Informative warnings on first retry
- Works around OSError errno 5 on Windows WSL2

See `DISCOVERIES.md` for details.

## Configuration

Mount plan configuration:

```toml
[issue_manager]
module = "amplifier-module-issue-manager"
config = {
    data_dir = ".amplifier/issues",
    auto_create_dir = true,
    actor = "system"
}
```

## Events Emitted

- `issue:created` - Issue created
- `issue:updated` - Issue updated
- `issue:closed` - Issue closed
- `issue:dependency_added` - Dependency added
- `issue:dependency_removed` - Dependency removed

## Error Handling

| Error | Condition | Recovery |
|-------|-----------|----------|
| `ValueError` | Invalid input (priority, status, type) | Fix input and retry |
| `ValueError` | Issue not found | Check issue ID |
| `ValueError` | Cycle would be created | Remove conflicting dependency |
| `OSError` | File I/O error | Auto-retry with backoff |

## Performance Characteristics

- Load time: < 100ms for 1000 issues (acceptance criteria)
- Memory usage: O(n) for n issues
- Ready work calculation: O(n) per call
- Cycle detection: O(V+E) where V=issues, E=dependencies

## Testing

```bash
cd amplifier-module-issue-manager
uv pip install -e ".[dev]"
uv run pytest tests/
```

Test coverage:
- `test_manager.py` - CRUD operations
- `test_dependencies.py` - Dependency management and cycle detection
- `test_ready_work.py` - Leaf-based scheduling
- `test_storage.py` - JSONL persistence

## Regeneration Specification

This module can be regenerated from this specification alone.

Key invariants:
- Public interface (IssueManager API)
- Data models (Issue, Dependency, IssueEvent)
- Storage format (JSONL)
- Event types
- Error conditions

Internal implementation (index structure, algorithm details) can be changed without breaking contract.

## Philosophy Compliance

✅ **Ruthless simplicity** - No unnecessary abstractions, simple data structures
✅ **Text-first** - JSONL storage, human-readable and diffable
✅ **Fail fast** - Meaningful errors with clear messages
✅ **Event-driven** - Canonical events for observability
✅ **Modular** - Self-contained, regeneratable from spec
✅ **Defensive** - Retry logic for cloud sync issues

## Contributing

See `../AGENTS.md` for contribution guidelines.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
