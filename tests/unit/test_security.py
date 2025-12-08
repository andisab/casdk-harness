"""Unit tests for bash command security validation."""

import pytest

from harness.security import (
    ALLOWED_COMMANDS,
    BLOCKED_PATTERNS,
    COMMAND_VALIDATORS,
    COMPILED_BLOCKED_PATTERNS,
    CommandValidationError,
    bash_security_hook,
    create_security_hook,
    get_base_command,
    validate_chmod_command,
    validate_command,
    validate_pkill_command,
    validate_rm_command,
)


class TestGetBaseCommand:
    """Tests for base command extraction."""

    def test_simple_command(self) -> None:
        """Test extracting base command from simple command."""
        assert get_base_command("ls -la") == "ls"
        assert get_base_command("git status") == "git"
        assert get_base_command("python script.py") == "python"

    def test_path_command(self) -> None:
        """Test extracting base command from full path."""
        assert get_base_command("/usr/bin/python script.py") == "python"
        assert get_base_command("/bin/bash -c 'echo hello'") == "bash"

    def test_env_var_prefix(self) -> None:
        """Test extracting command with environment variable prefix."""
        assert get_base_command("FOO=bar python script.py") == "python"
        assert get_base_command("DEBUG=1 LOG_LEVEL=debug npm start") == "npm"

    def test_empty_command(self) -> None:
        """Test empty command returns None."""
        assert get_base_command("") is None
        assert get_base_command("   ") is None


class TestValidateRmCommand:
    """Tests for rm command validation."""

    def test_rm_in_workspace_allowed(self) -> None:
        """Test rm in workspace directory is allowed."""
        assert validate_rm_command("rm /workspace/temp.txt") is True
        assert validate_rm_command("rm -rf /workspace/node_modules") is True
        assert validate_rm_command("rm -r /workspace/build/") is True

    def test_rm_outside_workspace_blocked(self) -> None:
        """Test rm outside workspace is blocked."""
        assert validate_rm_command("rm /etc/passwd") is False
        assert validate_rm_command("rm -rf /") is False
        assert validate_rm_command("rm -rf ~") is False
        assert validate_rm_command("rm temp.txt") is False  # No explicit /workspace


class TestValidateChmodCommand:
    """Tests for chmod command validation."""

    def test_normal_chmod_allowed(self) -> None:
        """Test normal chmod commands are allowed."""
        assert validate_chmod_command("chmod 755 script.sh") is True
        assert validate_chmod_command("chmod +x script.sh") is True
        assert validate_chmod_command("chmod 644 config.txt") is True

    def test_chmod_777_blocked(self) -> None:
        """Test chmod 777 is blocked."""
        assert validate_chmod_command("chmod 777 /workspace/file") is False
        assert validate_chmod_command("chmod -R 777 /workspace") is False

    def test_recursive_chmod_outside_workspace_blocked(self) -> None:
        """Test recursive chmod outside workspace is blocked."""
        assert validate_chmod_command("chmod -R 755 /etc") is False
        assert validate_chmod_command("chmod -R 644 /var/log") is False


class TestValidatePkillCommand:
    """Tests for pkill/kill command validation."""

    def test_safe_process_targets_allowed(self) -> None:
        """Test killing safe development processes is allowed."""
        assert validate_pkill_command("pkill node") is True
        assert validate_pkill_command("pkill python") is True
        assert validate_pkill_command("pkill npm") is True
        assert validate_pkill_command("pkill pytest") is True
        assert validate_pkill_command("pkill uvicorn") is True

    def test_kill_with_pid_allowed(self) -> None:
        """Test kill with numeric PID is allowed."""
        assert validate_pkill_command("kill 12345") is True
        assert validate_pkill_command("kill -9 12345") is True

    def test_unsafe_targets_blocked(self) -> None:
        """Test killing system processes is blocked."""
        assert validate_pkill_command("pkill init") is False
        assert validate_pkill_command("pkill systemd") is False
        assert validate_pkill_command("pkill sshd") is False


class TestValidateCommand:
    """Tests for main command validation function."""

    def test_allowed_commands_pass(self) -> None:
        """Test that allowed commands pass validation."""
        allowed_examples = [
            "ls -la",
            "git status",
            "git commit -m 'test'",
            "python script.py",
            "npm install",
            "docker ps",
            "make build",
            "pytest tests/",
            "ruff check .",
            "cat file.txt",
            "grep pattern file.txt",
        ]

        for cmd in allowed_examples:
            is_valid, reason = validate_command(cmd)
            assert is_valid, f"Command '{cmd}' should be allowed: {reason}"

    def test_blocked_patterns(self) -> None:
        """Test that blocked patterns are caught."""
        blocked_examples = [
            "rm -rf /",
            "rm -rf /etc",
            "chmod 777 /workspace/file",
            "dd if=/dev/zero of=/dev/sda",
            "sudo rm -rf /",
            "cat /home/user/.ssh/id_rsa",
            "cat .env",
            "git push --force origin main",
            "npm install -g malware",
        ]

        for cmd in blocked_examples:
            is_valid, reason = validate_command(cmd)
            assert not is_valid, f"Command '{cmd}' should be blocked: {reason}"

    def test_unknown_commands_blocked(self) -> None:
        """Test that unknown commands are blocked."""
        unknown_examples = [
            "hackertool --exploit",
            "malware",
            "cryptominer start",
        ]

        for cmd in unknown_examples:
            is_valid, reason = validate_command(cmd)
            assert not is_valid, f"Command '{cmd}' should be blocked"
            assert "not in allowlist" in reason

    def test_allow_all_bypasses_checks(self) -> None:
        """Test that allow_all=True bypasses all checks."""
        is_valid, reason = validate_command("rm -rf /", allow_all=True)
        assert is_valid
        assert "allow_all=True" in reason

    def test_additional_allowed_commands(self) -> None:
        """Test adding custom allowed commands."""
        is_valid, _ = validate_command("customtool --version")
        assert not is_valid

        is_valid, _ = validate_command(
            "customtool --version",
            additional_allowed={"customtool"},
        )
        assert is_valid

    def test_additional_blocked_patterns(self) -> None:
        """Test adding custom blocked patterns."""
        is_valid, _ = validate_command("git commit -m 'FIXME'")
        assert is_valid

        is_valid, reason = validate_command(
            "git commit -m 'FIXME'",
            additional_blocked_patterns=["FIXME"],
        )
        assert not is_valid
        assert "blocked pattern" in reason


class TestBlockedPatterns:
    """Tests for specific blocked patterns."""

    def test_fork_bomb_blocked(self) -> None:
        """Test that fork bomb patterns are blocked."""
        # Note: This tests the pattern, actual fork bomb syntax may vary
        is_valid, _ = validate_command(":(){ :|:& };:")
        assert not is_valid

    def test_netcat_listener_blocked(self) -> None:
        """Test that netcat listener is blocked."""
        is_valid, _ = validate_command("nc -l 4444")
        assert not is_valid

    def test_credential_access_blocked(self) -> None:
        """Test that accessing credentials is blocked."""
        credentials_cmds = [
            "cat ~/.ssh/id_rsa",
            "cat /home/user/.aws/credentials",
            "cat .env",
            "cat /root/.netrc",
        ]

        for cmd in credentials_cmds:
            is_valid, _ = validate_command(cmd)
            assert not is_valid, f"Credential access '{cmd}' should be blocked"


class TestAllowedCommandsList:
    """Tests for the allowed commands list."""

    def test_essential_commands_allowed(self) -> None:
        """Test that essential development commands are in the allowlist."""
        essential = [
            "git", "ls", "cat", "grep", "python", "pip", "npm", "node",
            "make", "docker", "curl", "jq", "mkdir", "cp", "mv",
        ]

        for cmd in essential:
            assert cmd in ALLOWED_COMMANDS, f"{cmd} should be in ALLOWED_COMMANDS"

    def test_dangerous_commands_not_allowed(self) -> None:
        """Test that dangerous commands are not in the base allowlist."""
        dangerous = [
            "sudo", "su", "shutdown", "reboot", "init", "systemctl",
            "iptables", "nc",
        ]

        for cmd in dangerous:
            assert cmd not in ALLOWED_COMMANDS, f"{cmd} should NOT be in ALLOWED_COMMANDS"


class TestCommandValidationError:
    """Tests for CommandValidationError exception."""

    def test_stores_command_and_reason(self) -> None:
        """Exception stores command and reason attributes."""
        error = CommandValidationError("rm -rf /", "Dangerous command")
        assert error.command == "rm -rf /"
        assert error.reason == "Dangerous command"

    def test_message_format(self) -> None:
        """Exception message includes reason."""
        error = CommandValidationError("sudo rm", "sudo blocked")
        assert "Command blocked: sudo blocked" in str(error)

    def test_inherits_from_exception(self) -> None:
        """CommandValidationError inherits from Exception."""
        error = CommandValidationError("cmd", "reason")
        assert isinstance(error, Exception)


class TestCompiledPatterns:
    """Tests for compiled blocked patterns."""

    def test_patterns_compiled(self) -> None:
        """Blocked patterns are pre-compiled for performance."""
        assert len(COMPILED_BLOCKED_PATTERNS) == len(BLOCKED_PATTERNS)

    def test_compiled_patterns_are_regex(self) -> None:
        """Compiled patterns are regex Pattern objects."""
        import re
        for pattern in COMPILED_BLOCKED_PATTERNS:
            assert hasattr(pattern, "search")
            assert hasattr(pattern, "pattern")

    def test_command_validators_dict_populated(self) -> None:
        """COMMAND_VALIDATORS dict has expected validators."""
        assert "rm" in COMMAND_VALIDATORS
        assert "chmod" in COMMAND_VALIDATORS
        assert "pkill" in COMMAND_VALIDATORS
        assert "kill" in COMMAND_VALIDATORS
        assert callable(COMMAND_VALIDATORS["rm"])


class TestBashSecurityHook:
    """Tests for bash_security_hook() async function."""

    @pytest.mark.asyncio
    async def test_valid_command_returns_allowed(self) -> None:
        """Valid command returns allowed=True."""
        result = await bash_security_hook("git status")
        assert result["allowed"] is True
        assert "reason" in result

    @pytest.mark.asyncio
    async def test_invalid_command_returns_blocked(self) -> None:
        """Invalid command returns allowed=False."""
        result = await bash_security_hook("sudo rm -rf /")
        assert result["allowed"] is False
        assert "reason" in result

    @pytest.mark.asyncio
    async def test_allow_all_bypasses(self) -> None:
        """allow_all=True bypasses all checks."""
        result = await bash_security_hook("sudo rm -rf /", allow_all=True)
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self) -> None:
        """Returns dict with 'allowed' and 'reason' keys."""
        result = await bash_security_hook("ls")
        assert "allowed" in result
        assert "reason" in result
        assert isinstance(result["allowed"], bool)
        assert isinstance(result["reason"], str)

    @pytest.mark.asyncio
    async def test_empty_command_blocked(self) -> None:
        """Empty command is blocked."""
        result = await bash_security_hook("")
        assert result["allowed"] is False


class TestCreateSecurityHook:
    """Tests for create_security_hook() factory function."""

    def test_creates_callable(self) -> None:
        """Creates a callable hook function."""
        hook = create_security_hook()
        assert callable(hook)

    def test_hook_validates_commands(self) -> None:
        """Created hook validates commands correctly."""
        hook = create_security_hook()
        result = hook("git status")
        assert result["allowed"] is True

    def test_hook_blocks_dangerous_commands(self) -> None:
        """Created hook blocks dangerous commands."""
        hook = create_security_hook()
        result = hook("sudo rm -rf /")
        assert result["allowed"] is False

    def test_allow_all_creates_permissive_hook(self) -> None:
        """allow_all=True creates permissive hook."""
        hook = create_security_hook(allow_all=True)
        result = hook("sudo rm -rf /")
        assert result["allowed"] is True

    def test_hook_returns_dict(self) -> None:
        """Hook returns dict with expected keys."""
        hook = create_security_hook()
        result = hook("echo hello")
        assert isinstance(result, dict)
        assert "allowed" in result
        assert "reason" in result


class TestAdditionalBlockedPatterns:
    """Tests for additional blocked patterns not covered above."""

    def test_nmap_blocked(self) -> None:
        """nmap scanning is blocked."""
        is_valid, _ = validate_command("nmap 192.168.1.0/24")
        assert not is_valid

    def test_su_switch_user_blocked(self) -> None:
        """su - is blocked."""
        is_valid, _ = validate_command("su - root")
        assert not is_valid

    def test_doas_blocked(self) -> None:
        """doas (OpenBSD sudo) is blocked."""
        is_valid, _ = validate_command("doas apt update")
        assert not is_valid

    def test_mount_blocked(self) -> None:
        """mount command is blocked."""
        is_valid, _ = validate_command("mount /dev/sda1 /mnt")
        assert not is_valid

    def test_umount_blocked(self) -> None:
        """umount command is blocked."""
        is_valid, _ = validate_command("umount /mnt")
        assert not is_valid

    def test_mkfs_blocked(self) -> None:
        """mkfs filesystem creation is blocked."""
        is_valid, _ = validate_command("mkfs.ext4 /dev/sda1")
        assert not is_valid

    def test_fdisk_blocked(self) -> None:
        """fdisk partitioning is blocked."""
        is_valid, _ = validate_command("fdisk /dev/sda")
        assert not is_valid

    def test_command_substitution_blocked(self) -> None:
        """Command substitution $() is blocked."""
        is_valid, _ = validate_command("echo $(whoami)")
        assert not is_valid

    def test_backtick_substitution_blocked(self) -> None:
        """Backtick substitution is blocked."""
        is_valid, _ = validate_command("echo `whoami`")
        assert not is_valid

    def test_pip_install_user_blocked(self) -> None:
        """pip install --user is blocked."""
        is_valid, _ = validate_command("pip install --user package")
        assert not is_valid

    def test_git_force_push_master_blocked(self) -> None:
        """git push --force origin master is blocked."""
        is_valid, _ = validate_command("git push --force origin master")
        assert not is_valid


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_shlex_failure_fallback(self) -> None:
        """Falls back to split on shlex parse failure."""
        # Unbalanced quotes cause shlex failure
        result = get_base_command('echo "unclosed')
        assert result == "echo"

    def test_only_env_vars_no_command(self) -> None:
        """Returns None when only env vars present."""
        assert get_base_command("A=1 B=2") is None

    def test_command_with_many_env_vars(self) -> None:
        """Extracts command after multiple env vars."""
        assert get_base_command("A=1 B=2 C=3 D=4 python") == "python"

    def test_validate_command_strips_whitespace(self) -> None:
        """validate_command strips leading/trailing whitespace."""
        is_valid, _ = validate_command("  ls -la  ")
        assert is_valid is True

    def test_case_insensitive_pattern_matching(self) -> None:
        """Blocked patterns match case-insensitively."""
        is_valid, _ = validate_command("SUDO apt install")
        assert not is_valid

    def test_rm_with_multiple_workspace_paths(self) -> None:
        """rm validates with multiple workspace paths."""
        assert validate_rm_command("rm /workspace/a /workspace/b") is True

    def test_recursive_chmod_in_workspace_allowed(self) -> None:
        """Recursive chmod in workspace is allowed."""
        assert validate_chmod_command("chmod -R 755 /workspace/src") is True

    def test_kill_with_signal_flag(self) -> None:
        """kill with -15 signal is allowed."""
        assert validate_pkill_command("kill -15 54321") is True

    def test_pkill_gunicorn_allowed(self) -> None:
        """pkill gunicorn is allowed."""
        assert validate_pkill_command("pkill gunicorn") is True

    def test_empty_command_validation(self) -> None:
        """Empty command fails validation."""
        is_valid, reason = validate_command("")
        assert not is_valid
        assert "empty" in reason.lower()

    def test_whitespace_only_command(self) -> None:
        """Whitespace-only command fails validation."""
        is_valid, _ = validate_command("   ")
        assert not is_valid

    def test_allowed_commands_is_frozenset(self) -> None:
        """ALLOWED_COMMANDS is immutable frozenset."""
        assert isinstance(ALLOWED_COMMANDS, frozenset)

    def test_path_with_multiple_segments(self) -> None:
        """Extracts command from deep path."""
        assert get_base_command("/a/b/c/d/node") == "node"

    def test_relative_path_command(self) -> None:
        """Extracts command from relative path."""
        assert get_base_command("./script.sh") == "script.sh"


class TestSpecificValidators:
    """Tests for command-specific validators."""

    def test_rm_validator_is_called(self) -> None:
        """rm validator is called for rm commands."""
        # rm without workspace fails specific validation
        is_valid, reason = validate_command("rm important.txt")
        assert not is_valid
        assert "failed specific validation" in reason.lower()

    def test_chmod_validator_is_called(self) -> None:
        """chmod validator is called for chmod commands."""
        # chmod 777 fails specific validation
        is_valid, reason = validate_command("chmod 777 file.txt")
        assert not is_valid

    def test_kill_validator_is_called(self) -> None:
        """kill validator is called for kill commands."""
        # pkill without safe target fails
        is_valid, reason = validate_command("pkill systemd")
        assert not is_valid

    def test_validator_passes_for_safe_commands(self) -> None:
        """Validators pass for safe commands."""
        assert validate_command("rm /workspace/temp")[0] is True
        assert validate_command("chmod 755 file.sh")[0] is True
        assert validate_command("pkill node")[0] is True
        assert validate_command("kill 12345")[0] is True
