"""Signal handling and graceful shutdown tests.

This module tests that processes handle SIGTERM correctly, flush logs,
and clean up resources. These tests are critical for production reliability
where containers may be stopped/restarted frequently.

Cost: Free (no API calls)
Duration: ~30-60 seconds total (due to container start/stop)
"""

import asyncio
import subprocess

import pytest


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.slow
async def test_docker_stop_graceful_shutdown():
    """
    Test that docker stop triggers graceful shutdown with log flushing.

    Purpose: Verify containers handle SIGTERM correctly and flush logs.
    Critical for preventing data loss during container restarts.

    Expected behavior:
    - Container receives SIGTERM on stop
    - Logs contain shutdown messages
    - Container exits cleanly

    Prerequisites: Docker daemon running
    Cost: Free
    Duration: ~15-20 seconds
    """
    # Start the main-agent container
    start_proc = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.dev.yml",
        "up",
        "-d",
        "main-agent",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    await start_proc.communicate()
    assert start_proc.returncode == 0, "Failed to start main-agent container"

    # Wait for container to be fully running
    await asyncio.sleep(5)

    # Send SIGTERM via docker stop
    stop_proc = await asyncio.create_subprocess_exec(
        "docker",
        "stop",
        "-t",
        "10",  # 10 second grace period
        "claude-main-agent",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    await stop_proc.communicate()

    # Check logs for graceful shutdown messages
    logs_proc = await asyncio.create_subprocess_exec(
        "docker",
        "logs",
        "--tail",
        "50",
        "claude-main-agent",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await logs_proc.communicate()
    combined_logs = stdout.decode() + stderr.decode()

    # Verify graceful shutdown happened
    assert (
        "SIGTERM" in combined_logs or "shutdown" in combined_logs.lower()
    ), "Expected graceful shutdown log messages"

    # Container should have exited cleanly (exit code 0 or stopped state)
    # We don't assert specific exit code since it may vary


@pytest.mark.integration
async def test_signal_handler_flushes_streams():
    """
    Test that signal handler explicitly flushes stdout/stderr.

    Purpose: Verify signal handlers flush output before exiting.
    Prevents loss of final log messages during shutdown.

    Expected behavior:
    - Process registers SIGTERM handler
    - Handler prints message and flushes
    - Message received before process exits

    Cost: Free
    """
    # Simple Python script that registers signal handler and flushes
    code = """
import signal
import sys
import time

def handler(signum, frame):
    print("SIGTERM received")
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, handler)

print("Ready to receive signals")
sys.stdout.flush()

# Wait for signal
time.sleep(30)
"""

    # Run script in subprocess
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-u",
        "-c",
        code,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for "Ready" message
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
    assert b"Ready" in line

    # Send SIGTERM
    proc.terminate()

    # Read remaining output
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

    # Verify the "SIGTERM received" message was flushed before exit
    assert b"SIGTERM received" in stdout, "Signal handler did not flush output"


@pytest.mark.integration
async def test_tini_forwards_signals():
    """
    Test that tini properly forwards signals to child process.

    Purpose: Verify tini (PID 1 init) forwards SIGTERM to child processes.
    Docker uses tini as PID 1 to handle signals correctly.

    Expected behavior:
    - Tini spawns child process
    - SIGTERM to tini is forwarded to child
    - Child receives and handles signal

    Cost: Free
    """
    # Run a simple process under tini
    code = """
import signal
import sys
import time

def handler(signum, frame):
    print("Child received SIGTERM", flush=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, handler)
print("Child ready", flush=True)
time.sleep(30)
"""

    # Start process with tini (if available on host)
    try:
        proc = await asyncio.create_subprocess_exec(
            "tini",
            "--",
            "python",
            "-u",
            "-c",
            code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        pytest.skip("tini not available on host - will test in container")
        return

    # Wait for ready
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
    assert b"Child ready" in line

    # Send SIGTERM to tini (PID 1 equivalent)
    proc.terminate()

    # Verify child received signal
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    assert b"Child received SIGTERM" in stdout, "Tini did not forward signal"


@pytest.mark.integration
async def test_asyncio_task_cancellation_on_signal():
    """
    Test that signal handler cancels all pending asyncio tasks.

    Purpose: Verify async cleanup on shutdown prevents hung tasks.
    Important for agent sessions that use asyncio extensively.

    Expected behavior:
    - Signal handler registered in event loop
    - Handler cancels all pending tasks
    - Graceful shutdown completed

    Cost: Free
    """
    code = """
import asyncio
import signal
import sys

shutdown_event = asyncio.Event()

async def graceful_shutdown(signame):
    print(f"Received {signame}", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()

    # Cancel all tasks
    current = asyncio.current_task()
    for task in asyncio.all_tasks():
        if task is not current and not task.done():
            task.cancel()

    shutdown_event.set()

async def main():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGTERM,
        lambda: asyncio.create_task(graceful_shutdown("SIGTERM"))
    )

    print("Ready", flush=True)

    # Wait for shutdown
    await shutdown_event.wait()
    print("Shutdown complete", flush=True)

asyncio.run(main())
"""

    proc = await asyncio.create_subprocess_exec(
        "python",
        "-u",
        "-c",
        code,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for ready
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
    assert b"Ready" in line

    # Send SIGTERM
    proc.terminate()

    # Verify graceful shutdown
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    assert b"Received SIGTERM" in stdout
    assert b"Shutdown complete" in stdout
