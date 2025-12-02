"""GitLab MCP server for Claude Agent SDK.

Provides GitLab repository operations through the Model Context Protocol.
Tools include project search, file operations, issues, and merge requests.

API Reference: https://docs.gitlab.com/ee/api/rest/
"""

import base64
import os
import urllib.parse
from typing import Any

import httpx

from claude_agent_sdk import create_sdk_mcp_server, tool

# GitLab API configuration
GITLAB_API_BASE = "https://gitlab.com/api/v4"
REQUEST_TIMEOUT = 30.0
DEFAULT_PER_PAGE = 20


def _get_headers() -> dict[str, str]:
    """Get HTTP headers for GitLab API requests.

    Returns headers with PRIVATE-TOKEN if GITLAB_PERSONAL_ACCESS_TOKEN is set.

    Raises:
        ValueError: If GITLAB_PERSONAL_ACCESS_TOKEN is not set
    """
    token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "GITLAB_PERSONAL_ACCESS_TOKEN environment variable is required"
        )

    return {
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
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


def _encode_project_path(project_path: str) -> str:
    """URL-encode a project path for GitLab API.

    GitLab requires project paths to be URL-encoded when used in API endpoints.
    Example: 'owner/repo' becomes 'owner%2Frepo'
    """
    return urllib.parse.quote(project_path, safe="")


# Raw async handler functions (for testing)
async def _search_projects_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for projects on GitLab.

    Args:
        args: Dictionary with keys:
            - query: Search query (required)
            - per_page: Results per page (optional, default 20, max 100)

    Returns:
        Dictionary with matching projects
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
                f"{GITLAB_API_BASE}/projects",
                params={"search": query, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            projects = response.json()

            if not projects:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No projects found matching '{query}'",
                        }
                    ]
                }

            output_lines = [f"Found {len(projects)} projects:\n"]
            for project in projects:
                path = project.get("path_with_namespace", "unknown")
                description = (project.get("description") or "No description")[:100]
                stars = project.get("star_count", 0)
                visibility = project.get("visibility", "unknown")
                web_url = project.get("web_url", "")

                output_lines.append(f"- **{path}** ({visibility}, ⭐ {stars})")
                output_lines.append(f"  {description}")
                if web_url:
                    output_lines.append(f"  {web_url}")
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


async def _get_project_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get project metadata.

    Args:
        args: Dictionary with keys:
            - project: Project path (e.g., 'owner/repo') or numeric ID (required)

    Returns:
        Dictionary with project information
    """
    project = args.get("project", "").strip()

    if not project:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: project is required (e.g., 'owner/repo' or numeric ID)",
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

    # Encode project path if it contains a slash
    project_id = project if project.isdigit() else _encode_project_path(project)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITLAB_API_BASE}/projects/{project_id}",
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Project not found: {project}")

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

            output_lines = [
                f"# {data.get('path_with_namespace', 'unknown')}",
                "",
                f"**Description**: {data.get('description') or 'No description'}",
                f"**Visibility**: {data.get('visibility', 'Unknown')}",
                f"**Stars**: {data.get('star_count', 0)} | "
                f"**Forks**: {data.get('forks_count', 0)}",
                f"**Open Issues**: {data.get('open_issues_count', 0)}",
                f"**Default Branch**: {data.get('default_branch', 'main')}",
                f"**Created**: {data.get('created_at', 'unknown')}",
                f"**Updated**: {data.get('last_activity_at', 'unknown')}",
                f"**URL**: {data.get('web_url', '')}",
                "",
                f"**Clone (SSH)**: {data.get('ssh_url_to_repo', '')}",
                f"**Clone (HTTPS)**: {data.get('http_url_to_repo', '')}",
                f"**Topics**: {', '.join(data.get('topics', []))}",
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


async def _get_file_contents_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get file contents from a repository.

    Args:
        args: Dictionary with keys:
            - project: Project path (e.g., 'owner/repo') or numeric ID (required)
            - path: File path within the repository (required)
            - ref: Git reference (branch, tag, commit SHA) (optional, defaults to default branch)

    Returns:
        Dictionary with file contents
    """
    project = args.get("project", "").strip()
    path = args.get("path", "").strip()
    ref = args.get("ref", "").strip()

    if not project or not path:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: project and path are required",
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

    project_id = project if project.isdigit() else _encode_project_path(project)
    encoded_path = urllib.parse.quote(path, safe="")

    try:
        url = f"{GITLAB_API_BASE}/projects/{project_id}/repository/files/{encoded_path}"
        params = {}
        if ref:
            params["ref"] = ref

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                return _format_error(404, f"File not found: {path}")

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

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
            file_info += f"**Ref**: {data.get('ref', 'unknown')}\n"
            file_info += f"**Commit**: {data.get('commit_id', 'unknown')[:8]}\n\n"
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


async def _list_issues_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    List issues for a project.

    Args:
        args: Dictionary with keys:
            - project: Project path (e.g., 'owner/repo') or numeric ID (required)
            - state: Issue state: 'opened', 'closed', or 'all' (optional, default 'opened')
            - per_page: Results per page (optional, default 20, max 100)

    Returns:
        Dictionary with list of issues
    """
    project = args.get("project", "").strip()

    if not project:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: project is required",
                }
            ]
        }

    state = args.get("state", "opened")
    if state not in ("opened", "closed", "all"):
        state = "opened"

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

    project_id = project if project.isdigit() else _encode_project_path(project)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITLAB_API_BASE}/projects/{project_id}/issues",
                params={"state": state, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Project not found: {project}")

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            issues = response.json()

            if not issues:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No {state} issues found for {project}",
                        }
                    ]
                }

            output_lines = [f"# Issues for {project} ({state})\n"]
            for issue in issues:
                iid = issue.get("iid", "?")
                title = issue.get("title", "Untitled")
                state_emoji = "🟢" if issue.get("state") == "opened" else "🔴"
                labels = [lbl for lbl in issue.get("labels", [])]
                labels_str = f" [{', '.join(labels)}]" if labels else ""
                author = issue.get("author", {}).get("username", "unknown")

                output_lines.append(f"{state_emoji} **#{iid}**: {title}{labels_str}")
                output_lines.append(f"   by @{author} - {issue.get('web_url', '')}")
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
            - project: Project path (e.g., 'owner/repo') or numeric ID (required)
            - title: Issue title (required)
            - description: Issue description (optional)

    Returns:
        Dictionary with created issue details
    """
    project = args.get("project", "").strip()
    title = args.get("title", "").strip()
    description = args.get("description", "").strip()

    if not project or not title:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: project and title are required",
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

    project_id = project if project.isdigit() else _encode_project_path(project)

    try:
        payload: dict[str, Any] = {"title": title}
        if description:
            payload["description"] = description

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{GITLAB_API_BASE}/projects/{project_id}/issues",
                json=payload,
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Project not found: {project}")

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code == 403:
                return _format_error(
                    403,
                    "Access denied. Check project permissions and token scopes.",
                )

            if response.status_code not in (201, 200):
                return _format_error(response.status_code, response.text[:200])

            data = response.json()

            output_lines = [
                "✅ Issue created successfully!",
                "",
                f"**#{data.get('iid', '?')}**: {data.get('title', 'Untitled')}",
                f"**URL**: {data.get('web_url', '')}",
                f"**State**: {data.get('state', 'unknown')}",
                f"**Created by**: @{data.get('author', {}).get('username', 'unknown')}",
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


async def _list_merge_requests_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    List merge requests for a project.

    Args:
        args: Dictionary with keys:
            - project: Project path (e.g., 'owner/repo') or numeric ID (required)
            - state: MR state: 'opened', 'closed', 'merged', or 'all' (optional, default 'opened')
            - per_page: Results per page (optional, default 20, max 100)

    Returns:
        Dictionary with list of merge requests
    """
    project = args.get("project", "").strip()

    if not project:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: project is required",
                }
            ]
        }

    state = args.get("state", "opened")
    if state not in ("opened", "closed", "merged", "all"):
        state = "opened"

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

    project_id = project if project.isdigit() else _encode_project_path(project)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GITLAB_API_BASE}/projects/{project_id}/merge_requests",
                params={"state": state, "per_page": per_page},
                headers=headers,
            )

            if response.status_code == 404:
                return _format_error(404, f"Project not found: {project}")

            if response.status_code == 401:
                return _format_error(401, "Invalid or expired access token")

            if response.status_code != 200:
                return _format_error(response.status_code, response.text[:200])

            mrs = response.json()

            if not mrs:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No {state} merge requests found for {project}",
                        }
                    ]
                }

            output_lines = [f"# Merge Requests for {project} ({state})\n"]
            for mr in mrs:
                iid = mr.get("iid", "?")
                title = mr.get("title", "Untitled")
                mr_state = mr.get("state", "unknown")
                if mr_state == "opened":
                    state_emoji = "🟢"
                elif mr_state == "merged":
                    state_emoji = "🟣"
                else:
                    state_emoji = "🔴"

                source = mr.get("source_branch", "?")
                target = mr.get("target_branch", "?")
                author = mr.get("author", {}).get("username", "unknown")

                output_lines.append(f"{state_emoji} **!{iid}**: {title}")
                output_lines.append(f"   {source} → {target} by @{author}")
                output_lines.append(f"   {mr.get('web_url', '')}")
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


# Wrapped tools for SDK
@tool(
    "search_projects",
    "Search for GitLab projects by name or description.",
    {"query": str, "per_page": int},
)
async def search_projects(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for search_projects tool."""
    return await _search_projects_handler(args)


@tool(
    "get_project",
    "Get metadata and information about a GitLab project.",
    {"project": str},
)
async def get_project(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for get_project tool."""
    return await _get_project_handler(args)


@tool(
    "get_file_contents",
    "Get the contents of a file from a GitLab repository.",
    {"project": str, "path": str, "ref": str},
)
async def get_file_contents(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for get_file_contents tool."""
    return await _get_file_contents_handler(args)


@tool(
    "list_issues",
    "List issues for a GitLab project with optional filtering.",
    {"project": str, "state": str, "per_page": int},
)
async def list_issues(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for list_issues tool."""
    return await _list_issues_handler(args)


@tool(
    "create_issue",
    "Create a new issue in a GitLab project.",
    {"project": str, "title": str, "description": str},
)
async def create_issue(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for create_issue tool."""
    return await _create_issue_handler(args)


@tool(
    "list_merge_requests",
    "List merge requests for a GitLab project with optional filtering.",
    {"project": str, "state": str, "per_page": int},
)
async def list_merge_requests(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for list_merge_requests tool."""
    return await _list_merge_requests_handler(args)


# Create and export the MCP server
gitlab_server = create_sdk_mcp_server(
    name="gitlab",
    version="1.0.0",
    tools=[
        search_projects,
        get_project,
        get_file_contents,
        list_issues,
        create_issue,
        list_merge_requests,
    ],
)
