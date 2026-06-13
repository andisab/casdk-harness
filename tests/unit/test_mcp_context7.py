"""Unit tests for Context7 MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_servers.context7.server import (
    _get_headers,
    context7_server,
)
from mcp_servers.context7.server import (
    _get_library_docs_handler as get_library_docs,
)

# Import the server module - use handler functions for testing
from mcp_servers.context7.server import (
    _resolve_library_id_handler as resolve_library_id,
)


class TestGetHeaders:
    """Tests for _get_headers helper function."""

    def test_headers_without_api_key(self):
        """Test headers when CONTEXT7_API_KEY not set."""
        with patch.dict("os.environ", {}, clear=True):
            headers = _get_headers()
            assert "Accept" in headers
            assert headers["Accept"] == "application/json"
            assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """Test headers include Authorization when API key is set."""
        with patch.dict("os.environ", {"CONTEXT7_API_KEY": "test-key"}, clear=False):
            headers = _get_headers()
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-key"


class TestResolveLibraryId:
    """Tests for resolve_library_id tool."""

    @pytest.mark.asyncio
    async def test_missing_library_name(self):
        """Test error when libraryName is missing."""
        result = await resolve_library_id({})
        assert "content" in result
        assert "Error: libraryName is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_empty_library_name(self):
        """Test error when libraryName is empty."""
        result = await resolve_library_id({"libraryName": "  "})
        assert "content" in result
        assert "Error: libraryName is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_search(self):
        """Test successful library search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "/vercel/next.js",
                    "title": "Next.js",
                    "description": "The React Framework",
                    "totalSnippets": 100,
                    "benchmarkScore": 85,
                }
            ]
        }

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await resolve_library_id({"libraryName": "next.js"})

            assert "content" in result
            assert "Next.js" in result["content"][0]["text"]
            assert "/vercel/next.js" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_no_results_found(self):
        """Test when no libraries are found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await resolve_library_id({"libraryName": "nonexistent-lib"})

            assert "content" in result
            assert "No libraries found" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"retryAfterSeconds": 60}

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await resolve_library_id({"libraryName": "react"})

            assert "content" in result
            assert "Rate limited" in result["content"][0]["text"]
            assert "60" in result["content"][0]["text"]


class TestGetLibraryDocs:
    """Tests for get_library_docs tool."""

    @pytest.mark.asyncio
    async def test_missing_library_id(self):
        """Test error when library ID is missing."""
        result = await get_library_docs({})
        assert "content" in result
        assert "context7CompatibleLibraryID is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_library_id_normalization(self):
        """Test that library IDs without leading slash are normalized."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "# Documentation",
            "metadata": {"tokens_returned": 1000}
        }

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # Library ID without leading slash
            await get_library_docs(
                {"context7CompatibleLibraryID": "vercel/next.js"}
            )

            # Should have made request with normalized URL
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert "/vercel/next.js" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_successful_docs_fetch(self):
        """Test successful documentation fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "# Next.js Routing\n\nThis is the documentation.",
            "metadata": {"tokens_returned": 500}
        }

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await get_library_docs({
                "context7CompatibleLibraryID": "/vercel/next.js",
                "topic": "routing",
                "tokens": 5000
            })

            assert "content" in result
            assert "Next.js Routing" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_library_not_found(self):
        """Test 404 response for non-existent library."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("mcp_servers.context7.server.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await get_library_docs({
                "context7CompatibleLibraryID": "/nonexistent/library"
            })

            assert "content" in result
            assert "Library not found" in result["content"][0]["text"]


class TestContext7Server:
    """Tests for Context7 server creation."""

    def test_server_is_sdk_dict(self):
        """Test server is an SDK-compatible dict."""
        assert isinstance(context7_server, dict)
        assert context7_server["type"] == "sdk"

    def test_server_has_correct_name(self):
        """Test server has correct name."""
        assert context7_server["name"] == "context7"

    def test_server_has_instance(self):
        """Test server has MCP server instance."""
        assert "instance" in context7_server
        # Instance should be an MCP Server object
        from mcp.server.lowlevel.server import Server
        assert isinstance(context7_server["instance"], Server)
