"""Docker MCP server for Claude Agent SDK.

Provides Docker container operations through the Model Context Protocol.
Tools include listing containers, viewing logs, and getting container stats.
"""

from typing import Any

import docker
from claude_agent_sdk import create_sdk_mcp_server, tool
from docker.errors import DockerException, NotFound

# Initialize Docker client
try:
    docker_client = docker.from_env()
except DockerException as e:
    docker_client = None
    _docker_error = str(e)


@tool(
    "list_containers",
    "List Docker containers with their status",
    {"all": bool},
)
async def list_containers(args: dict[str, Any]) -> dict[str, Any]:
    """
    List Docker containers.

    Args:
        args: Dictionary with optional 'all' key:
            - all: If True, show all containers (including stopped)

    Returns:
        Dictionary with container list
    """
    if docker_client is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Docker client unavailable - {_docker_error}",
                }
            ]
        }

    try:
        show_all = args.get("all", False)
        containers = docker_client.containers.list(all=show_all)

        if not containers:
            message = "No containers found"
            if not show_all:
                message += " (use all=true to see stopped containers)"

            return {
                "content": [
                    {
                        "type": "text",
                        "text": message,
                    }
                ]
            }

        # Format container information
        container_info = []
        for container in containers:
            info = f"{container.name} ({container.status})"
            if hasattr(container, "attrs"):
                # Add image info if available
                image = container.attrs.get("Config", {}).get("Image", "")
                if image:
                    info += f" - Image: {image}"

            container_info.append(info)

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(container_info),
                }
            ]
        }

    except DockerException as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Docker error: {e}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error listing containers: {e}",
                }
            ]
        }


@tool(
    "container_logs",
    "Get logs from a Docker container",
    {"container": str, "tail": int},
)
async def container_logs(args: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve logs from a Docker container.

    Args:
        args: Dictionary with:
            - container: Container name or ID
            - tail: Number of lines to retrieve (optional, default: 100)

    Returns:
        Dictionary with container logs
    """
    if docker_client is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Docker client unavailable - {_docker_error}",
                }
            ]
        }

    container_name = args.get("container")
    if not container_name:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: container parameter is required",
                }
            ]
        }

    tail = args.get("tail", 100)

    # Validate tail parameter
    if not isinstance(tail, int) or tail < 1 or tail > 10000:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: tail must be an integer between 1 and 10000",
                }
            ]
        }

    try:
        container = docker_client.containers.get(container_name)
        logs = container.logs(tail=tail, timestamps=True).decode("utf-8")

        if not logs.strip():
            logs = f"No logs available for container '{container_name}'"

        return {
            "content": [
                {
                    "type": "text",
                    "text": logs,
                }
            ]
        }

    except NotFound:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Container '{container_name}' not found",
                }
            ]
        }
    except DockerException as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Docker error: {e}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error getting container logs: {e}",
                }
            ]
        }


@tool(
    "container_stats",
    "Get resource usage statistics for a Docker container",
    {"container": str},
)
async def container_stats(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get resource usage statistics for a container.

    Args:
        args: Dictionary with 'container' key (container name or ID)

    Returns:
        Dictionary with container statistics (CPU, memory, network, etc.)
    """
    if docker_client is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Docker client unavailable - {_docker_error}",
                }
            ]
        }

    container_name = args.get("container")
    if not container_name:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: container parameter is required",
                }
            ]
        }

    try:
        container = docker_client.containers.get(container_name)
        stats = container.stats(stream=False)

        # Extract key statistics
        cpu_stats = stats.get("cpu_stats", {})
        memory_stats = stats.get("memory_stats", {})
        network_stats = stats.get("networks", {})

        # Format stats for readability
        stats_text = [
            f"Container: {container_name}",
            f"Status: {container.status}",
            "",
            "Memory:",
            f"  Usage: {memory_stats.get('usage', 0)} bytes",
            f"  Limit: {memory_stats.get('limit', 0)} bytes",
            "",
            "CPU:",
            f"  System CPU usage: {cpu_stats.get('system_cpu_usage', 0)}",
            f"  Online CPUs: {cpu_stats.get('online_cpus', 0)}",
        ]

        if network_stats:
            stats_text.append("")
            stats_text.append("Network:")
            for interface, data in network_stats.items():
                stats_text.append(f"  {interface}:")
                stats_text.append(f"    RX bytes: {data.get('rx_bytes', 0)}")
                stats_text.append(f"    TX bytes: {data.get('tx_bytes', 0)}")

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(stats_text),
                }
            ]
        }

    except NotFound:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Container '{container_name}' not found",
                }
            ]
        }
    except DockerException as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Docker error: {e}",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error getting container stats: {e}",
                }
            ]
        }


# Create and export the MCP server
docker_server = create_sdk_mcp_server(
    name="docker",
    version="1.0.0",
    tools=[list_containers, container_logs, container_stats],
)
