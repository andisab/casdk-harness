"""GitHub MCP server for Claude Agent SDK.

Provides GitHub repository operations through the Model Context Protocol.
Tools include code search, repository operations, and issue management.

API Reference: https://docs.github.com/en/rest
"""

import base64
import os
from typing import Any

import httpx

from claude_agent_sdk import create_sdk_mcp_server, tool

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 30.0
DEFAULT_PER_PAGE = 30


def _get_headers() -> dict[str, str]:
    """Get HTTP headers for GitHub API requests.

    Returns headers with Authorization if GITHUB_PERSONAL_ACCESS_TOKEN is set.

    Raises:
        ValueError: If GITHUB_PERSONAL_ACCESS_TOKEN is not set
    """
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "GITHUB_PERSONAL_ACCESS_TOKEN environment variable is required"
        )

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _format_error(status_code: int, message: str) -> dict[str, Any]:
    """Format an error response."""
    return {
        "content": [
            {
                "type": "text",
                "text": f"Error ({status_code}): {message}",
            }
        ]
    }


# Raw async handler functions (for testing)
async def _search_code_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for code across GitHub.

    Args:
        args: Dictionary with keys:
            - query: Search query (required). Can include qualifiers like
              'language:python', 'repo:owner/name', 'path:src/'
            - per_page: Results per page (optional, default 30, max 100)

    Returns:
        Dictionary with matching code files
    """
    query = args.get("query", "").strip()

    if not query:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: query is required",
                }
            ]
        }

    per_page = min(args.get("per_page", DEFAULT_PER_PAGE), 100)

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/search/code",
                params={"q": query, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 403:
                return _format_error(403, "Rate limit exceeded or access denied")

            if response.status_code == 422:
                return _format_error(422, "Invalid search query")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()
            total_count = data.get("total_count", 0)
            items = data.get("items", [])

            if not items:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No code found matching '{query}'",
                        }
                    ]
                }

            output_lines = [f"Found {total_count} results (showing {len(items)}):\n"]
            for item in items:
                repo = item.get("repository", {}).get("full_name", "unknown")
                path = item.get("path", "unknown")
                html_url = item.get("html_url", "")

                output_lines.append(f"- **{repo}**: `{path}`")
                if html_url:
                    output_lines.append(f"  {html_url}")
                output_lines.append("")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_lines),
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


async def _search_repos_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for repositories on GitHub.

    Args:
        args: Dictionary with keys:
            - query: Search query (required). Can include qualifiers like
              'language:python', 'stars:>1000', 'topic:machine-learning'
            - per_page: Results per page (optional, default 30, max 100)

    Returns:
        Dictionary with matching repositories
    """
    query = args.get("query", "").strip()

    if not query:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: query is required",
                }
            ]
        }

    per_page = min(args.get("per_page", DEFAULT_PER_PAGE), 100)

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/search/repositories",
                params={"q": query, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 403:
                return _format_error(403, "Rate limit exceeded or access denied")

            if response.status_code == 422:
                return _format_error(422, "Invalid search query")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()
            total_count = data.get("total_count", 0)
            items = data.get("items", [])

            if not items:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No repositories found matching '{query}'",
                        }
                    ]
                }

            output_lines = [f"Found {total_count} repositories (showing {len(items)}):\n"]
            for repo in items:
                full_name = repo.get("full_name", "unknown")
                description = repo.get("description", "No description")[:100]
                stars = repo.get("stargazers_count", 0)
                language = repo.get("language", "Unknown")
                html_url = repo.get("html_url", "")

                output_lines.append(f"- **{full_name}** ({language}, ⭐ {stars})")
                output_lines.append(f"  {description}")
                if html_url:
                    output_lines.append(f"  {html_url}")
                output_lines.append("")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_lines),
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


async def _get_file_contents_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get file contents from a repository.

    Args:
        args: Dictionary with keys:
            - owner: Repository owner (required)
            - repo: Repository name (required)
            - path: File path within the repository (required)
            - ref: Git reference (branch, tag, commit SHA) (optional, defaults to main)

    Returns:
        Dictionary with file contents
    """
    owner = args.get("owner", "").strip()
    repo = args.get("repo", "").strip()
    path = args.get("path", "").strip()
    ref = args.get("ref", "").strip()

    if not owner or not repo or not path:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: owner, repo, and path are required",
                }
            ]
        }

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                return _format_error(404, f"File not found: {path}")

            if response.status_code == 403:
                return _format_error(403, "Rate limit exceeded or access denied")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

            # Check if it's a file or directory
            if isinstance(data, list):
                # It's a directory
                output_lines = [f"Directory listing for {path}:\n"]
                for item in data:
                    item_type = "📁" if item.get("type") == "dir" else "📄"
                    output_lines.append(f"{item_type} {item.get('name', 'unknown')}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "\n".join(output_lines),
                        }
                    ]
                }

            # It's a file
            content = data.get("content", "")
            encoding = data.get("encoding", "")

            if encoding == "base64" and content:
                try:
                    decoded_content = base64.b64decode(content).decode("utf-8")
                except Exception:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Error: Unable to decode file content (binary file?)",
                            }
                        ]
                    }
            else:
                decoded_content = content

            file_info = f"# {path}\n"
            file_info += f"**Size**: {data.get('size', 'unknown')} bytes\n"
            file_info += f"**SHA**: {data.get('sha', 'unknown')[:8]}\n\n"
            file_info += "```\n" + decoded_content + "\n```"

            return {
                "content": [
                    {
                        "type": "text",
                        "text": file_info,
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


async def _get_repo_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get repository metadata.

    Args:
        args: Dictionary with keys:
            - owner: Repository owner (required)
            - repo: Repository name (required)

    Returns:
        Dictionary with repository information
    """
    owner = args.get("owner", "").strip()
    repo = args.get("repo", "").strip()

    if not owner or not repo:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: owner and repo are required",
                }
            ]
        }

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Repository not found: {owner}/{repo}")

            if response.status_code == 403:
                return _format_error(403, "Rate limit exceeded or access denied")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

            output_lines = [
                f"# {data.get('full_name', 'unknown')}",
                "",
                f"**Description**: {data.get('description', 'No description')}",
                f"**Language**: {data.get('language', 'Unknown')}",
                f"**Stars**: {data.get('stargazers_count', 0)} | "
                f"**Forks**: {data.get('forks_count', 0)} | "
                f"**Watchers**: {data.get('watchers_count', 0)}",
                f"**Open Issues**: {data.get('open_issues_count', 0)}",
                f"**Default Branch**: {data.get('default_branch', 'main')}",
                f"**Created**: {data.get('created_at', 'unknown')}",
                f"**Updated**: {data.get('updated_at', 'unknown')}",
                f"**URL**: {data.get('html_url', '')}",
                "",
                f"**Clone URL**: {data.get('clone_url', '')}",
                f"**Topics**: {', '.join(data.get('topics', []))}",
            ]

            if data.get("license"):
                output_lines.append(
                    f"**License**: {data['license'].get('name', 'Unknown')}"
                )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_lines),
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


async def _list_issues_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    List issues for a repository.

    Args:
        args: Dictionary with keys:
            - owner: Repository owner (required)
            - repo: Repository name (required)
            - state: Issue state: 'open', 'closed', or 'all' (optional, default 'open')
            - per_page: Results per page (optional, default 30, max 100)

    Returns:
        Dictionary with list of issues
    """
    owner = args.get("owner", "").strip()
    repo = args.get("repo", "").strip()

    if not owner or not repo:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: owner and repo are required",
                }
            ]
        }

    state = args.get("state", "open")
    if state not in ("open", "closed", "all"):
        state = "open"

    per_page = min(args.get("per_page", DEFAULT_PER_PAGE), 100)

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
                params={"state": state, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Repository not found: {owner}/{repo}")

            if response.status_code == 403:
                return _format_error(403, "Rate limit exceeded or access denied")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            issues = response.json()

            # Filter out pull requests (they appear in issues endpoint)
            issues = [i for i in issues if "pull_request" not in i]

            if not issues:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No {state} issues found for {owner}/{repo}",
                        }
                    ]
                }

            output_lines = [f"# Issues for {owner}/{repo} ({state})\n"]
            for issue in issues:
                number = issue.get("number", "?")
                title = issue.get("title", "Untitled")
                state_emoji = "🟢" if issue.get("state") == "open" else "🔴"
                labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
                labels_str = f" [{', '.join(labels)}]" if labels else ""
                user = issue.get("user", {}).get("login", "unknown")

                output_lines.append(f"{state_emoji} **#{number}**: {title}{labels_str}")
                output_lines.append(f"   by @{user} - {issue.get('html_url', '')}")
                output_lines.append("")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_lines),
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


async def _create_issue_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new issue.

    Args:
        args: Dictionary with keys:
            - owner: Repository owner (required)
            - repo: Repository name (required)
            - title: Issue title (required)
            - body: Issue body/description (optional)

    Returns:
        Dictionary with created issue details
    """
    owner = args.get("owner", "").strip()
    repo = args.get("repo", "").strip()
    title = args.get("title", "").strip()
    body = args.get("body", "").strip()

    if not owner or not repo or not title:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: owner, repo, and title are required",
                }
            ]
        }

    try:
        headers = _get_headers()
    except ValueError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(e),
                }
            ]
        }

    try:
        payload: dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
                json=payload,
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Repository not found: {owner}/{repo}")

            if response.status_code == 403:
                return _format_error(
                    403,
                    "Access denied. Check repository permissions and token scopes.",
                )

            if response.status_code == 410:
                return _format_error(410, "Issues are disabled for this repository")

            if response.status_code not in (201, 200):
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

            output_lines = [
                "✅ Issue created successfully!",
                "",
                f"**#{data.get('number', '?')}**: {data.get('title', 'Untitled')}",
                f"**URL**: {data.get('html_url', '')}",
                f"**State**: {data.get('state', 'unknown')}",
                f"**Created by**: @{data.get('user', {}).get('login', 'unknown')}",
            ]

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(output_lines),
                    }
                ]
            }

    except httpx.TimeoutException:
        return _format_error(0, "Request timed out")
    except httpx.RequestError as e:
        return _format_error(0, f"Network error: {e}")
    except Exception as e:
        return _format_error(0, f"Unexpected error: {e}")


# Wrapped tools for SDK
@tool(
    "search_code",
    "Search for code across GitHub repositories. Returns matching files with context.",
    {"query": str, "per_page": int},
)
async def search_code(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for search_code tool."""
    return await _search_code_handler(args)


@tool(
    "search_repos",
    "Search for GitHub repositories by name, description, or other criteria.",
    {"query": str, "per_page": int},
)
async def search_repos(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for search_repos tool."""
    return await _search_repos_handler(args)


@tool(
    "get_file_contents",
    "Get the contents of a file from a GitHub repository.",
    {"owner": str, "repo": str, "path": str, "ref": str},
)
async def get_file_contents(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for get_file_contents tool."""
    return await _get_file_contents_handler(args)


@tool(
    "get_repo",
    "Get metadata and information about a GitHub repository.",
    {"owner": str, "repo": str},
)
async def get_repo(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for get_repo tool."""
    return await _get_repo_handler(args)


@tool(
    "list_issues",
    "List issues for a GitHub repository with optional filtering.",
    {"owner": str, "repo": str, "state": str, "per_page": int},
)
async def list_issues(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for list_issues tool."""
    return await _list_issues_handler(args)


@tool(
    "create_issue",
    "Create a new issue in a GitHub repository.",
    {"owner": str, "repo": str, "title": str, "body": str},
)
async def create_issue(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for create_issue tool."""
    return await _create_issue_handler(args)


# Create and export the MCP server
github_server = create_sdk_mcp_server(
    name="github",
    version="1.0.0",
    tools=[
        search_code,
        search_repos,
        get_file_contents,
        get_repo,
        list_issues,
        create_issue,
    ],
)
