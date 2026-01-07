"""Tests for IssueManager CRUD operations."""

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


def test_create_issue(manager):
    """Test issue creation."""
    issue = manager.create_issue(
        title="Test issue",
        description="Test description",
        priority=1,
        issue_type="feature",
    )

    assert issue.id
    assert issue.title == "Test issue"
    assert issue.description == "Test description"
    assert issue.priority == 1
    assert issue.issue_type == "feature"
    assert issue.status == "open"


def test_get_issue(manager):
    """Test getting an issue."""
    issue = manager.create_issue(title="Test issue")
    retrieved = manager.get_issue(issue.id)

    assert retrieved is not None
    assert retrieved.id == issue.id
    assert retrieved.title == issue.title


def test_get_nonexistent_issue(manager):
    """Test getting nonexistent issue returns None."""
    assert manager.get_issue("nonexistent") is None


def test_update_issue(manager):
    """Test updating an issue."""
    issue = manager.create_issue(title="Original")
    updated = manager.update_issue(
        issue.id,
        title="Updated",
        status="in_progress",
        priority=3,
    )

    assert updated.title == "Updated"
    assert updated.status == "in_progress"
    assert updated.priority == 3


def test_update_nonexistent_issue(manager):
    """Test updating nonexistent issue raises error."""
    with pytest.raises(ValueError, match="Issue not found"):
        manager.update_issue("nonexistent", title="Test")


def test_update_invalid_status(manager):
    """Test updating with invalid status raises error."""
    issue = manager.create_issue(title="Test")
    with pytest.raises(ValueError, match="Invalid status"):
        manager.update_issue(issue.id, status="invalid")


def test_update_invalid_priority(manager):
    """Test updating with invalid priority raises error."""
    issue = manager.create_issue(title="Test")
    with pytest.raises(ValueError, match="Priority must be 0-4"):
        manager.update_issue(issue.id, priority=5)


def test_close_issue(manager):
    """Test closing an issue."""
    issue = manager.create_issue(title="Test")
    closed = manager.close_issue(issue.id, reason="Done")

    assert closed.status == "closed"
    assert closed.closed_at is not None


def test_close_nonexistent_issue(manager):
    """Test closing nonexistent issue raises error."""
    with pytest.raises(ValueError, match="Issue not found"):
        manager.close_issue("nonexistent")


def test_list_issues(manager):
    """Test listing issues."""
    issue1 = manager.create_issue(title="Issue 1", priority=1, issue_type="bug")
    issue2 = manager.create_issue(title="Issue 2", priority=2, issue_type="feature")
    issue3 = manager.create_issue(title="Issue 3")
    manager.close_issue(issue3.id)

    all_issues = manager.list_issues()
    assert len(all_issues) >= 3

    priority_issues = manager.list_issues(priority=1)
    assert len(priority_issues) == 1
    assert priority_issues[0].id == issue1.id

    type_issues = manager.list_issues(issue_type="feature")
    assert len(type_issues) == 1
    assert type_issues[0].id == issue2.id


def test_create_invalid_priority(manager):
    """Test creating issue with invalid priority."""
    with pytest.raises(ValueError, match="Priority must be 0-4"):
        manager.create_issue(title="Test", priority=10)


def test_create_invalid_type(manager):
    """Test creating issue with invalid type."""
    with pytest.raises(ValueError, match="Invalid issue_type"):
        manager.create_issue(title="Test", issue_type="invalid")


def test_persistence(temp_dir):
    """Test issues persist across manager instances."""
    manager1 = IssueManager(temp_dir)
    issue = manager1.create_issue(title="Persistent issue")

    manager2 = IssueManager(temp_dir)
    retrieved = manager2.get_issue(issue.id)

    assert retrieved is not None
    assert retrieved.title == "Persistent issue"


def test_update_metadata(manager):
    """Test updating issue metadata."""
    issue = manager.create_issue(title="Test", metadata={"key1": "value1"})
    updated = manager.update_issue(issue.id, metadata={"key2": "value2"})

    assert updated.metadata["key1"] == "value1"
    assert updated.metadata["key2"] == "value2"
