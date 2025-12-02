"""Unit tests for GitHub MCP server."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Import handler functions for testing (not decorated tools)
from mcp_servers.github.server import (
    _search_code_handler as search_code,
    _search_repos_handler as search_repos,
    _get_file_contents_handler as get_file_contents,
    _get_repo_handler as get_repo,
    _list_issues_handler as list_issues,
    _create_issue_handler as create_issue,
    github_server,
    _get_headers,
)


class TestGetHeaders:
    """Tests for _get_headers helper function."""

    def test_missing_token_raises_error(self):
        """Test error when GITHUB_PERSONAL_ACCESS_TOKEN not set."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GITHUB_PERSONAL_ACCESS_TOKEN"):
                _get_headers()

    def test_headers_with_token(self):
        """Test headers when token is set."""
        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            headers = _get_headers()
            assert headers["Authorization"] == "Bearer test-token"
            assert headers["Accept"] == "application/vnd.github+json"
            assert "X-GitHub-Api-Version" in headers


class TestSearchCode:
    """Tests for search_code tool."""

    @pytest.mark.asyncio
    async def test_missing_query(self):
        """Test error when query is missing."""
        result = await search_code({})
        assert "content" in result
        assert "Error: query is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_missing_token(self):
        """Test error when token is missing."""
        with patch.dict("os.environ", {}, clear=True):
            result = await search_code({"query": "test"})
            assert "content" in result
            assert "GITHUB_PERSONAL_ACCESS_TOKEN" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_search(self):
        """Test successful code search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_count": 1,
            "items": [
                {
                    "repository": {"full_name": "user/repo"},
                    "path": "src/main.py",
                    "html_url": "https://github.com/user/repo/blob/main/src/main.py"
                }
            ]
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await search_code({"query": "test", "per_page": 10})

                assert "content" in result
                assert "user/repo" in result["content"][0]["text"]
                assert "src/main.py" in result["content"][0]["text"]


class TestSearchRepos:
    """Tests for search_repos tool."""

    @pytest.mark.asyncio
    async def test_missing_query(self):
        """Test error when query is missing."""
        result = await search_repos({})
        assert "content" in result
        assert "Error: query is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_search(self):
        """Test successful repository search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_count": 1,
            "items": [
                {
                    "full_name": "facebook/react",
                    "description": "A JavaScript library for building UIs",
                    "stargazers_count": 200000,
                    "language": "JavaScript",
                    "html_url": "https://github.com/facebook/react"
                }
            ]
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await search_repos({"query": "react"})

                assert "content" in result
                assert "facebook/react" in result["content"][0]["text"]
                assert "JavaScript" in result["content"][0]["text"]


class TestGetFileContents:
    """Tests for get_file_contents tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await get_file_contents({})
        assert "content" in result
        assert "owner, repo, and path are required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_file_fetch(self):
        """Test successful file content fetch."""
        import base64
        content = base64.b64encode(b"print('Hello, World!')").decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": content,
            "encoding": "base64",
            "size": 22,
            "sha": "abc123def456"
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await get_file_contents({
                    "owner": "user",
                    "repo": "repo",
                    "path": "main.py"
                })

                assert "content" in result
                assert "Hello, World!" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_directory_listing(self):
        """Test directory listing response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "main.py", "type": "file"},
            {"name": "src", "type": "dir"}
        ]

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await get_file_contents({
                    "owner": "user",
                    "repo": "repo",
                    "path": "/"
                })

                assert "content" in result
                assert "Directory listing" in result["content"][0]["text"]
                assert "main.py" in result["content"][0]["text"]


class TestGetRepo:
    """Tests for get_repo tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await get_repo({})
        assert "content" in result
        assert "owner and repo are required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_repo_fetch(self):
        """Test successful repository metadata fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "full_name": "facebook/react",
            "description": "A JavaScript library for building UIs",
            "language": "JavaScript",
            "stargazers_count": 200000,
            "forks_count": 40000,
            "watchers_count": 6000,
            "open_issues_count": 500,
            "default_branch": "main",
            "created_at": "2013-05-24",
            "updated_at": "2025-01-15",
            "html_url": "https://github.com/facebook/react",
            "clone_url": "https://github.com/facebook/react.git",
            "topics": ["react", "javascript"],
            "license": {"name": "MIT License"}
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await get_repo({"owner": "facebook", "repo": "react"})

                assert "content" in result
                text = result["content"][0]["text"]
                assert "facebook/react" in text
                assert "JavaScript" in text
                assert "MIT License" in text


class TestListIssues:
    """Tests for list_issues tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await list_issues({})
        assert "content" in result
        assert "owner and repo are required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_issues_list(self):
        """Test successful issues listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 123,
                "title": "Bug: Something is broken",
                "state": "open",
                "labels": [{"name": "bug"}],
                "user": {"login": "contributor"},
                "html_url": "https://github.com/user/repo/issues/123"
            }
        ]

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await list_issues({
                    "owner": "user",
                    "repo": "repo",
                    "state": "open"
                })

                assert "content" in result
                text = result["content"][0]["text"]
                assert "#123" in text
                assert "Bug: Something is broken" in text
                assert "bug" in text

    @pytest.mark.asyncio
    async def test_filters_out_pull_requests(self):
        """Test that pull requests are filtered out from issues."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 123,
                "title": "Regular issue",
                "state": "open",
                "labels": [],
                "user": {"login": "user1"},
                "html_url": "https://github.com/user/repo/issues/123"
            },
            {
                "number": 124,
                "title": "Pull request",
                "state": "open",
                "pull_request": {"url": "..."},  # This marks it as a PR
                "labels": [],
                "user": {"login": "user2"},
                "html_url": "https://github.com/user/repo/pull/124"
            }
        ]

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await list_issues({"owner": "user", "repo": "repo"})

                text = result["content"][0]["text"]
                assert "#123" in text
                assert "#124" not in text  # PR should be filtered out


class TestCreateIssue:
    """Tests for create_issue tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await create_issue({})
        assert "content" in result
        assert "owner, repo, and title are required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_issue_creation(self):
        """Test successful issue creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 456,
            "title": "New Feature Request",
            "state": "open",
            "html_url": "https://github.com/user/repo/issues/456",
            "user": {"login": "author"}
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.github.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await create_issue({
                    "owner": "user",
                    "repo": "repo",
                    "title": "New Feature Request",
                    "body": "Please add this feature"
                })

                assert "content" in result
                text = result["content"][0]["text"]
                assert "Issue created successfully" in text
                assert "#456" in text


class TestGitHubServer:
    """Tests for GitHub server creation."""

    def test_server_is_sdk_dict(self):
        """Test server is an SDK-compatible dict."""
        assert isinstance(github_server, dict)
        assert github_server["type"] == "sdk"

    def test_server_has_correct_name(self):
        """Test server has correct name."""
        assert github_server["name"] == "github"

    def test_server_has_instance(self):
        """Test server has MCP server instance."""
        assert "instance" in github_server
        # Instance should be an MCP Server object
        from mcp.server.lowlevel.server import Server
        assert isinstance(github_server["instance"], Server)
