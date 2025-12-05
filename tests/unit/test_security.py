"""Unit tests for bash command security validation."""


from harness.security import (
    ALLOWED_COMMANDS,
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
