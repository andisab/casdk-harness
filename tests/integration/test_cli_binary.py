"""Claude CLI binary and subprocess spawning tests.

This module tests the Claude CLI binary directly, bypassing the SDK to isolate
subprocess communication issues. These tests verify that the CLI can be found,
executed, and communicated with via stdin/stdout.

Cost: Free (no API calls)
Duration: < 5 seconds total
"""

import os
import shutil
import subprocess
import sys


def test_claude_cli_exists():
    """
    Test that Claude CLI binary exists and is executable.

    Purpose: Verify the Claude CLI is properly installed and accessible in PATH.
    This is a prerequisite for all SDK operations.

    Expected behavior:
    - CLI binary found in PATH
    - Binary has executable permissions

    Cost: Free
    """
    print("\n" + "=" * 80)
    print("TEST: Claude CLI binary exists")
    print("=" * 80)

    # Find claude binary
    claude_path = shutil.which("claude")

    if claude_path:
        print(f"✓ Found claude at: {claude_path}")

        # Check if executable
        if os.access(claude_path, os.X_OK):
            print("✓ Claude is executable")
        else:
            print("✗ Claude is not executable")
            return False
    else:
        print("✗ Claude not found in PATH")
        print(f"PATH: {os.environ.get('PATH')}")
        return False

    print("✓ TEST PASSED\n")
    return True


def test_claude_cli_version():
    """
    Test that Claude CLI can run and return version.

    Purpose: Verify CLI can execute basic commands without hanging.

    Expected behavior:
    - CLI responds to --version flag
    - Exits with code 0
    - Returns version string

    Cost: Free
    """
    print("=" * 80)
    print("TEST: Claude CLI --version")
    print("=" * 80)

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        print(f"Exit code: {result.returncode}")
        print(f"Stdout: {result.stdout.strip()}")
        print(f"Stderr: {result.stderr.strip()}")

        if result.returncode == 0:
            print("✓ TEST PASSED\n")
            return True
        else:
            print("✗ TEST FAILED\n")
            return False

    except subprocess.TimeoutExpired:
        print("✗ TEST FAILED: Timeout")
        return False
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        return False


def test_claude_cli_subprocess_spawn():
    """
    Test that we can spawn Claude CLI as subprocess with stdin/stdout.

    Purpose: Verify subprocess spawning works for interactive communication.
    This tests the core subprocess pattern used by the SDK.

    Expected behavior:
    - Process spawns successfully
    - Process stays alive (doesn't crash immediately)
    - Process responds to termination signals

    Cost: Free
    """
    print("=" * 80)
    print("TEST: Spawn Claude CLI subprocess with stdin/stdout")
    print("=" * 80)

    try:
        # Spawn Claude CLI process
        proc = subprocess.Popen(
            ["claude"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
        )

        print(f"✓ Process spawned with PID: {proc.pid}")

        # Wait briefly to see if process crashes immediately
        try:
            proc.wait(timeout=2)
            print(f"✗ Process exited immediately with code: {proc.returncode}")
            print(f"Stderr: {proc.stderr.read()}")
            return False
        except subprocess.TimeoutExpired:
            print("✓ Process is still running after 2 seconds")

        # Try to terminate gracefully
        proc.terminate()
        try:
            proc.wait(timeout=2)
            print(f"✓ Process terminated with code: {proc.returncode}")
        except subprocess.TimeoutExpired:
            print("⚠ Process did not terminate, killing...")
            proc.kill()
            proc.wait()

        print("✓ TEST PASSED\n")
        return True

    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_environment():
    """
    Test environment variables required for SDK operation.

    Purpose: Verify all required environment variables are set correctly.

    Expected behavior:
    - ANTHROPIC_API_KEY is set (redacted in output)
    - HOME and PATH are configured
    - Environment is suitable for SDK operation

    Cost: Free
    """
    print("=" * 80)
    print("TEST: Environment variables")
    print("=" * 80)

    required_vars = {
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
        "HOME": os.environ.get("HOME"),
        "PATH": os.environ.get("PATH"),
    }

    all_present = True
    for var, value in required_vars.items():
        if value:
            if var == "ANTHROPIC_API_KEY":
                print(f"✓ {var}: {value[:10]}... ({len(value)} chars)")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: NOT SET")
            all_present = False

    if all_present:
        print("✓ TEST PASSED\n")
    else:
        print("✗ TEST FAILED\n")

    return all_present


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Claude CLI Subprocess Diagnostic Tests")
    print("=" * 80)

    results = {
        "Environment": test_environment(),
        "CLI exists": test_claude_cli_exists(),
        "CLI version": test_claude_cli_version(),
        "CLI subprocess": test_claude_cli_subprocess_spawn(),
    }

    print("\n" + "=" * 80)
    print("Test Results Summary")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    print("=" * 80)

    # Exit with error code if any test failed
    if not all(results.values()):
        sys.exit(1)
