"""Tests for leaf-based scheduling algorithm."""

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


def test_get_ready_issues_no_dependencies(manager):
    """Test getting ready issues when there are no dependencies."""
    issue1 = manager.create_issue(title="Issue 1", priority=2)
    issue2 = manager.create_issue(title="Issue 2", priority=1)
    issue3 = manager.create_issue(title="Issue 3", priority=3)

    ready = manager.get_ready_issues()

    assert len(ready) == 3
    assert ready[0].id == issue2.id
    assert ready[1].id == issue1.id
    assert ready[2].id == issue3.id


def test_get_ready_issues_with_dependencies(manager):
    """Test getting ready issues with dependencies."""
    issue1 = manager.create_issue(title="Issue 1", priority=1)
    issue2 = manager.create_issue(title="Issue 2", priority=1)
    issue3 = manager.create_issue(title="Issue 3", priority=1)

    manager.add_dependency(issue1.id, issue2.id)
    manager.add_dependency(issue2.id, issue3.id)

    ready = manager.get_ready_issues()

    assert len(ready) == 1
    assert ready[0].id == issue3.id


def test_get_ready_issues_closed_blocker(manager):
    """Test that closed blockers don't block issues."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    manager.add_dependency(issue1.id, issue2.id)
    manager.close_issue(issue2.id)

    ready = manager.get_ready_issues()

    assert len(ready) == 1
    assert ready[0].id == issue1.id


def test_get_ready_issues_limit(manager):
    """Test limiting number of ready issues."""
    manager.create_issue(title="Issue 1", priority=1)
    manager.create_issue(title="Issue 2", priority=2)
    manager.create_issue(title="Issue 3", priority=3)

    ready = manager.get_ready_issues(limit=2)

    assert len(ready) == 2


def test_get_ready_issues_excludes_closed(manager):
    """Test that closed issues are not included in ready issues."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")
    manager.close_issue(issue1.id)

    ready = manager.get_ready_issues()

    assert len(ready) == 1
    assert ready[0].id == issue2.id


def test_get_blocked_issues(manager):
    """Test getting blocked issues."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")
    issue3 = manager.create_issue(title="Issue 3")

    manager.add_dependency(issue1.id, issue2.id)
    manager.add_dependency(issue1.id, issue3.id)

    blocked = manager.get_blocked_issues()

    assert len(blocked) == 1
    blocked_issue, blockers = blocked[0]
    assert blocked_issue.id == issue1.id
    assert len(blockers) == 2
    blocker_ids = {b.id for b in blockers}
    assert issue2.id in blocker_ids
    assert issue3.id in blocker_ids


def test_get_blocked_issues_closed_blocker(manager):
    """Test that closed blockers don't count."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    manager.add_dependency(issue1.id, issue2.id)
    manager.close_issue(issue2.id)

    blocked = manager.get_blocked_issues()

    assert len(blocked) == 0


def test_get_blocked_issues_excludes_closed(manager):
    """Test that closed issues are not included in blocked issues."""
    issue1 = manager.create_issue(title="Issue 1")
    issue2 = manager.create_issue(title="Issue 2")

    manager.add_dependency(issue1.id, issue2.id)
    manager.close_issue(issue1.id)

    blocked = manager.get_blocked_issues()

    assert len(blocked) == 0


def test_ready_issues_priority_sorting(manager):
    """Test that ready issues are sorted by priority."""
    issue_p4 = manager.create_issue(title="Priority 4", priority=4)
    issue_p0 = manager.create_issue(title="Priority 0", priority=0)
    issue_p2 = manager.create_issue(title="Priority 2", priority=2)
    issue_p1 = manager.create_issue(title="Priority 1", priority=1)

    ready = manager.get_ready_issues()

    assert ready[0].id == issue_p0.id
    assert ready[1].id == issue_p1.id
    assert ready[2].id == issue_p2.id
    assert ready[3].id == issue_p4.id


def test_complex_dependency_graph(manager):
    """Test ready issues with complex dependency graph."""
    issue1 = manager.create_issue(title="Issue 1", priority=1)
    issue2 = manager.create_issue(title="Issue 2", priority=2)
    issue3 = manager.create_issue(title="Issue 3", priority=3)
    issue4 = manager.create_issue(title="Issue 4", priority=4)
    issue5 = manager.create_issue(title="Issue 5", priority=4)

    manager.add_dependency(issue1.id, issue3.id)
    manager.add_dependency(issue2.id, issue3.id)
    manager.add_dependency(issue3.id, issue5.id)

    ready = manager.get_ready_issues()

    assert len(ready) == 2
    assert ready[0].id == issue4.id
    assert ready[1].id == issue5.id
