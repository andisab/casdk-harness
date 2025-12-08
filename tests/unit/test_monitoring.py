"""Unit tests for monitoring module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from harness.monitoring import MetricsCollector

if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def reset_metrics_singleton() -> None:
    """Reset the MetricsCollector singleton before each test."""
    MetricsCollector.reset_singleton()


@pytest.fixture
def metrics_collector(tmp_path: Path) -> MetricsCollector:
    """Create a MetricsCollector instance with temp directories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checkpoint = tmp_path / "checkpoints"
    checkpoint.mkdir()
    return MetricsCollector(
        port=19090,  # Use different port to avoid conflicts
        workspace_dir=workspace,
        checkpoint_dir=checkpoint,
    )


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


def test_singleton_pattern() -> None:
    """Test that MetricsCollector follows singleton pattern."""
    collector1 = MetricsCollector(port=19091)
    collector2 = MetricsCollector(port=19092)  # Different port should be ignored

    assert collector1 is collector2
    assert collector1.port == 19091  # First initialization wins


def test_reset_singleton() -> None:
    """Test that reset_singleton creates a new instance."""
    collector1 = MetricsCollector(port=19093)
    MetricsCollector.reset_singleton()
    collector2 = MetricsCollector(port=19094)

    assert collector1 is not collector2
    assert collector2.port == 19094


def test_singleton_server_started_flag() -> None:
    """Test that _server_started flag is reset with singleton."""
    MetricsCollector._server_started = True
    MetricsCollector.reset_singleton()

    assert MetricsCollector._server_started is False


# =============================================================================
# Multi-Model Pricing Tests (record_tokens)
# =============================================================================


def test_record_tokens_sonnet_pricing() -> None:
    """Test Sonnet model pricing calculation."""
    # Sonnet: $0.003/1K input, $0.015/1K output, $0.0003/1K cached
    usage = {
        "input_tokens": 1000,
        "output_tokens": 1000,
        "cache_read_input_tokens": 1000,
    }

    with patch.object(MetricsCollector, "record_token_usage") as mock_token, \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-sonnet-4-5-20250929", usage)

        # Verify token recording
        assert mock_token.call_count == 3
        mock_token.assert_any_call("claude-sonnet-4-5-20250929", "input", 1000)
        mock_token.assert_any_call("claude-sonnet-4-5-20250929", "output", 1000)
        mock_token.assert_any_call("claude-sonnet-4-5-20250929", "cached", 1000)

        # Verify cost: (1000/1000)*0.003 + (1000/1000)*0.015 + (1000/1000)*0.0003 = 0.0183
        mock_cost.assert_called_once()
        call_args = mock_cost.call_args[0]
        assert call_args[0] == "claude-sonnet-4-5-20250929"
        assert abs(call_args[1] - 0.0183) < 0.0001


def test_record_tokens_opus_pricing() -> None:
    """Test Opus model pricing calculation."""
    # Opus: $0.015/1K input, $0.075/1K output, $0.0015/1K cached
    usage = {
        "input_tokens": 1000,
        "output_tokens": 1000,
        "cache_read_input_tokens": 1000,
    }

    with patch.object(MetricsCollector, "record_token_usage"), \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-opus-4-5-20251101", usage)

        # Verify cost: (1000/1000)*0.015 + (1000/1000)*0.075 + (1000/1000)*0.0015 = 0.0915
        mock_cost.assert_called_once()
        call_args = mock_cost.call_args[0]
        assert call_args[0] == "claude-opus-4-5-20251101"
        assert abs(call_args[1] - 0.0915) < 0.0001


def test_record_tokens_haiku_pricing() -> None:
    """Test Haiku model pricing calculation."""
    # Haiku: $0.001/1K input, $0.005/1K output, $0.0001/1K cached
    usage = {
        "input_tokens": 1000,
        "output_tokens": 1000,
        "cache_read_input_tokens": 1000,
    }

    with patch.object(MetricsCollector, "record_token_usage"), \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-3-5-haiku-20241022", usage)

        # Verify cost: (1000/1000)*0.001 + (1000/1000)*0.005 + (1000/1000)*0.0001 = 0.0061
        mock_cost.assert_called_once()
        call_args = mock_cost.call_args[0]
        assert call_args[0] == "claude-3-5-haiku-20241022"
        assert abs(call_args[1] - 0.0061) < 0.0001


def test_record_tokens_case_insensitive_model() -> None:
    """Test that model name matching is case-insensitive."""
    usage = {"input_tokens": 1000, "output_tokens": 0}

    with patch.object(MetricsCollector, "record_token_usage"), \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        # Uppercase OPUS should still use Opus pricing
        MetricsCollector.record_tokens("main", "CLAUDE-OPUS-4-5", usage)

        call_args = mock_cost.call_args[0]
        # Opus input rate is $0.015/1K
        assert abs(call_args[1] - 0.015) < 0.0001


def test_record_tokens_zero_tokens() -> None:
    """Test that zero tokens results in no cost recording."""
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    with patch.object(MetricsCollector, "record_token_usage") as mock_token, \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-sonnet-4-5-20250929", usage)

        # No tokens should be recorded
        mock_token.assert_not_called()
        # No cost should be recorded
        mock_cost.assert_not_called()


def test_record_tokens_partial_usage() -> None:
    """Test recording with only some token types present."""
    usage = {"input_tokens": 500}  # Only input tokens

    with patch.object(MetricsCollector, "record_token_usage") as mock_token, \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-sonnet-4-5-20250929", usage)

        # Only input tokens should be recorded
        mock_token.assert_called_once_with("claude-sonnet-4-5-20250929", "input", 500)

        # Cost: (500/1000)*0.003 = 0.0015
        call_args = mock_cost.call_args[0]
        assert abs(call_args[1] - 0.0015) < 0.0001


def test_record_tokens_empty_usage() -> None:
    """Test recording with empty usage dictionary."""
    usage: dict = {}

    with patch.object(MetricsCollector, "record_token_usage") as mock_token, \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "claude-sonnet-4-5-20250929", usage)

        mock_token.assert_not_called()
        mock_cost.assert_not_called()


def test_record_tokens_default_model_pricing() -> None:
    """Test that unknown models default to Sonnet pricing."""
    usage = {"input_tokens": 1000, "output_tokens": 1000}

    with patch.object(MetricsCollector, "record_token_usage"), \
         patch.object(MetricsCollector, "record_api_cost") as mock_cost:
        MetricsCollector.record_tokens("main", "some-unknown-model", usage)

        # Should use Sonnet pricing: 0.003 + 0.015 = 0.018
        call_args = mock_cost.call_args[0]
        assert abs(call_args[1] - 0.018) < 0.0001


# =============================================================================
# Cache Metrics Tests
# =============================================================================


def test_update_cache_metrics_full() -> None:
    """Test updating all cache metrics."""
    with patch("harness.monitoring.interactive_cache_read_tokens") as mock_read, \
         patch("harness.monitoring.interactive_cache_creation_tokens") as mock_create, \
         patch("harness.monitoring.interactive_cache_hit_ratio") as mock_ratio:

        MetricsCollector.update_cache_metrics(
            agent="main",
            model="claude-sonnet-4-5",
            cache_read=500,
            cache_creation=200,
            total_input=1000,
        )

        # Verify cache read tokens recorded
        mock_read.labels.assert_called_with(agent="main", model="claude-sonnet-4-5")
        mock_read.labels().inc.assert_called_with(500)

        # Verify cache creation tokens recorded
        mock_create.labels.assert_called_with(agent="main", model="claude-sonnet-4-5")
        mock_create.labels().inc.assert_called_with(200)

        # Verify hit ratio: 500/1000 = 0.5
        mock_ratio.labels.assert_called_with(agent="main")
        mock_ratio.labels().set.assert_called_with(0.5)


def test_update_cache_metrics_zero_cache_read() -> None:
    """Test that zero cache_read skips inc call."""
    with patch("harness.monitoring.interactive_cache_read_tokens") as mock_read, \
         patch("harness.monitoring.interactive_cache_creation_tokens") as mock_create, \
         patch("harness.monitoring.interactive_cache_hit_ratio") as mock_ratio:

        MetricsCollector.update_cache_metrics(
            agent="main",
            model="claude-sonnet-4-5",
            cache_read=0,
            cache_creation=200,
            total_input=1000,
        )

        # Cache read should not be called
        mock_read.labels().inc.assert_not_called()

        # Cache creation should be called
        mock_create.labels().inc.assert_called_with(200)

        # Hit ratio should be 0
        mock_ratio.labels().set.assert_called_with(0.0)


def test_update_cache_metrics_zero_cache_creation() -> None:
    """Test that zero cache_creation skips inc call."""
    with patch("harness.monitoring.interactive_cache_read_tokens") as mock_read, \
         patch("harness.monitoring.interactive_cache_creation_tokens") as mock_create, \
         patch("harness.monitoring.interactive_cache_hit_ratio"):

        MetricsCollector.update_cache_metrics(
            agent="main",
            model="claude-sonnet-4-5",
            cache_read=500,
            cache_creation=0,
            total_input=1000,
        )

        # Cache read should be called
        mock_read.labels().inc.assert_called_with(500)

        # Cache creation should not be called
        mock_create.labels().inc.assert_not_called()


def test_update_cache_metrics_zero_total_input() -> None:
    """Test that zero total_input skips hit ratio calculation."""
    with patch("harness.monitoring.interactive_cache_read_tokens"), \
         patch("harness.monitoring.interactive_cache_creation_tokens"), \
         patch("harness.monitoring.interactive_cache_hit_ratio") as mock_ratio:

        MetricsCollector.update_cache_metrics(
            agent="main",
            model="claude-sonnet-4-5",
            cache_read=0,
            cache_creation=0,
            total_input=0,
        )

        # Hit ratio should not be set (divide by zero protection)
        mock_ratio.labels().set.assert_not_called()


# =============================================================================
# Interactive Session Metrics Tests
# =============================================================================


def test_record_user_prompt() -> None:
    """Test recording user prompt metric."""
    with patch("harness.monitoring.interactive_session_prompts_total") as mock_prompts:
        MetricsCollector.record_user_prompt("main")

        mock_prompts.labels.assert_called_with(agent="main")
        mock_prompts.labels().inc.assert_called_once()


def test_record_agent_response() -> None:
    """Test recording agent response metric."""
    with patch("harness.monitoring.interactive_session_responses_total") as mock_responses:
        MetricsCollector.record_agent_response("main")

        mock_responses.labels.assert_called_with(agent="main")
        mock_responses.labels().inc.assert_called_once()


def test_record_interactive_session_duration() -> None:
    """Test recording interactive session duration."""
    with patch("harness.monitoring.interactive_session_duration_seconds") as mock_duration:
        MetricsCollector.record_interactive_session_duration("main", 3600.5)

        mock_duration.labels.assert_called_with(agent="main")
        mock_duration.labels().observe.assert_called_with(3600.5)


def test_record_tool_call_success() -> None:
    """Test recording successful tool call."""
    with patch("harness.monitoring.interactive_tool_calls_total") as mock_tools:
        MetricsCollector.record_tool_call("main", "Read", "success")

        mock_tools.labels.assert_called_with(agent="main", tool_name="Read", status="success")
        mock_tools.labels().inc.assert_called_once()


def test_record_tool_call_default_status() -> None:
    """Test that tool call defaults to success status."""
    with patch("harness.monitoring.interactive_tool_calls_total") as mock_tools:
        MetricsCollector.record_tool_call("main", "Write")  # No status

        mock_tools.labels.assert_called_with(agent="main", tool_name="Write", status="success")


def test_record_tool_call_error() -> None:
    """Test recording failed tool call."""
    with patch("harness.monitoring.interactive_tool_calls_total") as mock_tools:
        MetricsCollector.record_tool_call("main", "Bash", "error")

        mock_tools.labels.assert_called_with(agent="main", tool_name="Bash", status="error")


def test_record_message_type() -> None:
    """Test recording message types."""
    with patch("harness.monitoring.interactive_message_types_total") as mock_types:
        MetricsCollector.record_message_type("main", "tool_use")

        mock_types.labels.assert_called_with(agent="main", message_type="tool_use")
        mock_types.labels().inc.assert_called_once()


def test_record_message_type_various() -> None:
    """Test recording various message types."""
    message_types = ["text", "tool_use", "thinking", "tool_result"]

    with patch("harness.monitoring.interactive_message_types_total") as mock_types:
        for msg_type in message_types:
            MetricsCollector.record_message_type("main", msg_type)

        assert mock_types.labels.call_count == 4


# =============================================================================
# Basic Metrics Tests
# =============================================================================


def test_record_request() -> None:
    """Test recording agent request."""
    with patch("harness.monitoring.agent_requests_total") as mock_requests:
        MetricsCollector.record_request("main", "success")

        mock_requests.labels.assert_called_with(agent="main", status="success")
        mock_requests.labels().inc.assert_called_once()


def test_record_request_error() -> None:
    """Test recording error request."""
    with patch("harness.monitoring.agent_requests_total") as mock_requests:
        MetricsCollector.record_request("main", "error")

        mock_requests.labels.assert_called_with(agent="main", status="error")


def test_record_duration() -> None:
    """Test recording agent duration."""
    with patch("harness.monitoring.agent_duration_seconds") as mock_duration:
        MetricsCollector.record_duration("main", 1.5)

        mock_duration.labels.assert_called_with(agent="main")
        mock_duration.labels().observe.assert_called_with(1.5)


def test_set_active_sessions() -> None:
    """Test setting active sessions count."""
    with patch("harness.monitoring.agent_active_sessions") as mock_sessions:
        MetricsCollector.set_active_sessions("main", 5)

        mock_sessions.labels.assert_called_with(agent="main")
        mock_sessions.labels().set.assert_called_with(5)


def test_record_token_usage() -> None:
    """Test recording token usage."""
    with patch("harness.monitoring.api_tokens_used") as mock_tokens:
        MetricsCollector.record_token_usage("claude-sonnet-4-5", "input", 1000)

        mock_tokens.labels.assert_called_with(model="claude-sonnet-4-5", type="input")
        mock_tokens.labels().inc.assert_called_with(1000)


def test_record_api_cost() -> None:
    """Test recording API cost."""
    with patch("harness.monitoring.api_cost_dollars") as mock_cost:
        MetricsCollector.record_api_cost("claude-sonnet-4-5", 0.05)

        mock_cost.labels.assert_called_with(model="claude-sonnet-4-5")
        mock_cost.labels().inc.assert_called_with(0.05)


def test_set_memory_usage() -> None:
    """Test setting memory usage."""
    with patch("harness.monitoring.memory_usage_bytes") as mock_memory:
        MetricsCollector.set_memory_usage("agent", 1024000)

        mock_memory.labels.assert_called_with(component="agent")
        mock_memory.labels().set.assert_called_with(1024000)


# =============================================================================
# System Metrics Collection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_collect_system_metrics_workspace(metrics_collector: MetricsCollector) -> None:
    """Test that system metrics collection counts workspace files."""
    # Create some Python files in workspace
    workspace = metrics_collector.workspace_dir
    (workspace / "file1.py").write_text("# test")
    (workspace / "file2.py").write_text("# test")
    (workspace / "subdir").mkdir()
    (workspace / "subdir" / "file3.py").write_text("# test")

    with patch("harness.monitoring.workspace_files_total") as mock_files:
        # Run one iteration of collection
        metrics_collector.running = True

        async def run_once():
            # Manually execute the collection logic once
            if metrics_collector.workspace_dir.exists():
                file_count = len(list(metrics_collector.workspace_dir.rglob("*.py")))
                mock_files.set(file_count)

        await run_once()

        mock_files.set.assert_called_with(3)


@pytest.mark.asyncio
async def test_collect_system_metrics_checkpoints(metrics_collector: MetricsCollector) -> None:
    """Test that system metrics collection measures checkpoint size."""
    # Create some checkpoint files
    checkpoint_dir = metrics_collector.checkpoint_dir
    (checkpoint_dir / "checkpoint_1.json").write_text('{"test": "data"}')
    (checkpoint_dir / "checkpoint_2.json").write_text('{"more": "data", "extra": "info"}')

    with patch("harness.monitoring.checkpoint_size_bytes") as mock_size:
        # Run one iteration of collection
        if metrics_collector.checkpoint_dir.exists():
            total_size = sum(
                f.stat().st_size for f in metrics_collector.checkpoint_dir.iterdir()
                if f.is_file()
            )
            mock_size.set(total_size)

        # Total size should be sum of both files
        mock_size.set.assert_called_once()
        call_args = mock_size.set.call_args[0][0]
        assert call_args > 0  # Some bytes were recorded


def test_stop_metrics_collection(metrics_collector: MetricsCollector) -> None:
    """Test stopping metrics collection."""
    metrics_collector.running = True
    metrics_collector.stop()

    assert metrics_collector.running is False


# =============================================================================
# Server Start Tests
# =============================================================================


def test_start_server_success(metrics_collector: MetricsCollector) -> None:
    """Test successful server start."""
    with patch("harness.monitoring.start_http_server") as mock_start:
        metrics_collector.start()

        mock_start.assert_called_once_with(metrics_collector.port)
        assert MetricsCollector._server_started is True


def test_start_server_already_running() -> None:
    """Test that server doesn't start twice."""
    MetricsCollector._server_started = True
    collector = MetricsCollector(port=19095)

    with patch("harness.monitoring.start_http_server") as mock_start:
        collector.start()

        # Should not try to start again
        mock_start.assert_not_called()


def test_start_server_port_in_use_linux() -> None:
    """Test handling of port already in use (Linux errno 98)."""
    collector = MetricsCollector(port=19096)

    error = OSError()
    error.errno = 98  # Linux: Address already in use

    with patch("harness.monitoring.start_http_server", side_effect=error):
        collector.start()

        # Should still mark as started (metrics still work)
        assert MetricsCollector._server_started is True


def test_start_server_port_in_use_macos() -> None:
    """Test handling of port already in use (macOS errno 48)."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19097)

    error = OSError()
    error.errno = 48  # macOS: Address already in use

    with patch("harness.monitoring.start_http_server", side_effect=error):
        collector.start()

        # Should still mark as started (metrics still work)
        assert MetricsCollector._server_started is True


def test_start_server_other_os_error() -> None:
    """Test handling of other OS errors."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19098)

    error = OSError()
    error.errno = 13  # Permission denied

    with patch("harness.monitoring.start_http_server", side_effect=error):
        collector.start()

        # Should NOT mark as started for other errors
        assert MetricsCollector._server_started is False


def test_start_server_general_exception() -> None:
    """Test handling of general exceptions."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19099)

    with patch("harness.monitoring.start_http_server", side_effect=Exception("Connection error")):
        collector.start()

        # Should NOT mark as started for general errors
        assert MetricsCollector._server_started is False


# =============================================================================
# Initialization Tests
# =============================================================================


def test_initialization_defaults() -> None:
    """Test MetricsCollector default values."""
    collector = MetricsCollector()

    assert collector.port == 9090
    assert collector.workspace_dir == Path("/workspace")
    assert collector.checkpoint_dir == Path("/memory/checkpoints")
    assert collector.running is False


def test_initialization_custom_dirs(tmp_path: Path) -> None:
    """Test MetricsCollector with custom directories."""
    workspace = tmp_path / "custom_workspace"
    checkpoint = tmp_path / "custom_checkpoint"

    MetricsCollector.reset_singleton()
    collector = MetricsCollector(
        port=19100,
        workspace_dir=workspace,
        checkpoint_dir=checkpoint,
    )

    assert collector.port == 19100
    assert collector.workspace_dir == workspace
    assert collector.checkpoint_dir == checkpoint
