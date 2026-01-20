"""Tests for GitHub sync functionality."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from amplifier_module_tool_issue.tool import IssueTool


@pytest.fixture
def mock_coordinator():
    """Mock coordinator for testing."""
    coordinator = MagicMock()
    return coordinator


@pytest.fixture
def mock_issue_manager():
    """Mock issue manager with test issues."""
    manager = MagicMock()

    # Create mock issues
    issue1 = MagicMock()
    issue1.issue_id = "issue_1"
    issue1.title = "Test Issue 1"
    issue1.description = "Description 1"
    issue1.status = "open"
    issue1.priority = 2
    issue1.assignee = "testuser"
    issue1.session_id = "session_123"
    issue1.created_at = "2026-01-20T10:00:00Z"
    issue1.metadata = {"area": "core"}

    issue2 = MagicMock()
    issue2.issue_id = "issue_2"
    issue2.title = "Test Issue 2"
    issue2.description = "Description 2"
    issue2.status = "in_progress"
    issue2.priority = 1
    issue2.assignee = None
    issue2.session_id = "session_456"
    issue2.created_at = "2026-01-20T11:00:00Z"
    issue2.metadata = None

    # Already synced issue
    issue3 = MagicMock()
    issue3.issue_id = "issue_3"
    issue3.title = "Already Synced"
    issue3.description = "Already on GitHub"
    issue3.status = "open"
    issue3.priority = 2
    issue3.assignee = "testuser"
    issue3.session_id = "session_789"
    issue3.created_at = "2026-01-20T12:00:00Z"
    issue3.metadata = {"github_issue_number": 42, "github_repo": "test/repo"}

    # Closed issue
    issue4 = MagicMock()
    issue4.issue_id = "issue_4"
    issue4.title = "Closed Issue"
    issue4.description = "This is closed"
    issue4.status = "closed"
    issue4.priority = 2
    issue4.assignee = "testuser"
    issue4.session_id = "session_999"
    issue4.created_at = "2026-01-20T09:00:00Z"
    issue4.metadata = None

    manager.list_issues.return_value = [issue1, issue2, issue3, issue4]
    manager.update_issue = MagicMock()

    return manager


@pytest.fixture
def issue_tool(mock_coordinator, mock_issue_manager, tmp_path):
    """Create IssueTool instance with mocked dependencies."""
    tool = IssueTool(
        coordinator=mock_coordinator,
        data_dir=tmp_path / "issues",
        actor="test",
        session_id="test_session",
    )
    tool.issue_manager = mock_issue_manager
    return tool


class TestSyncToGitHub:
    """Tests for sync_to_github operation."""

    @pytest.mark.asyncio
    async def test_sync_skips_already_synced_issues(
        self, issue_tool, mock_issue_manager
    ):
        """Test that already synced issues are skipped."""
        with patch.object(issue_tool, "_create_github_issue"):
            result = await issue_tool._sync_to_github({"repo": "test/repo"})

            # Should not create GitHub issue for issue_3 (already synced)
            assert result["skipped_count"] == 2  # issue_3 (synced) + issue_4 (closed)
            assert result["synced_count"] == 2  # issue_1 + issue_2

    @pytest.mark.asyncio
    async def test_sync_skips_closed_issues_by_default(
        self, issue_tool, mock_issue_manager
    ):
        """Test that closed issues are skipped unless include_closed=True."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            mock_create.return_value = 100

            result = await issue_tool._sync_to_github({"repo": "test/repo"})

            # Should skip closed issue (issue_4)
            assert result["synced_count"] == 2  # Only open/in-progress
            assert result["skipped_count"] == 2  # issue_3 (synced) + issue_4 (closed)

    @pytest.mark.asyncio
    async def test_sync_includes_closed_when_requested(
        self, issue_tool, mock_issue_manager
    ):
        """Test that closed issues are synced when include_closed=True."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            mock_create.return_value = 100

            result = await issue_tool._sync_to_github(
                {"repo": "test/repo", "include_closed": True}
            )

            # Should include closed issue
            assert result["synced_count"] == 3  # issue_1, issue_2, issue_4
            assert result["skipped_count"] == 1  # Only issue_3 (already synced)

    @pytest.mark.asyncio
    async def test_sync_updates_local_metadata(self, issue_tool, mock_issue_manager):
        """Test that local issues get GitHub metadata after sync."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            mock_create.return_value = 99

            await issue_tool._sync_to_github({"repo": "test/repo"})

            # Should update metadata with GitHub info
            calls = mock_issue_manager.update_issue.call_args_list
            assert len(calls) == 2  # Updated issue_1 and issue_2

            # Check metadata update for first issue
            first_call = calls[0]
            metadata = first_call[1]["metadata"]

            assert metadata["github_issue_number"] == 99
            assert metadata["github_repo"] == "test/repo"
            assert "synced_at" in metadata

    @pytest.mark.asyncio
    async def test_sync_handles_errors_gracefully(self, issue_tool, mock_issue_manager):
        """Test that sync continues after errors and reports them."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            # First call succeeds, second fails
            mock_create.side_effect = [99, Exception("GitHub API error")]

            result = await issue_tool._sync_to_github({"repo": "test/repo"})

            # Should have 1 success and 1 error
            assert result["synced_count"] == 1
            assert result["error_count"] == 1
            assert len(result["errors"]) == 1
            assert "GitHub API error" in result["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_sync_returns_github_urls(self, issue_tool, mock_issue_manager):
        """Test that sync returns GitHub URLs for synced issues."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            mock_create.return_value = 123

            result = await issue_tool._sync_to_github({"repo": "test/repo"})

            # Check URLs are formatted correctly
            assert len(result["synced"]) == 2
            first_synced = result["synced"][0]
            assert (
                first_synced["github_url"] == "https://github.com/test/repo/issues/123"
            )
            assert first_synced["github_number"] == 123


class TestCreateGitHubIssue:
    """Tests for _create_github_issue method."""

    @pytest.mark.asyncio
    async def test_create_github_issue_with_all_fields(self, issue_tool):
        """Test GitHub issue creation with all fields populated."""
        mock_issue = MagicMock()
        mock_issue.title = "Test Issue"
        mock_issue.description = "Test Description"
        mock_issue.status = "in_progress"
        mock_issue.priority = 1
        mock_issue.assignee = "testuser"
        mock_issue.session_id = "session_123"
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_1"
        mock_issue.metadata = {"area": "core"}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/test/repo/issues/42"

            result = await issue_tool._create_github_issue(mock_issue, "test/repo")

            assert result == 42

            # Verify gh CLI command
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "gh"
            assert cmd[1] == "issue"
            assert cmd[2] == "create"
            assert "--repo" in cmd
            assert "test/repo" in cmd
            assert "--title" in cmd
            assert "Test Issue" in cmd
            assert "--assignee" in cmd
            assert "testuser" in cmd
            assert "--label" in cmd

            # Check labels in command
            label_idx = cmd.index("--label")
            labels = cmd[label_idx + 1].split(",")
            assert "status:in-progress" in labels
            assert "priority:high" in labels
            assert "area:core" in labels

    @pytest.mark.asyncio
    async def test_create_github_issue_without_optional_fields(self, issue_tool):
        """Test GitHub issue creation without assignee or area."""
        mock_issue = MagicMock()
        mock_issue.title = "Minimal Issue"
        mock_issue.description = None
        mock_issue.status = "open"
        mock_issue.priority = 2
        mock_issue.assignee = None
        mock_issue.session_id = None
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_1"
        mock_issue.metadata = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/test/repo/issues/99"

            result = await issue_tool._create_github_issue(mock_issue, "test/repo")

            assert result == 99

            # Verify no assignee in command
            cmd = mock_run.call_args[0][0]
            assert "--assignee" not in cmd

            # Check labels (no area label)
            label_idx = cmd.index("--label")
            labels = cmd[label_idx + 1].split(",")
            assert "status:open" in labels
            assert "priority:normal" in labels
            assert not any("area:" in label for label in labels)

    @pytest.mark.asyncio
    async def test_create_github_issue_label_mapping(self, issue_tool):
        """Test that priority and status are correctly mapped to labels."""
        test_cases = [
            (0, "critical", "priority:critical"),
            (1, "high", "priority:high"),
            (2, "normal", "priority:normal"),
            (3, "low", "priority:low"),
            (4, "deferred", "priority:deferred"),
        ]

        for priority_num, priority_name, expected_label in test_cases:
            mock_issue = MagicMock()
            mock_issue.title = f"Priority {priority_name}"
            mock_issue.description = "Test"
            mock_issue.status = "open"
            mock_issue.priority = priority_num
            mock_issue.assignee = None
            mock_issue.session_id = "session_123"
            mock_issue.created_at = "2026-01-20T10:00:00Z"
            mock_issue.issue_id = f"issue_{priority_num}"
            mock_issue.metadata = None

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.stdout = (
                    f"https://github.com/test/repo/issues/{priority_num}"
                )

                await issue_tool._create_github_issue(mock_issue, "test/repo")

                cmd = mock_run.call_args[0][0]
                label_idx = cmd.index("--label")
                labels = cmd[label_idx + 1].split(",")
                assert expected_label in labels

    @pytest.mark.asyncio
    async def test_create_github_issue_parse_error(self, issue_tool):
        """Test error handling when issue number can't be parsed."""
        mock_issue = MagicMock()
        mock_issue.title = "Test"
        mock_issue.description = "Test"
        mock_issue.status = "open"
        mock_issue.priority = 2
        mock_issue.assignee = None
        mock_issue.session_id = "session_123"
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_1"
        mock_issue.metadata = None

        with patch("subprocess.run") as mock_run:
            # Return invalid format
            mock_run.return_value.stdout = "Invalid response"

            with pytest.raises(ValueError, match="Could not parse issue number"):
                await issue_tool._create_github_issue(mock_issue, "test/repo")

    @pytest.mark.asyncio
    async def test_create_github_issue_subprocess_error(self, issue_tool):
        """Test error handling when gh CLI fails."""
        mock_issue = MagicMock()
        mock_issue.title = "Test"
        mock_issue.description = "Test"
        mock_issue.status = "open"
        mock_issue.priority = 2
        mock_issue.assignee = None
        mock_issue.session_id = "session_123"
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_1"
        mock_issue.metadata = None

        with patch("subprocess.run") as mock_run:
            # Simulate gh CLI error
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "gh", stderr="Permission denied"
            )

            with pytest.raises(subprocess.CalledProcessError):
                await issue_tool._create_github_issue(mock_issue, "test/repo")


class TestSyncToGitHubIntegration:
    """Integration tests for the full sync operation via execute()."""

    @pytest.mark.asyncio
    async def test_sync_operation_via_execute(self, issue_tool, mock_issue_manager):
        """Test sync_to_github operation through the execute interface."""
        with patch.object(issue_tool, "_create_github_issue") as mock_create:
            mock_create.return_value = 100

            result = await issue_tool.execute(
                {"operation": "sync_to_github", "params": {"repo": "test/repo"}}
            )

            assert result.success is True
            assert "synced_count" in result.output
            assert result.output["synced_count"] == 2

    @pytest.mark.asyncio
    async def test_sync_operation_error_handling(self, issue_tool, mock_issue_manager):
        """Test error handling in sync operation."""
        with patch.object(issue_tool, "_sync_to_github") as mock_sync:
            mock_sync.side_effect = Exception("Network error")

            result = await issue_tool.execute(
                {"operation": "sync_to_github", "params": {}}
            )

            assert result.success is False
            assert "Network error" in result.error["message"]


class TestGitHubIssueBodyFormat:
    """Tests for GitHub issue body formatting."""

    @pytest.mark.asyncio
    async def test_issue_body_includes_metadata(self, issue_tool):
        """Test that issue body includes all required metadata."""
        mock_issue = MagicMock()
        mock_issue.title = "Test Issue"
        mock_issue.description = "Test Description"
        mock_issue.status = "open"
        mock_issue.priority = 2
        mock_issue.assignee = None
        mock_issue.session_id = "session_abc123"
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_xyz"
        mock_issue.metadata = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/test/repo/issues/1"

            await issue_tool._create_github_issue(mock_issue, "test/repo")

            cmd = mock_run.call_args[0][0]
            body_idx = cmd.index("--body")
            body = cmd[body_idx + 1]

            # Verify metadata in body
            assert "Test Description" in body
            assert "session_abc123" in body
            assert "issue_xyz" in body
            assert "2026-01-20T10:00:00Z" in body
            assert "Synced from Amplifier local issue tracker" in body

    @pytest.mark.asyncio
    async def test_issue_body_handles_missing_description(self, issue_tool):
        """Test that missing description is handled gracefully."""
        mock_issue = MagicMock()
        mock_issue.title = "No Description"
        mock_issue.description = None
        mock_issue.status = "open"
        mock_issue.priority = 2
        mock_issue.assignee = None
        mock_issue.session_id = "session_123"
        mock_issue.created_at = "2026-01-20T10:00:00Z"
        mock_issue.issue_id = "issue_1"
        mock_issue.metadata = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/test/repo/issues/1"

            await issue_tool._create_github_issue(mock_issue, "test/repo")

            cmd = mock_run.call_args[0][0]
            body_idx = cmd.index("--body")
            body = cmd[body_idx + 1]

            assert "No description provided" in body
