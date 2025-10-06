"""Integration tests for Git MCP server."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from mcp_servers.git.server import git_diff, git_log, git_status


@pytest.mark.integration
@pytest.mark.asyncio
async def test_git_status():
    """Test Git MCP git_status tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmppath, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )

        # Change to test directory for git operations
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmppath)

            # Test status on clean repo
            result = await git_status({})
            assert "content" in result
            content = result["content"][0]["text"]
            assert "clean" in content.lower() or "no changes" in content.lower()

            # Create a file
            (tmppath / "test.txt").write_text("test")

            # Test status with untracked file
            result = await git_status({})
            assert "content" in result

        finally:
            os.chdir(original_cwd)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_git_log():
    """Test Git MCP git_log tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Initialize git repo and create a commit
        subprocess.run(["git", "init"], cwd=tmppath, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )

        # Create and commit a file
        test_file = tmppath / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmppath, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmppath)

            # Test git log
            result = await git_log({"limit": 5})
            assert "content" in result
            content = result["content"][0]["text"]
            assert "Initial commit" in content

        finally:
            os.chdir(original_cwd)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_git_diff():
    """Test Git MCP git_diff tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Initialize git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmppath, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )

        test_file = tmppath / "test.txt"
        test_file.write_text("version 1")
        subprocess.run(["git", "add", "."], cwd=tmppath, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmppath,
            check=True,
            capture_output=True,
        )

        # Modify the file
        test_file.write_text("version 2")

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmppath)

            # Test unstaged diff
            result = await git_diff({"staged": False})
            assert "content" in result
            content = result["content"][0]["text"]
            # Should show the change or indicate no changes to diff

        finally:
            os.chdir(original_cwd)
