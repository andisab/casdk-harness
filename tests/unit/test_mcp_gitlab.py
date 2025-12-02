"""Unit tests for GitLab MCP server."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Import handler functions for testing (not decorated tools)
from mcp_servers.gitlab.server import (
    _search_projects_handler as search_projects,
    _get_project_handler as get_project,
    _get_file_contents_handler as get_file_contents,
    _list_issues_handler as list_issues,
    _create_issue_handler as create_issue,
    _list_merge_requests_handler as list_merge_requests,
    gitlab_server,
    _get_headers,
    _encode_project_path,
)


class TestGetHeaders:
    """Tests for _get_headers helper function."""

    def test_missing_token_raises_error(self):
        """Test error when GITLAB_PERSONAL_ACCESS_TOKEN not set."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GITLAB_PERSONAL_ACCESS_TOKEN"):
                _get_headers()

    def test_headers_with_token(self):
        """Test headers when token is set."""
        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            headers = _get_headers()
            assert headers["PRIVATE-TOKEN"] == "test-token"
            assert headers["Content-Type"] == "application/json"


class TestEncodeProjectPath:
    """Tests for _encode_project_path helper function."""

    def test_encodes_slash(self):
        """Test that slashes are encoded."""
        result = _encode_project_path("owner/repo")
        assert result == "owner%2Frepo"

    def test_encodes_special_characters(self):
        """Test that special characters are encoded."""
        result = _encode_project_path("owner/my-repo.test")
        assert "%2F" in result


class TestSearchProjects:
    """Tests for search_projects tool."""

    @pytest.mark.asyncio
    async def test_missing_query(self):
        """Test error when query is missing."""
        result = await search_projects({})
        assert "content" in result
        assert "Error: query is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_missing_token(self):
        """Test error when token is missing."""
        with patch.dict("os.environ", {}, clear=True):
            result = await search_projects({"query": "test"})
            assert "content" in result
            assert "GITLAB_PERSONAL_ACCESS_TOKEN" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_search(self):
        """Test successful project search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "path_with_namespace": "owner/repo",
                "description": "A test project",
                "star_count": 100,
                "visibility": "public",
                "web_url": "https://gitlab.com/owner/repo"
            }
        ]

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await search_projects({"query": "test", "per_page": 10})

                assert "content" in result
                assert "owner/repo" in result["content"][0]["text"]
                assert "public" in result["content"][0]["text"]


class TestGetProject:
    """Tests for get_project tool."""

    @pytest.mark.asyncio
    async def test_missing_project(self):
        """Test error when project is missing."""
        result = await get_project({})
        assert "content" in result
        assert "project is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_project_fetch(self):
        """Test successful project metadata fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "path_with_namespace": "owner/repo",
            "description": "A test project",
            "visibility": "public",
            "star_count": 100,
            "forks_count": 20,
            "open_issues_count": 5,
            "default_branch": "main",
            "created_at": "2024-01-01",
            "last_activity_at": "2024-12-01",
            "web_url": "https://gitlab.com/owner/repo",
            "ssh_url_to_repo": "git@gitlab.com:owner/repo.git",
            "http_url_to_repo": "https://gitlab.com/owner/repo.git",
            "topics": ["python", "api"]
        }

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await get_project({"project": "owner/repo"})

                assert "content" in result
                text = result["content"][0]["text"]
                assert "owner/repo" in text
                assert "public" in text


class TestGetFileContents:
    """Tests for get_file_contents tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await get_file_contents({})
        assert "content" in result
        assert "project and path are required" in result["content"][0]["text"]

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
            "ref": "main",
            "commit_id": "abc123def456"
        }

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await get_file_contents({
                    "project": "owner/repo",
                    "path": "main.py"
                })

                assert "content" in result
                assert "Hello, World!" in result["content"][0]["text"]


class TestListIssues:
    """Tests for list_issues tool."""

    @pytest.mark.asyncio
    async def test_missing_project(self):
        """Test error when project is missing."""
        result = await list_issues({})
        assert "content" in result
        assert "project is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_issues_list(self):
        """Test successful issues listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "iid": 123,
                "title": "Bug: Something is broken",
                "state": "opened",
                "labels": ["bug"],
                "author": {"username": "contributor"},
                "web_url": "https://gitlab.com/owner/repo/-/issues/123"
            }
        ]

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await list_issues({
                    "project": "owner/repo",
                    "state": "opened"
                })

                assert "content" in result
                text = result["content"][0]["text"]
                assert "#123" in text
                assert "Bug: Something is broken" in text
                assert "bug" in text


class TestCreateIssue:
    """Tests for create_issue tool."""

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test error when required parameters are missing."""
        result = await create_issue({})
        assert "content" in result
        assert "project and title are required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_issue_creation(self):
        """Test successful issue creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "iid": 456,
            "title": "New Feature Request",
            "state": "opened",
            "web_url": "https://gitlab.com/owner/repo/-/issues/456",
            "author": {"username": "author"}
        }

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await create_issue({
                    "project": "owner/repo",
                    "title": "New Feature Request",
                    "description": "Please add this feature"
                })

                assert "content" in result
                text = result["content"][0]["text"]
                assert "Issue created successfully" in text
                assert "#456" in text


class TestListMergeRequests:
    """Tests for list_merge_requests tool."""

    @pytest.mark.asyncio
    async def test_missing_project(self):
        """Test error when project is missing."""
        result = await list_merge_requests({})
        assert "content" in result
        assert "project is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_successful_mrs_list(self):
        """Test successful merge requests listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "iid": 42,
                "title": "Add new feature",
                "state": "opened",
                "source_branch": "feature-branch",
                "target_branch": "main",
                "author": {"username": "developer"},
                "web_url": "https://gitlab.com/owner/repo/-/merge_requests/42"
            }
        ]

        with patch.dict(
            "os.environ",
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "test-token"},
            clear=False
        ):
            with patch("mcp_servers.gitlab.server.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance

                result = await list_merge_requests({
                    "project": "owner/repo",
                    "state": "opened"
                })

                assert "content" in result
                text = result["content"][0]["text"]
                assert "!42" in text
                assert "Add new feature" in text
                assert "feature-branch" in text
                assert "main" in text


class TestGitLabServer:
    """Tests for GitLab server creation."""

    def test_server_is_sdk_dict(self):
        """Test server is an SDK-compatible dict."""
        assert isinstance(gitlab_server, dict)
        assert gitlab_server["type"] == "sdk"

    def test_server_has_correct_name(self):
        """Test server has correct name."""
        assert gitlab_server["name"] == "gitlab"

    def test_server_has_instance(self):
        """Test server has MCP server instance."""
        assert "instance" in gitlab_server
        # Instance should be an MCP Server object
        from mcp.server.lowlevel.server import Server
        assert isinstance(gitlab_server["instance"], Server)
