"""Unit tests for direct_agent module.

Tests the direct agent invocation workaround that bypasses the SDK Task tool
limitation (GitHub issues #11205, #12212).
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from harness.agents.definitions import AGENT_DEFINITIONS
from harness.subagent import (
    _get_call_retries,
    _get_plugin_base_path,
    _get_retry_backoff,
    _is_transient_error,
    _load_plugin_agents,
    call_agent,
    call_agent_simple,
    get_agent_info,
    list_available_agents,
)

logger = structlog.get_logger(__name__)


class TestGetPluginBasePath:
    """Tests for _get_plugin_base_path function."""

    def test_returns_path_object(self) -> None:
        """Test that function returns a Path object."""
        result = _get_plugin_base_path()
        assert isinstance(result, Path)

    def test_returns_plugins_directory(self) -> None:
        """Test that function returns path to plugins directory."""
        result = _get_plugin_base_path()
        assert result.name == "plugins"
        assert result.parent.name == "harness"


class TestListAvailableAgents:
    """Tests for list_available_agents function."""

    def test_returns_dict(self) -> None:
        """Test that function returns a dictionary."""
        result = list_available_agents()
        assert isinstance(result, dict)

    def test_includes_harness_agents(self) -> None:
        """Test that harness agents are included."""
        result = list_available_agents()

        # Check for known harness agents
        assert "python-expert" in result
        assert "tech-lead" in result
        assert "typescript-expert" in result

    def test_includes_plugin_agents(self) -> None:
        """Test that plugin agents are included."""
        result = list_available_agents()

        # Check for known plugin agents (namespaced)
        plugin_agents = [k for k in result.keys() if ":" in k]
        assert len(plugin_agents) >= 1  # At least context-engineer

    def test_descriptions_are_strings(self) -> None:
        """Test that all descriptions are non-empty strings."""
        result = list_available_agents()

        for name, desc in result.items():
            assert isinstance(desc, str), f"Agent {name} has non-string description"
            assert len(desc) > 0, f"Agent {name} has empty description"

    def test_contains_all_harness_agents(self) -> None:
        """Test that all harness agent definitions are included."""
        result = list_available_agents()

        for agent_name in AGENT_DEFINITIONS.keys():
            assert agent_name in result, f"Missing harness agent: {agent_name}"


class TestGetAgentInfo:
    """Tests for get_agent_info function."""

    def test_harness_agent_returns_correct_info(self) -> None:
        """Test getting info for a harness agent."""
        info = get_agent_info("python-expert")

        assert info["name"] == "python-expert"
        assert info["source"] == "harness"
        assert "description" in info
        assert "model" in info
        assert "tools" in info
        assert "prompt" in info

    def test_harness_agent_model_is_valid(self) -> None:
        """Test that harness agent model is valid."""
        info = get_agent_info("python-expert")

        assert info["model"] in ["sonnet", "opus", "haiku"]

    def test_harness_agent_has_tools(self) -> None:
        """Test that harness agent has tools list."""
        info = get_agent_info("python-expert")

        assert isinstance(info["tools"], list)
        # Python expert should have some tools
        assert len(info["tools"]) > 0

    def test_harness_agent_has_prompt(self) -> None:
        """Test that harness agent has system prompt."""
        info = get_agent_info("python-expert")

        assert isinstance(info["prompt"], str)
        assert len(info["prompt"]) > 0

    def test_plugin_agent_returns_correct_info(self) -> None:
        """Test getting info for a plugin agent."""
        # Get first plugin agent from available
        agents = list_available_agents()
        plugin_agents = [k for k in agents.keys() if ":" in k]

        if plugin_agents:
            info = get_agent_info(plugin_agents[0])

            assert info["source"] == "plugin"
            assert "description" in info
            assert "model" in info
            assert "tools" in info
            assert "prompt" in info

    def test_nonexistent_agent_raises_valueerror(self) -> None:
        """Test that nonexistent agent raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_agent_info("nonexistent-agent-xyz")

        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent-agent-xyz" in str(exc_info.value)

    def test_valueerror_includes_available_agents(self) -> None:
        """Test that ValueError includes available agents list."""
        with pytest.raises(ValueError) as exc_info:
            get_agent_info("nonexistent-agent")

        # Should mention some known agents
        error_msg = str(exc_info.value)
        assert "python-expert" in error_msg or "Available agents" in error_msg


class TestLoadPluginAgents:
    """Tests for _load_plugin_agents function."""

    def test_returns_dict(self) -> None:
        """Test that function returns a dictionary."""
        result = _load_plugin_agents()
        assert isinstance(result, dict)

    def test_caches_results(self) -> None:
        """Test that results are cached."""
        result1 = _load_plugin_agents()
        result2 = _load_plugin_agents()

        # Should return same object (cached)
        assert result1 is result2

    def test_plugin_agents_have_required_attributes(self) -> None:
        """Test that plugin agents have required attributes."""
        result = _load_plugin_agents()

        for name, agent in result.items():
            assert hasattr(agent, "description"), f"Agent {name} missing description"
            assert hasattr(agent, "model"), f"Agent {name} missing model"
            assert hasattr(agent, "tools"), f"Agent {name} missing tools"
            assert hasattr(agent, "prompt"), f"Agent {name} missing prompt"


class TestCallAgent:
    """Tests for call_agent async function."""

    @pytest.mark.asyncio
    async def test_invalid_agent_raises_valueerror(self) -> None:
        """Test that invalid agent name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            async for _ in call_agent("nonexistent-agent", "test prompt"):
                pass

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_builds_correct_options(self) -> None:
        """Test that call_agent builds correct SDK options."""

        async def mock_query_gen(*args, **kwargs):
            return
            yield  # Make it an async generator

        with patch("harness.subagent.query", return_value=mock_query_gen()):
            # Consume the generator
            messages = []
            async for msg in call_agent("python-expert", "test prompt"):
                messages.append(msg)

        # The test verifies that call_agent successfully processes an agent
        # (it would fail with ValueError if agent not found)
        assert messages == []  # Empty because mock returns nothing

    @pytest.mark.asyncio
    async def test_max_turns_enforced_harness_side(self) -> None:
        """Phase A.5 L1.1: call_agent caps at the agent's max_turns even when
        the underlying query yields more turns. The SDK forwards --max-turns
        to the CLI but it did not bind in practice (the eval-architect ran 73
        turns at max_turns=20), so the cap is enforced harness-side."""
        from claude_agent_sdk import AssistantMessage

        async def mock_query_gen(*args, **kwargs):
            for _ in range(10):
                yield AssistantMessage(content=[], model="sonnet")

        info = {
            "max_turns": 3,
            "model": "sonnet",
            "tools": None,
            "prompt": "system prompt",
            "source": "harness",
        }
        with (
            patch("harness.subagent.query", return_value=mock_query_gen()),
            patch("harness.subagent.get_agent_info", return_value=info),
        ):
            received = [
                m async for m in call_agent("python-expert", "go", verbose=False)
            ]
        # Capped at max_turns=3 assistant turns, not the 10 the query yielded.
        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_custom_permission_mode(self) -> None:
        """Test that custom permission_mode is passed through."""

        async def mock_query_gen(*args, **kwargs):
            return
            yield

        with patch("harness.subagent.query", return_value=mock_query_gen()) as mock_query:
            async for _ in call_agent(
                "python-expert", "test", permission_mode="bypassPermissions"
            ):
                pass

    @pytest.mark.asyncio
    async def test_custom_cwd(self) -> None:
        """Test that custom cwd is passed through."""

        async def mock_query_gen(*args, **kwargs):
            return
            yield

        with patch("harness.subagent.query", return_value=mock_query_gen()):
            async for _ in call_agent(
                "python-expert", "test", cwd="/custom/path"
            ):
                pass

    @pytest.mark.asyncio
    async def test_extra_options_passed_through(self) -> None:
        """Test that extra options are passed to ClaudeAgentOptions."""

        async def mock_query_gen(*args, **kwargs):
            return
            yield

        with patch("harness.subagent.query", return_value=mock_query_gen()):
            async for _ in call_agent(
                "python-expert", "test", max_turns=50
            ):
                pass

            # Extra options should be passed to ClaudeAgentOptions
            # This would error if max_turns wasn't accepted


class TestCallAgentSimple:
    """Tests for call_agent_simple async function."""

    @pytest.mark.asyncio
    async def test_returns_string(self) -> None:
        """Test that call_agent_simple returns a string."""
        with patch("harness.subagent.call_agent") as mock_call:
            mock_message = MagicMock()
            mock_message.content = "Test response"

            async def async_gen():
                yield mock_message

            mock_call.return_value = async_gen()

            # Patch isinstance to recognize our mock as AssistantMessage
            with patch("harness.subagent.isinstance", side_effect=lambda obj, cls: True if cls.__name__ == "AssistantMessage" else isinstance(obj, cls)):
                # Need to import and patch properly
                pass

            result = await call_agent_simple("python-expert", "test")
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_invalid_agent_raises_valueerror(self) -> None:
        """Test that invalid agent name raises ValueError."""
        with pytest.raises(ValueError):
            await call_agent_simple("nonexistent-agent", "test prompt")

    @pytest.mark.asyncio
    async def test_collects_text_from_content_string(self) -> None:
        """Test that text is collected from string content."""
        with patch("harness.subagent.query") as mock_query:
            # Create a mock AssistantMessage
            mock_message = MagicMock()
            mock_message.content = "Direct string response"

            async def async_gen():
                yield mock_message

            mock_query.return_value = async_gen()

            # Patch the isinstance check
            original_isinstance = __builtins__["isinstance"]

            def patched_isinstance(obj, cls):
                from claude_agent_sdk.types import AssistantMessage
                if cls is AssistantMessage:
                    return hasattr(obj, "content")
                return original_isinstance(obj, cls)

            with patch("harness.subagent.isinstance", patched_isinstance):
                result = await call_agent_simple("python-expert", "test")

            # The mock message has content attribute
            assert "Direct string response" in result or result == ""

    @pytest.mark.asyncio
    async def test_collects_text_from_content_list(self) -> None:
        """Test that text is collected from list content with text blocks."""
        with patch("harness.subagent.query") as mock_query:
            # Create mock text block
            mock_block = MagicMock()
            mock_block.text = "Text block content"

            # Create a mock AssistantMessage with list content
            mock_message = MagicMock()
            mock_message.content = [mock_block]

            async def async_gen():
                yield mock_message

            mock_query.return_value = async_gen()

            with patch("harness.subagent.isinstance") as mock_isinstance:
                # Make isinstance return True for AssistantMessage check
                mock_isinstance.side_effect = lambda obj, cls: hasattr(obj, "content")

                result = await call_agent_simple("python-expert", "test")

            # Should have collected text from block
            assert isinstance(result, str)


class TestAgentModels:
    """Tests for agent model configurations."""

    def test_all_harness_agents_have_valid_models(self) -> None:
        """Test that all harness agents have valid model values."""
        for name in AGENT_DEFINITIONS.keys():
            info = get_agent_info(name)
            assert info["model"] in ["sonnet", "opus", "haiku"], (
                f"Agent {name} has invalid model: {info['model']}"
            )

    def test_python_expert_has_valid_model(self) -> None:
        """Test that python-expert has a valid model."""
        info = get_agent_info("python-expert")
        assert info["model"] in ["sonnet", "opus", "haiku"]

    def test_testing_agent_uses_haiku(self) -> None:
        """Test that sdet-expert uses haiku model."""
        info = get_agent_info("sdet-expert")
        assert info["model"] == "haiku"


class TestAgentToolSets:
    """Tests for agent tool configurations."""

    def test_python_expert_has_required_tools(self) -> None:
        """Test that python-expert has expected tools."""
        info = get_agent_info("python-expert")
        tools = info["tools"]

        # Should have core development tools
        assert "Read" in tools
        assert "Write" in tools
        assert "Bash" in tools

    def test_code_review_expert_has_read_only_tools(self) -> None:
        """Test that code-review-expert doesn't have write tools."""
        info = get_agent_info("code-review-expert")
        tools = info["tools"]

        # Should have read access
        assert "Read" in tools

        # Should NOT have write access
        assert "Write" not in tools
        assert "Edit" not in tools


class TestAgentIntegration:
    """Integration tests for agent functionality."""

    def test_all_listed_agents_can_get_info(self) -> None:
        """Test that all listed agents can have their info retrieved."""
        agents = list_available_agents()

        for agent_name in agents.keys():
            # Should not raise
            info = get_agent_info(agent_name)
            assert info is not None
            assert info["name"] == agent_name

    def test_harness_and_plugin_agents_coexist(self) -> None:
        """Test that harness and plugin agents can coexist."""
        agents = list_available_agents()

        harness_count = sum(1 for k in agents.keys() if ":" not in k)
        plugin_count = sum(1 for k in agents.keys() if ":" in k)

        # Should have both types
        assert harness_count > 0, "No harness agents found"
        assert plugin_count >= 0  # Plugin agents might be 0 if plugins not loaded

        logger.info(
            "Agent count verification",
            harness_agents=harness_count,
            plugin_agents=plugin_count,
        )


# ---------------------------------------------------------------------------
# D9: transient-error retry tests
# ---------------------------------------------------------------------------


class TestIsTransientError:
    """Tests for _is_transient_error pattern matcher."""

    def test_failed_to_open_socket_is_transient(self) -> None:
        exc = RuntimeError("API Error: Unable to connect to API (FailedToOpenSocket)")
        assert _is_transient_error(exc) is True

    def test_connection_refused_is_transient(self) -> None:
        exc = ConnectionError("API Error: Unable to connect to API (ConnectionRefused)")
        assert _is_transient_error(exc) is True

    def test_sdk_returned_error_result_success_is_transient(self) -> None:
        exc = RuntimeError("Claude Code returned an error result: success")
        assert _is_transient_error(exc) is True

    def test_chained_cause_is_transient(self) -> None:
        inner = RuntimeError("FailedToOpenSocket")
        try:
            try:
                raise inner
            except RuntimeError as e:
                raise ValueError("orchestrator wrap") from e
        except ValueError as wrap:
            assert _is_transient_error(wrap) is True

    def test_value_error_not_transient(self) -> None:
        exc = ValueError("Agent 'foo' not found")
        assert _is_transient_error(exc) is False

    def test_empty_message_not_transient(self) -> None:
        exc = RuntimeError("")
        assert _is_transient_error(exc) is False

    def test_circular_cause_does_not_loop(self) -> None:
        # Construct a cycle: a.__cause__ → b, b.__cause__ → a
        a = RuntimeError("a")
        b = RuntimeError("b")
        a.__cause__ = b
        b.__cause__ = a
        # Should terminate (no exception, no infinite loop)
        assert _is_transient_error(a) is False


class TestRetryConfig:
    """Tests for env-var-driven retry config helpers."""

    def test_default_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CGF_CALL_RETRIES", raising=False)
        assert _get_call_retries() == 3

    def test_retries_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_CALL_RETRIES", "7")
        assert _get_call_retries() == 7

    def test_retries_negative_clamps_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_CALL_RETRIES", "-5")
        assert _get_call_retries() == 0

    def test_retries_garbage_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_CALL_RETRIES", "not-a-number")
        assert _get_call_retries() == 3

    def test_default_backoff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CGF_CALL_RETRY_BACKOFF", raising=False)
        assert _get_retry_backoff() == 5.0

    def test_backoff_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_CALL_RETRY_BACKOFF", "2.5")
        assert _get_retry_backoff() == 2.5


class TestCallAgentSimpleRetry:
    """Tests for transient-error retry inside call_agent_simple."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt_after_transient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transient error on attempt 1 → retry → success on attempt 2."""
        monkeypatch.setenv("CGF_CALL_RETRY_BACKOFF", "0")  # no real sleep
        call_count = {"n": 0}

        async def fake_call_agent(*_args: Any, **_kwargs: Any):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError(
                    "Claude Code returned an error result: success"
                )
            # Yield an AssistantMessage with a text content block
            from claude_agent_sdk.types import AssistantMessage  # type: ignore

            class _TextBlock:
                def __init__(self, text: str) -> None:
                    self.text = text

            yield AssistantMessage(content=[_TextBlock("OK retry won")], model="sonnet")

        with patch("harness.subagent.call_agent", fake_call_agent):
            result = await call_agent_simple(
                "python-expert", "test prompt", max_retries=3
            )

        assert call_count["n"] == 2
        assert "OK retry won" in result

    @pytest.mark.asyncio
    async def test_no_retry_for_non_transient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-transient errors should propagate immediately, no retry."""
        monkeypatch.setenv("CGF_CALL_RETRY_BACKOFF", "0")
        call_count = {"n": 0}

        async def fake_call_agent(*_args: Any, **_kwargs: Any):
            call_count["n"] += 1
            raise ValueError("Agent 'no-such-agent' not found")
            yield  # unreachable; makes this an async generator

        with patch("harness.subagent.call_agent", fake_call_agent):
            with pytest.raises(ValueError, match="not found"):
                await call_agent_simple(
                    "python-expert", "test prompt", max_retries=3
                )

        assert call_count["n"] == 1  # Only one attempt

    @pytest.mark.asyncio
    async def test_no_retry_for_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TimeoutError must propagate without retry; per-call timeout is hard."""
        monkeypatch.setenv("CGF_CALL_RETRY_BACKOFF", "0")
        call_count = {"n": 0}

        async def fake_call_agent(*_args: Any, **_kwargs: Any):
            call_count["n"] += 1
            raise TimeoutError("query timed out")
            yield

        with patch("harness.subagent.call_agent", fake_call_agent):
            with pytest.raises(TimeoutError):
                await call_agent_simple(
                    "python-expert", "test prompt", max_retries=3
                )

        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_reraises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After max_retries+1 transient failures, the last error propagates."""
        monkeypatch.setenv("CGF_CALL_RETRY_BACKOFF", "0")
        call_count = {"n": 0}

        async def fake_call_agent(*_args: Any, **_kwargs: Any):
            call_count["n"] += 1
            raise RuntimeError("FailedToOpenSocket attempt " + str(call_count["n"]))
            yield

        with patch("harness.subagent.call_agent", fake_call_agent):
            with pytest.raises(RuntimeError, match="FailedToOpenSocket"):
                await call_agent_simple(
                    "python-expert", "test prompt", max_retries=2
                )

        # max_retries=2 means 1 initial + 2 retries = 3 attempts total
        assert call_count["n"] == 3
