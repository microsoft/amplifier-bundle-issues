"""Tests for JSONL storage layer."""

import tempfile
from pathlib import Path

import pytest
from amplifier_module_issue_manager import IssueManager


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_dir):
    """Create issue manager for tests."""
    return IssueManager(temp_dir)


def test_storage_creates_files(temp_dir):
    """Test that storage creates JSONL files."""
    manager = IssueManager(temp_dir)
    manager.create_issue(title="Test")

    assert (temp_dir / "issues.jsonl").exists()
    assert (temp_dir / "events.jsonl").exists()


def test_storage_persistence(temp_dir):
    """Test that data persists across instances."""
    manager1 = IssueManager(temp_dir)
    issue = manager1.create_issue(title="Persistent")

    manager2 = IssueManager(temp_dir)
    retrieved = manager2.get_issue(issue.id)

    assert retrieved is not None
    assert retrieved.title == "Persistent"


def test_storage_handles_empty_files(temp_dir):
    """Test that storage handles empty files gracefully."""
    (temp_dir / "issues.jsonl").touch()
    (temp_dir / "dependencies.jsonl").touch()
    (temp_dir / "events.jsonl").touch()

    manager = IssueManager(temp_dir)
    issues = manager.list_issues()

    assert len(issues) == 0


def test_storage_handles_missing_files(temp_dir):
    """Test that storage handles missing files gracefully."""
    manager = IssueManager(temp_dir)
    issues = manager.list_issues()

    assert len(issues) == 0


def test_event_storage(temp_dir):
    """Test that events are stored."""
    manager = IssueManager(temp_dir)
    issue = manager.create_issue(title="Test")
    manager.update_issue(issue.id, title="Updated")

    events = manager.get_issue_events(issue.id)

    assert len(events) >= 2
    assert events[0].event_type == "created"
    assert events[1].event_type == "updated"


def test_dependency_storage(temp_dir):
    """Test that dependencies persist."""
    manager1 = IssueManager(temp_dir)
    issue1 = manager1.create_issue(title="Issue 1")
    issue2 = manager1.create_issue(title="Issue 2")
    manager1.add_dependency(issue1.id, issue2.id)

    manager2 = IssueManager(temp_dir)
    deps = manager2.get_dependencies(issue1.id)

    assert len(deps) == 1
    assert deps[0].id == issue2.id


def test_full_reload(temp_dir):
    """Test full reload of all data."""
    manager1 = IssueManager(temp_dir)

    issue1 = manager1.create_issue(title="Issue 1", priority=1)
    issue2 = manager1.create_issue(title="Issue 2", priority=2)
    issue3 = manager1.create_issue(title="Issue 3", priority=3)

    manager1.add_dependency(issue1.id, issue2.id)
    manager1.add_dependency(issue2.id, issue3.id)
    manager1.update_issue(issue1.id, status="in_progress")
    manager1.close_issue(issue3.id)

    manager2 = IssueManager(temp_dir)

    all_issues = manager2.list_issues()
    assert len(all_issues) == 3

    ready = manager2.get_ready_issues()
    assert len(ready) == 1

    blocked = manager2.get_blocked_issues()
    assert len(blocked) == 1
