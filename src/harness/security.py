"""Bash command security validation for autonomous mode.

This module provides security hooks to validate bash commands before execution.
Based on the pattern from claude-quickstarts/autonomous-coding/security.py.

Security Principles:
1. Allowlist approach - only known-safe commands are permitted
2. Blocklist for dangerous patterns - even in allowlisted commands
3. Validation of dangerous command arguments
4. Configurable bypass for trusted environments
"""

import re
import shlex
from collections.abc import Callable

# Commands that are allowed by default
ALLOWED_COMMANDS = frozenset({
    # Version control
    "git",
    "gh",  # GitHub CLI
    "glab",  # GitLab CLI

    # File operations (read-focused)
    "ls",
    "cat",
    "head",
    "tail",
    "find",
    "grep",
    "rg",  # ripgrep
    "wc",
    "diff",
    "tree",
    "eza",

    # Development tools
    "python",
    "python3",
    "pip",
    "pip3",
    "uv",
    "pytest",
    "mypy",
    "ruff",
    "node",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "bun",

    # Build tools
    "make",
    "cargo",
    "go",

    # Environment
    "cd",
    "pwd",
    "echo",
    "env",
    "which",
    "whoami",
    "date",
    "sleep",

    # Process management (limited)
    "ps",
    "top",
    "htop",
    "kill",
    "pkill",

    # Docker (limited)
    "docker",
    "docker-compose",

    # Utilities
    "curl",
    "wget",
    "jq",
    "yq",
    "sed",
    "awk",
    "sort",
    "uniq",
    "tr",
    "cut",
    "xargs",
    "tee",
    "true",
    "false",
    "test",
    "[",

    # Directory operations
    "mkdir",
    "touch",
    "cp",
    "mv",
    "ln",

    # Compression
    "tar",
    "gzip",
    "gunzip",
    "zip",
    "unzip",

    # Text editors (for scripted use)
    "ed",

    # Permissions (restricted via validation)
    "chmod",
    "chown",

    # Remove (restricted via validation)
    "rm",
    "rmdir",
})

# Patterns that are always blocked, even in allowed commands
BLOCKED_PATTERNS = [
    # Destructive filesystem operations
    r"rm\s+-[rf]*\s+/(?!workspace)",  # rm -rf outside /workspace
    r"rm\s+-[rf]*\s+~",  # rm -rf home directory
    r"rm\s+-[rf]*\s+\.\.",  # rm -rf parent directory

    # Dangerous chmod patterns
    r"chmod\s+777\s+/",  # chmod 777 at root
    r"chmod\s+-R\s+777",  # recursive chmod 777

    # System manipulation
    r"dd\s+.*of=/dev/",  # dd to device files
    r"mkfs\.",  # filesystem creation
    r"fdisk",  # disk partitioning
    r"mount\s+",  # mounting
    r"umount\s+",  # unmounting

    # Fork bombs and resource exhaustion
    r":\(\)\s*{\s*:\|:\s*&\s*}\s*;",  # bash fork bomb
    r"while\s+true.*done",  # infinite loops (basic pattern)

    # Network attacks
    r"nc\s+-l",  # netcat listener
    r"nmap\s+",  # network scanning

    # Credential exposure
    r"cat\s+.*\.env(?:\s|$)",  # reading .env files
    r"cat\s+.*/\.ssh/",  # reading SSH keys
    r"cat\s+.*/\.aws/",  # reading AWS credentials
    r"cat\s+.*/\.netrc",  # reading netrc

    # Dangerous git operations
    r"git\s+push\s+.*--force\s+origin\s+(?:main|master)",  # force push to main

    # Package manager attacks
    r"pip\s+install\s+--user",  # installing to user (potential override)
    r"npm\s+install\s+-g",  # global npm install

    # Sudo and privilege escalation
    r"sudo\s+",  # any sudo command
    r"su\s+-",  # switch user
    r"doas\s+",  # OpenBSD sudo alternative

    # Shell escape and injection
    r"\$\(.*\)",  # command substitution (can be dangerous)
    r"`.*`",  # backtick command substitution
]

# Compiled blocked patterns for performance
COMPILED_BLOCKED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


class CommandValidationError(Exception):
    """Raised when a command fails validation."""

    def __init__(self, command: str, reason: str) -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Command blocked: {reason}")


def get_base_command(command: str) -> str | None:
    """Extract the base command from a command line.

    Args:
        command: Full command line string

    Returns:
        Base command name or None if parsing fails
    """
    try:
        # Handle command prefixes like env vars
        parts = shlex.split(command)
        if not parts:
            return None

        # Skip environment variable assignments
        for part in parts:
            if "=" not in part:
                # Handle path prefixes
                if "/" in part:
                    return part.split("/")[-1]
                return part

        return None
    except ValueError:
        # shlex parsing failed, try basic split
        parts = command.strip().split()
        if parts:
            base = parts[0]
            if "/" in base:
                return base.split("/")[-1]
            return base
        return None


def validate_rm_command(command: str) -> bool:
    """Validate rm command is safe.

    Only allows rm within /workspace directory.

    Args:
        command: Full rm command

    Returns:
        True if safe, False otherwise
    """
    # Must explicitly target /workspace
    if "/workspace" not in command:
        return False

    # Check for recursive flags without workspace target
    if re.search(r"-[rf]*\s+/(?!workspace)", command):
        return False

    return True


def validate_chmod_command(command: str) -> bool:
    """Validate chmod command is safe.

    Blocks dangerous permission patterns.

    Args:
        command: Full chmod command

    Returns:
        True if safe, False otherwise
    """
    # Block 777 permissions
    if "777" in command:
        return False

    # Block recursive chmod on system directories
    if "-R" in command and not re.search(r"/workspace", command):
        return False

    return True


def validate_pkill_command(command: str) -> bool:
    """Validate pkill/kill command is safe.

    Only allows killing specific development processes.

    Args:
        command: Full pkill/kill command

    Returns:
        True if safe, False otherwise
    """
    safe_targets = ["node", "python", "npm", "pytest", "uvicorn", "gunicorn"]

    for target in safe_targets:
        if target in command.lower():
            return True

    # Allow kill with PID (numeric argument, with optional signal flag)
    if re.search(r"kill\s+(-\d+\s+)?\d+", command):
        return True

    return False


# Command-specific validators
COMMAND_VALIDATORS: dict[str, Callable[[str], bool]] = {
    "rm": validate_rm_command,
    "chmod": validate_chmod_command,
    "pkill": validate_pkill_command,
    "kill": validate_pkill_command,
}


def validate_command(
    command: str,
    allow_all: bool = False,
    additional_allowed: set[str] | None = None,
    additional_blocked_patterns: list[str] | None = None,
) -> tuple[bool, str]:
    """Validate a bash command for safety.

    Args:
        command: Command to validate
        allow_all: If True, bypass all checks (for trusted environments)
        additional_allowed: Additional commands to allow
        additional_blocked_patterns: Additional patterns to block

    Returns:
        Tuple of (is_valid, reason)
    """
    if allow_all:
        return True, "All commands allowed (allow_all=True)"

    command = command.strip()
    if not command:
        return False, "Empty command"

    # Check blocked patterns first
    patterns = COMPILED_BLOCKED_PATTERNS.copy()
    if additional_blocked_patterns:
        patterns.extend(re.compile(p, re.IGNORECASE) for p in additional_blocked_patterns)

    for pattern in patterns:
        if pattern.search(command):
            return False, f"Matches blocked pattern: {pattern.pattern}"

    # Get base command
    base_cmd = get_base_command(command)
    if not base_cmd:
        return False, "Could not parse command"

    # Check if command is allowed
    allowed = ALLOWED_COMMANDS.copy()
    if additional_allowed:
        allowed = allowed | additional_allowed

    if base_cmd not in allowed:
        return False, f"Command '{base_cmd}' not in allowlist"

    # Run command-specific validator if exists
    if base_cmd in COMMAND_VALIDATORS:
        validator = COMMAND_VALIDATORS[base_cmd]
        if not validator(command):
            return False, f"Command '{base_cmd}' failed specific validation"

    return True, "Command is allowed"


async def bash_security_hook(
    command: str,
    allow_all: bool = False,
) -> dict[str, str | bool]:
    """Async security hook for bash command validation.

    This is designed to integrate with Claude SDK hooks.

    Args:
        command: Command to validate
        allow_all: If True, bypass all checks

    Returns:
        Dict with 'allowed' (bool) and 'reason' (str)
    """
    is_valid, reason = validate_command(command, allow_all=allow_all)

    return {
        "allowed": is_valid,
        "reason": reason,
    }


def create_security_hook(allow_all: bool = False) -> Callable[[str], dict[str, str | bool]]:
    """Create a security hook with configured settings.

    Args:
        allow_all: If True, bypass all checks

    Returns:
        Synchronous security hook function
    """
    def hook(command: str) -> dict[str, str | bool]:
        is_valid, reason = validate_command(command, allow_all=allow_all)
        return {"allowed": is_valid, "reason": reason}

    return hook
