"""Tests for session linking functionality."""

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
def manager_with_session(temp_dir):
    """Create IssueManager with session_id."""
    return IssueManager(temp_dir, actor="test", session_id="session-abc123")


@pytest.fixture
def manager_no_session(temp_dir):
    """Create IssueManager without session_id."""
    return IssueManager(temp_dir, actor="test")


def test_session_id_in_events(manager_with_session):
    """Test that session_id is recorded in events."""
    issue = manager_with_session.create_issue(title="Test Issue")
    events = manager_with_session.get_issue_events(issue.id)
    
    assert len(events) == 1
    assert events[0].session_id == "session-abc123"
    assert events[0].event_type == "created"


def test_session_id_none_when_not_set(manager_no_session):
    """Test that session_id is None when not configured."""
    issue = manager_no_session.create_issue(title="Test Issue")
    events = manager_no_session.get_issue_events(issue.id)
    
    assert len(events) == 1
    assert events[0].session_id is None


def test_get_issue_sessions_single_session(manager_with_session):
    """Test get_issue_sessions with single session."""
    issue = manager_with_session.create_issue(title="Test Issue")
    manager_with_session.update_issue(issue.id, status="in_progress")
    
    result = manager_with_session.get_issue_sessions(issue.id)
    
    assert result["issue_id"] == issue.id
    assert result["linked_sessions"] == ["session-abc123"]
    assert result["session_count"] == 1
    assert "session-abc123" in result["events_by_session"]
    assert "created" in result["events_by_session"]["session-abc123"]
    assert "updated" in result["events_by_session"]["session-abc123"]


def test_get_issue_sessions_multiple_sessions(temp_dir):
    """Test get_issue_sessions with multiple sessions."""
    # First session creates the issue
    manager1 = IssueManager(temp_dir, actor="test", session_id="session-111")
    issue = manager1.create_issue(title="Test Issue")
    
    # Second session updates the issue
    manager2 = IssueManager(temp_dir, actor="test", session_id="session-222")
    manager2.update_issue(issue.id, status="in_progress")
    
    # Third session closes the issue
    manager3 = IssueManager(temp_dir, actor="test", session_id="session-333")
    manager3.close_issue(issue.id)
    
    result = manager3.get_issue_sessions(issue.id)
    
    assert result["session_count"] == 3
    assert sorted(result["linked_sessions"]) == ["session-111", "session-222", "session-333"]
    assert "created" in result["events_by_session"]["session-111"]
    assert "updated" in result["events_by_session"]["session-222"]
    assert "closed" in result["events_by_session"]["session-333"]


def test_get_issue_sessions_nonexistent_issue(manager_with_session):
    """Test get_issue_sessions with nonexistent issue."""
    with pytest.raises(ValueError, match="Issue not found"):
        manager_with_session.get_issue_sessions("nonexistent-id")


def test_get_issue_sessions_no_sessions(manager_no_session):
    """Test get_issue_sessions when no sessions recorded."""
    issue = manager_no_session.create_issue(title="Test Issue")
    
    result = manager_no_session.get_issue_sessions(issue.id)
    
    assert result["session_count"] == 0
    assert result["linked_sessions"] == []


def test_emit_session_ended(manager_with_session):
    """Test emitting session_ended event."""
    issue = manager_with_session.create_issue(title="Test Issue")
    manager_with_session.update_issue(issue.id, status="in_progress")
    
    manager_with_session.emit_session_ended(issue.id)
    
    events = manager_with_session.get_issue_events(issue.id)
    session_ended_events = [e for e in events if e.event_type == "session_ended"]
    
    assert len(session_ended_events) == 1
    assert session_ended_events[0].session_id == "session-abc123"


def test_emit_session_ended_nonexistent_issue(manager_with_session):
    """Test emit_session_ended silently ignores nonexistent issues."""
    # Should not raise - silently ignores
    manager_with_session.emit_session_ended("nonexistent-id")


def test_session_linking_hint(manager_with_session):
    """Test that get_issue_sessions returns helpful hint."""
    issue = manager_with_session.create_issue(title="Test Issue")
    
    result = manager_with_session.get_issue_sessions(issue.id)
    
    assert "hint" in result
    assert "amplifier session resume" in result["hint"]
