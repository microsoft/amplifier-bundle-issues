"""Tests for dependency management and cycle detection."""

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


def test_add_dependency(manager):
    """Test adding a dependency."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    dep = manager.add_dependency(issue1.id, issue2.id, dep_type="blocks")

    assert dep.from_id == issue1.id
    assert dep.to_id == issue2.id
    assert dep.dep_type == "blocks"


def test_add_dependency_nonexistent_issue(manager):
    """Test adding dependency with nonexistent issue."""
    issue = manager.create_issue(title="Issue")

    with pytest.raises(ValueError, match="Issue not found"):
        manager.add_dependency(issue.id, "nonexistent")

    with pytest.raises(ValueError, match="Issue not found"):
        manager.add_dependency("nonexistent", issue.id)


def test_add_dependency_invalid_type(manager):
    """Test adding dependency with invalid type."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    with pytest.raises(ValueError, match="Invalid dep_type"):
        manager.add_dependency(issue1.id, issue2.id, dep_type="invalid")


def test_detect_simple_cycle(manager):
    """Test cycle detection for simple cycle."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    manager.add_dependency(issue1.id, issue2.id)

    with pytest.raises(ValueError, match="cycle"):
        manager.add_dependency(issue2.id, issue1.id)


def test_detect_complex_cycle(manager):
    """Test cycle detection for complex cycle."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")
    issue3 = manager.create_issue(title="Issue 3")

    manager.add_dependency(issue1.id, issue2.id)
    manager.add_dependency(issue2.id, issue3.id)

    with pytest.raises(ValueError, match="cycle"):
        manager.add_dependency(issue3.id, issue1.id)


def test_remove_dependency(manager):
    """Test removing a dependency."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    manager.add_dependency(issue1.id, issue2.id)
    manager.remove_dependency(issue1.id, issue2.id)

    deps = manager.get_dependencies(issue1.id)
    assert len(deps) == 0


def test_remove_nonexistent_dependency(manager):
    """Test removing nonexistent dependency."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    with pytest.raises(ValueError, match="Dependency not found"):
        manager.remove_dependency(issue1.id, issue2.id)


def test_get_dependencies(manager):
    """Test getting issue dependencies."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")
    issue3 = manager.create_issue(title="Issue 3")

    manager.add_dependency(issue1.id, issue2.id)
    manager.add_dependency(issue1.id, issue3.id)

    deps = manager.get_dependencies(issue1.id)
    assert len(deps) == 2
    dep_ids = {d.id for d in deps}
    assert issue2.id in dep_ids
    assert issue3.id in dep_ids


def test_get_dependents(manager):
    """Test getting issue dependents."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")
    issue3 = manager.create_issue(title="Issue 3")

    manager.add_dependency(issue2.id, issue1.id)
    manager.add_dependency(issue3.id, issue1.id)

    dependents = manager.get_dependents(issue1.id)
    assert len(dependents) == 2
    dep_ids = {d.id for d in dependents}
    assert issue2.id in dep_ids
    assert issue3.id in dep_ids


def test_dependency_persistence(temp_dir):
    """Test dependencies persist across manager instances."""
    manager1 = IssueManager(temp_dir)
    issue1 = manager1.create_issue(title="Issue 1")
    issue2 = manager1.create_issue(title="Issue 2")
    manager1.add_dependency(issue1.id, issue2.id)

    manager2 = IssueManager(temp_dir)
    deps = manager2.get_dependencies(issue1.id)

    assert len(deps) == 1
    assert deps[0].id == issue2.id
