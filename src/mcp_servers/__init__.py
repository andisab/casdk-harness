"""MCP Servers for Claude Agent SDK.

This package contains in-process MCP servers (Method A) that run
directly within the agent process for faster execution and easier debugging.

Servers:
    - context7: Library documentation lookup via Context7 API
    - docker: Docker container management (Docker SDK)
    - git: Git repository operations (CLI wrapper)
    - github: GitHub repository operations via REST API
    - memory: Knowledge graph for persistent memory
"""

from mcp_servers.context7 import context7_server
from mcp_servers.docker import docker_server
from mcp_servers.git import git_server
from mcp_servers.github import github_server
from mcp_servers.memory import memory_server

__all__ = [
    "context7_server",
    "docker_server",
    "git_server",
    "github_server",
    "memory_server",
]
