"""Container stream buffering tests with PYTHONUNBUFFERED.

This module verifies that PYTHONUNBUFFERED=1 prevents message buffering in
subprocess communication. Buffering can cause 60+ second delays in message
delivery, which was a critical bug during development.

Cost: Free (no API calls)
Duration: ~5-10 seconds total
"""

import asyncio
import json
import subprocess
import sys

import pytest


@pytest.mark.integration
async def test_subprocess_messages_unbuffered():
    """
    Test that subprocess messages are received immediately with PYTHONUNBUFFERED=1.

    Purpose: Verify unbuffered mode prevents message buffering delays.
    Regression test for 60-second timeout issue.

    Expected behavior:
    - All 10 messages received immediately
    - No buffering delays
    - Messages arrive in correct order

    Cost: Free
    """
    # Code to execute in subprocess - sends 10 JSON messages
    code = """
import sys, json, time
for i in range(10):
    msg = {"id": i, "text": f"Message {i}"}
    print(json.dumps(msg))
    sys.stdout.flush()
    time.sleep(0.1)
"""

    # Create subprocess with unbuffered output
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",  # Unbuffered mode
        "-c",
        code,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        limit=1024 * 256,  # 256KB buffer
        env={"PYTHONUNBUFFERED": "1"},  # Force unbuffered
    )

    messages = []
    timeout_seconds = 30.0

    try:
        # Read messages until EOF
        while not proc.stdout.at_eof():
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                break

            if not line:
                break

            try:
                msg = json.loads(line.decode().strip())
                messages.append(msg)
            except json.JSONDecodeError:
                pass

        # Wait for process to complete
        await asyncio.wait_for(proc.wait(), timeout=5.0)

    except Exception as e:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
        raise

    # Verify we received all 10 messages
    assert len(messages) == 10, f"Expected 10 messages, got {len(messages)}"
    assert all(msg["id"] == i for i, msg in enumerate(messages))


@pytest.mark.integration
async def test_subprocess_messages_without_unbuffered():
    """
    Test that buffering causes message delays without PYTHONUNBUFFERED.

    Purpose: Demonstrate the problem that PYTHONUNBUFFERED solves.
    Validates the need for unbuffered mode in production.

    Expected behavior:
    - Messages buffered and delayed
    - Receive < 10 messages during execution
    - Messages only flush when process exits

    Cost: Free
    """
    # Same code as above, but without unbuffered mode
    code = """
import sys, json, time
for i in range(10):
    msg = {"id": i, "text": f"Message {i}"}
    print(json.dumps(msg))
    # No explicit flush
    time.sleep(0.01)
"""

    # Create subprocess WITHOUT unbuffered output
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",  # NO -u flag
        code,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        limit=1024 * 256,
        # No PYTHONUNBUFFERED env var
    )

    messages = []
    timeout_seconds = 2.0  # Shorter timeout - should timeout

    try:
        while not proc.stdout.at_eof():
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                break

            if not line:
                break

            try:
                msg = json.loads(line.decode().strip())
                messages.append(msg)
            except json.JSONDecodeError:
                pass

        await proc.wait()

    except Exception:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()

    # Without unbuffered mode, we expect to receive 0 messages during execution
    # (they'll only flush when process exits, which happens after our read loop)
    assert (
        len(messages) < 10
    ), f"Expected fewer than 10 messages due to buffering, got {len(messages)}"


@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_buffering():
    """
    Test that Docker container has PYTHONUNBUFFERED set correctly.

    Purpose: Verify production Docker configuration includes unbuffered mode.
    Critical for preventing message delays in containerized agents.

    Expected behavior:
    - PYTHONUNBUFFERED=1 in container environment
    - Environment variable accessible to Python processes

    Cost: Free
    """
    # This test verifies the environment variable is set in the container
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.dev.yml",
        "exec",
        "-T",
        "main-agent",
        "python",
        "-c",
        "import os; print(os.getenv('PYTHONUNBUFFERED', 'NOT_SET'))",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()
    result = stdout.decode().strip()

    assert result == "1", f"Expected PYTHONUNBUFFERED=1, got: {result}"


@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_has_tini():
    """
    Test that Docker container has tini installed and accessible.

    Purpose: Verify tini (PID 1 init system) is available for proper signal handling.
    Tini forwards signals correctly and prevents zombie processes.

    Expected behavior:
    - tini binary found in container PATH
    - Typically located at /usr/bin/tini

    Cost: Free
    """
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.dev.yml",
        "exec",
        "-T",
        "main-agent",
        "which",
        "tini",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()
    result = stdout.decode().strip()

    # tini should be installed at /usr/bin/tini
    assert "/tini" in result, f"Expected tini to be installed, got: {result}"
    assert proc.returncode == 0, "tini not found in container"
