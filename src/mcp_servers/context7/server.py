"""Context7 MCP server for Claude Agent SDK.

Provides library documentation lookup through the Model Context Protocol.
Tools include resolve_library_id and get_library_docs.

API Reference: https://context7.com/api/v1
"""

import os
from typing import Any

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

# Context7 API configuration
CONTEXT7_API_BASE = "https://context7.com/api/v1"
DEFAULT_TOKENS = 10000
REQUEST_TIMEOUT = 30.0


def _get_headers() -> dict[str, str]:
    """Get HTTP headers for Context7 API requests.

    Returns headers with Authorization if CONTEXT7_API_KEY is set.
    API works without key but has stricter rate limits.
    """
    headers = {"Accept": "application/json"}
    api_key = os.getenv("CONTEXT7_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# Raw async functions (for testing)
async def _resolve_library_id_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for libraries matching the given name.

    Args:
        args: Dictionary with 'libraryName' key (required)

    Returns:
        Dictionary with matching libraries including IDs, titles, and descriptions
    """
    library_name = args.get("libraryName", "").strip()

    if not library_name:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: libraryName is required",
                }
            ]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{CONTEXT7_API_BASE}/search",
                params={"query": library_name},
                headers=_get_headers(),
            )

            if response.status_code == 429:
                error_data = response.json()
                retry_after = error_data.get("retryAfterSeconds", 60)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Rate limited. Retry after {retry_after} seconds. "
                            "Consider setting CONTEXT7_API_KEY for higher limits.",
                        }
                    ]
                }

            if response.status_code == 401:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Unauthorized. Check your CONTEXT7_API_KEY.",
                        }
                    ]
                }

            if response.status_code != 200:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: API returned status {response.status_code}",
                        }
                    ]
                }

            data = response.json()
            results = data.get("results", [])

            if not results:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No libraries found matching '{library_name}'",
                        }
                    ]
                }

            # Format results
            output_lines = [f"Found {len(results)} matching libraries:\n"]
            for lib in results[:10]:  # Limit to top 10
                lib_id = lib.get("id", "unknown")
                title = lib.get("title", "Untitled")
                description = lib.get("description", "No description")[:200]
                snippets = lib.get("totalSnippets", 0)
                score = lib.get("benchmarkScore", "N/A")

                output_lines.append(f"- **{title}**")
                output_lines.append(f"  - Library ID: `{lib_id}`")
                output_lines.append(f"  - Description: {description}")
                output_lines.append(f"  - Snippets: {snippets}, Score: {score}")
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Request timed out. Try again later.",
                }
            ]
        }
    except httpx.RequestError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Network request failed: {e}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error resolving library: {e}",
                }
            ]
        }


async def _get_library_docs_handler(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch documentation for a library.

    Args:
        args: Dictionary with keys:
            - context7CompatibleLibraryID: Library ID in format '/project/library' (required)
            - topic: Filter by topic (optional)
            - tokens: Maximum tokens to return (optional, default 10000)

    Returns:
        Dictionary with documentation content
    """
    library_id = args.get("context7CompatibleLibraryID", "").strip()

    if not library_id:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: context7CompatibleLibraryID is required. "
                    "Use resolve_library_id to find the correct ID.",
                }
            ]
        }

    # Ensure library_id starts with /
    if not library_id.startswith("/"):
        library_id = f"/{library_id}"

    # Build API URL: /api/v1/{project}/{library}
    # Library ID format is /project/library, so we append it directly
    url = f"{CONTEXT7_API_BASE}{library_id}"

    # Build query params
    params: dict[str, Any] = {}
    topic = args.get("topic", "").strip()
    if topic:
        params["topic"] = topic

    tokens = args.get("tokens", DEFAULT_TOKENS)
    if isinstance(tokens, int) and tokens > 0:
        params["tokens"] = tokens
    else:
        params["tokens"] = DEFAULT_TOKENS

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                url,
                params=params,
                headers=_get_headers(),
            )

            if response.status_code == 429:
                error_data = response.json()
                retry_after = error_data.get("retryAfterSeconds", 60)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Rate limited. Retry after {retry_after} seconds. "
                            "Consider setting CONTEXT7_API_KEY for higher limits.",
                        }
                    ]
                }

            if response.status_code == 401:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Unauthorized. Check your CONTEXT7_API_KEY.",
                        }
                    ]
                }

            if response.status_code == 404:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Library not found: {library_id}. "
                            "Use resolve_library_id to find the correct ID.",
                        }
                    ]
                }

            if response.status_code != 200:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: API returned status {response.status_code}",
                        }
                    ]
                }

            data = response.json()

            # Extract content - format varies by endpoint
            content = data.get("content", "")
            if not content and isinstance(data, str):
                content = data

            if not content:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No documentation found for {library_id}"
                            + (f" with topic '{topic}'" if topic else ""),
                        }
                    ]
                }

            # Add metadata if available
            metadata = data.get("metadata", {})
            header = f"# Documentation for {library_id}\n"
            if topic:
                header += f"Topic: {topic}\n"
            if metadata:
                header += f"Tokens: {metadata.get('tokens_returned', 'N/A')}\n"
            header += "\n---\n\n"

            return {
                "content": [
                    {
                        "type": "text",
                        "text": header + str(content),
                    }
                ]
            }

    except httpx.TimeoutException:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Request timed out. Try again later.",
                }
            ]
        }
    except httpx.RequestError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Network request failed: {e}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error fetching documentation: {e}",
                }
            ]
        }


# Wrapped tools for SDK
@tool(
    "resolve_library_id",
    "Resolve a library/package name to Context7-compatible library ID. "
    "Returns matching libraries with IDs, descriptions, and metadata.",
    {"libraryName": str},
)
async def resolve_library_id(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for resolve_library_id tool."""
    return await _resolve_library_id_handler(args)


@tool(
    "get_library_docs",
    "Fetch documentation for a library using its Context7-compatible library ID. "
    "Use resolve_library_id first to get the ID.",
    {"context7CompatibleLibraryID": str, "topic": str, "tokens": int},
)
async def get_library_docs(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for get_library_docs tool."""
    return await _get_library_docs_handler(args)


# Create and export the MCP server
context7_server = create_sdk_mcp_server(
    name="context7",
    version="1.0.0",
    tools=[resolve_library_id, get_library_docs],
)
