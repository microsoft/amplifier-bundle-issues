"""Tests for GitHub permission verification."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from amplifier_module_tool_issue.tool import IssueTool


@pytest.fixture
def issue_tool(tmp_path):
    """Create IssueTool instance for testing."""
    coordinator = MagicMock()
    tool = IssueTool(
        coordinator=coordinator,
        data_dir=tmp_path / "issues",
        actor="test",
        session_id="test_session",
    )
    return tool


class TestVerifyGitHubPermissions:
    """Tests for _verify_github_permissions method."""

    @pytest.mark.asyncio
    async def test_gh_not_installed(self, issue_tool):
        """Test error when gh CLI is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is False
            assert "not installed" in result["error"]
            assert "gh" in result["error"]

    @pytest.mark.asyncio
    async def test_gh_version_check_fails(self, issue_tool):
        """Test error when gh version check fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is False
            assert "not installed" in result["error"]

    @pytest.mark.asyncio
    async def test_not_authenticated(self, issue_tool):
        """Test error when not authenticated with GitHub."""
        with patch("subprocess.run") as mock_run:
            # First call (gh --version) succeeds
            # Second call (gh auth status) fails
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=1),  # gh auth status
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is False
            assert "Not authenticated" in result["error"]
            assert "gh auth login" in result["error"]

    @pytest.mark.asyncio
    async def test_repo_not_found(self, issue_tool):
        """Test error when repository doesn't exist or no access."""
        with patch("subprocess.run") as mock_run:
            # gh --version: OK
            # gh auth status: OK
            # gh issue list: 404 not found
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=1, stderr="404: not found"),  # gh issue list
            ]

            result = await issue_tool._verify_github_permissions("test/nonexistent")

            assert result["success"] is False
            assert "not found" in result["error"]
            assert "test/nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_access_forbidden(self, issue_tool):
        """Test error when access is forbidden (403)."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=1, stderr="403 Forbidden"),  # gh issue list
            ]

            result = await issue_tool._verify_github_permissions("test/forbidden")

            assert result["success"] is False
            assert "forbidden" in result["error"].lower()
            assert "test/forbidden" in result["error"]

    @pytest.mark.asyncio
    async def test_has_write_permission(self, issue_tool):
        """Test success when user has write permission."""
        with patch("subprocess.run") as mock_run:
            repo_info = {"viewerPermission": "WRITE"}

            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list
                MagicMock(returncode=0, stdout=json.dumps(repo_info)),  # gh repo view
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_has_admin_permission(self, issue_tool):
        """Test success when user has admin permission."""
        with patch("subprocess.run") as mock_run:
            repo_info = {"viewerPermission": "ADMIN"}

            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list
                MagicMock(returncode=0, stdout=json.dumps(repo_info)),  # gh repo view
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_has_maintain_permission(self, issue_tool):
        """Test success when user has maintain permission."""
        with patch("subprocess.run") as mock_run:
            repo_info = {"viewerPermission": "MAINTAIN"}

            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list
                MagicMock(returncode=0, stdout=json.dumps(repo_info)),  # gh repo view
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_only_read_permission(self, issue_tool):
        """Test error when user only has read permission."""
        with patch("subprocess.run") as mock_run:
            repo_info = {"viewerPermission": "READ"}

            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list
                MagicMock(returncode=0, stdout=json.dumps(repo_info)),  # gh repo view
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is False
            assert "read" in result["error"].lower()
            assert "write" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_permission_check_fallback(self, issue_tool):
        """Test fallback to success when permission parsing fails but can list issues."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list (success)
                MagicMock(returncode=1),  # gh repo view (fails)
            ]

            result = await issue_tool._verify_github_permissions("test/repo")

            # Should succeed as fallback since we could list issues
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_timeout_handling(self, issue_tool):
        """Test timeout error handling."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 5)

            result = await issue_tool._verify_github_permissions("test/repo")

            assert result["success"] is False
            assert "timed out" in result["error"].lower()


class TestSyncWithPermissionCheck:
    """Tests for sync_to_github with permission verification."""

    @pytest.mark.asyncio
    async def test_sync_fails_without_permissions(self, issue_tool):
        """Test that sync fails gracefully when user lacks permissions."""
        with patch.object(issue_tool, "_verify_github_permissions") as mock_verify:
            mock_verify.return_value = {
                "success": False,
                "error": "You don't have write access to this repository.",
            }

            result = await issue_tool._sync_to_github({"repo": "test/repo"})

            assert result["synced_count"] == 0
            assert result["error_count"] == 1
            assert "permission_denied" in result
            assert result["permission_denied"] is True
            assert "write access" in result["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_sync_proceeds_with_permissions(self, issue_tool):
        """Test that sync proceeds normally when permissions are OK."""
        # Mock issue manager
        mock_issue = MagicMock()
        mock_issue.issue_id = "issue_1"
        mock_issue.title = "Test"
        mock_issue.status = "open"
        mock_issue.metadata = None
        issue_tool.issue_manager.list_issues = MagicMock(return_value=[mock_issue])

        with patch.object(issue_tool, "_verify_github_permissions") as mock_verify:
            with patch.object(issue_tool, "_create_github_issue") as mock_create:
                mock_verify.return_value = {"success": True}
                mock_create.return_value = 42

                result = await issue_tool._sync_to_github({"repo": "test/repo"})

                # Should proceed normally
                assert result["synced_count"] == 1
                assert result["error_count"] == 0
                assert "permission_denied" not in result

    @pytest.mark.asyncio
    async def test_permission_error_message_in_execute(self, issue_tool):
        """Test that permission errors are properly returned via execute()."""
        with patch.object(issue_tool, "_verify_github_permissions") as mock_verify:
            mock_verify.return_value = {
                "success": False,
                "error": "Not authenticated. Run: gh auth login",
            }

            result = await issue_tool.execute(
                {"operation": "sync_to_github", "params": {"repo": "test/repo"}}
            )

            assert result.success is True  # Tool execution succeeded
            assert result.output["permission_denied"] is True
            assert "gh auth login" in result.output["errors"][0]["error"]


class TestPermissionCheckCommandConstruction:
    """Tests for correct command construction in permission checks."""

    @pytest.mark.asyncio
    async def test_gh_version_command(self, issue_tool):
        """Test that gh version check uses correct command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            await issue_tool._verify_github_permissions("test/repo")

            # First call should be gh --version
            first_call = mock_run.call_args_list[0]
            assert first_call[0][0] == ["gh", "--version"]
            assert first_call[1].get("timeout") == 5

    @pytest.mark.asyncio
    async def test_auth_status_command(self, issue_tool):
        """Test that auth check uses correct command."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
            ]

            await issue_tool._verify_github_permissions("test/repo")

            # Second call should be gh auth status
            second_call = mock_run.call_args_list[1]
            assert second_call[0][0] == ["gh", "auth", "status"]
            assert second_call[1].get("timeout") == 10

    @pytest.mark.asyncio
    async def test_issue_list_command(self, issue_tool):
        """Test that issue list uses correct command and repo."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # gh --version
                MagicMock(returncode=0),  # gh auth status
                MagicMock(returncode=0, stdout="[]"),  # gh issue list
            ]

            await issue_tool._verify_github_permissions("org/my-repo")

            # Third call should be gh issue list
            third_call = mock_run.call_args_list[2]
            cmd = third_call[0][0]
            assert cmd[0:3] == ["gh", "issue", "list"]
            assert "--repo" in cmd
            assert "org/my-repo" in cmd
            assert "--limit" in cmd
            assert "1" in cmd
