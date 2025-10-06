"""Git MCP server for Claude Agent SDK.

Provides Git repository operations through the Model Context Protocol.
Tools include status, diff, and log operations.
"""

import subprocess
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "git_status",
    "Get current git repository status (modified, staged, untracked files)",
    {},
)
async def git_status(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get the current status of the git repository.

    Returns:
        Dictionary with git status output in porcelain format
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {result.stderr or 'Not a git repository'}",
                    }
                ]
            }

        status_output = result.stdout.strip()
        if not status_output:
            status_output = "Working tree clean - no changes"

        return {
            "content": [
                {
                    "type": "text",
                    "text": status_output,
                }
            ]
        }

    except FileNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: git command not found - is git installed?",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error running git status: {e}",
                }
            ]
        }


@tool(
    "git_diff",
    "Get git diff for changes (optionally for specific file, staged/unstaged)",
    {"file": str, "staged": bool},
)
async def git_diff(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get diff of changes in the repository.

    Args:
        args: Dictionary with optional keys:
            - file: Specific file to diff (optional)
            - staged: If True, show staged changes (--cached)

    Returns:
        Dictionary with diff output
    """
    cmd = ["git", "diff"]

    # Add --cached flag for staged changes
    if args.get("staged", False):
        cmd.append("--cached")

    # Add specific file if provided
    if args.get("file"):
        cmd.append(args["file"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {result.stderr}",
                    }
                ]
            }

        diff_output = result.stdout.strip()
        if not diff_output:
            diff_output = "No changes to diff"

        return {
            "content": [
                {
                    "type": "text",
                    "text": diff_output,
                }
            ]
        }

    except FileNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: git command not found - is git installed?",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error running git diff: {e}",
                }
            ]
        }


@tool(
    "git_log",
    "Get git commit history with configurable limit",
    {"limit": int},
)
async def git_log(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get recent git commit history.

    Args:
        args: Dictionary with optional 'limit' key (default: 10)

    Returns:
        Dictionary with commit history in oneline format
    """
    limit = args.get("limit", 10)

    # Validate limit
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: limit must be an integer between 1 and 100",
                }
            ]
        }

    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--oneline"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {result.stderr}",
                    }
                ]
            }

        log_output = result.stdout.strip()
        if not log_output:
            log_output = "No commits found"

        return {
            "content": [
                {
                    "type": "text",
                    "text": log_output,
                }
            ]
        }

    except FileNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: git command not found - is git installed?",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error running git log: {e}",
                }
            ]
        }


# Create and export the MCP server
git_server = create_sdk_mcp_server(
    name="git",
    version="1.0.0",
    tools=[git_status, git_diff, git_log],
)
