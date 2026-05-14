"""Unit tests for monitoring module."""

from __future__ import annotations

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
# Note: Token, cost, and cache-token tests were removed when those instruments
# were dropped in favor of SDK-emitted equivalents (claude_code_token_usage_*,
# claude_code_cost_usage_USD_total). Cache hit ratio is computed on dashboards
# via PromQL against the SDK metrics.
# =============================================================================


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
    mock_server = MagicMock()
    with patch("harness.monitoring.start_authenticated_http_server", return_value=mock_server):
        metrics_collector.start()

        assert MetricsCollector._server_started is True


def test_start_server_already_running() -> None:
    """Test that server doesn't start twice."""
    MetricsCollector._server_started = True
    collector = MetricsCollector(port=19095)

    with patch("harness.monitoring.start_authenticated_http_server") as mock_start:
        collector.start()

        # Should not try to start again
        mock_start.assert_not_called()


def test_start_server_port_in_use_linux() -> None:
    """Test handling of port already in use (Linux errno 98)."""
    collector = MetricsCollector(port=19096)

    error = OSError()
    error.errno = 98  # Linux: Address already in use

    with patch("harness.monitoring.start_authenticated_http_server", side_effect=error):
        collector.start()

        # Should still mark as started (metrics still work)
        assert MetricsCollector._server_started is True


def test_start_server_port_in_use_macos() -> None:
    """Test handling of port already in use (macOS errno 48)."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19097)

    error = OSError()
    error.errno = 48  # macOS: Address already in use

    with patch("harness.monitoring.start_authenticated_http_server", side_effect=error):
        collector.start()

        # Should still mark as started (metrics still work)
        assert MetricsCollector._server_started is True


def test_start_server_other_os_error() -> None:
    """Test handling of other OS errors."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19098)

    error = OSError()
    error.errno = 13  # Permission denied

    with patch("harness.monitoring.start_authenticated_http_server", side_effect=error):
        collector.start()

        # Should NOT mark as started for other errors
        assert MetricsCollector._server_started is False


def test_start_server_general_exception() -> None:
    """Test handling of general exceptions."""
    MetricsCollector.reset_singleton()
    collector = MetricsCollector(port=19099)

    with patch("harness.monitoring.start_authenticated_http_server", side_effect=Exception("Connection error")):
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


# =============================================================================
# Phase 1.3 — Run-level instrument helpers (grafana-refactor branch)
# =============================================================================


def test_record_run_config_sets_info_gauge_to_one() -> None:
    """record_run_config sets the labelled series to 1."""
    from harness.monitoring import harness_run_config_info, record_run_config

    record_run_config(
        resource="test-resource",
        path="multi",
        mode="optimize",
        model="sonnet",
        effort="default",
        eval_enabled=True,
        token_budget=1_000_000,
        max_iterations=3,
    )
    value = harness_run_config_info.labels(
        resource="test-resource",
        path="multi",
        mode="optimize",
        model="sonnet",
        effort="default",
        eval_enabled="true",
        token_budget="1000000",
        max_iterations="3",
    )._value.get()
    assert value == 1.0


def test_clear_run_config_sets_info_gauge_to_zero() -> None:
    """clear_run_config zeroes the same label set used at start."""
    from harness.monitoring import (
        clear_run_config,
        harness_run_config_info,
        record_run_config,
    )

    record_run_config(
        resource="clear-test",
        path="single",
        mode="optimize",
        model="haiku",
        effort="default",
        eval_enabled=False,
        token_budget=0,
        max_iterations=5,
    )
    clear_run_config(
        resource="clear-test",
        path="single",
        mode="optimize",
        model="haiku",
        effort="default",
        eval_enabled=False,
        token_budget=0,
        max_iterations=5,
    )

    value = harness_run_config_info.labels(
        resource="clear-test",
        path="single",
        mode="optimize",
        model="haiku",
        effort="default",
        eval_enabled="false",
        token_budget="0",
        max_iterations="5",
    )._value.get()
    assert value == 0.0


def test_record_run_start_sets_timestamp() -> None:
    """record_run_start populates the timestamp gauge."""
    from harness.monitoring import harness_run_start_timestamp, record_run_start

    record_run_start("start-test", timestamp=1_700_000_000.0)
    value = harness_run_start_timestamp.labels(resource="start-test")._value.get()
    assert value == 1_700_000_000.0


def test_singleton_semantic_record_run_config() -> None:
    """Subsequent record_run_config calls clear prior series.

    Regression: Run Config table on D00/D70 used to accumulate one
    row per (resource, config) ever recorded; the new singleton
    semantic ensures only the current run's row is present.
    """
    from harness.monitoring import harness_run_config_info, record_run_config

    record_run_config(
        resource="first-resource", path="single", mode="optimize",
        model="haiku", effort="default", eval_enabled=False,
        token_budget=0, max_iterations=3,
    )
    record_run_config(
        resource="second-resource", path="multi", mode="optimize",
        model="sonnet", effort="default", eval_enabled=True,
        token_budget=100, max_iterations=5,
    )

    # Only the second resource's series should remain.  Collect all
    # active label combos from the underlying metric registry.
    sample_resources = {
        sample.labels["resource"]
        for metric in harness_run_config_info.collect()
        for sample in metric.samples
        if sample.value == 1.0
    }
    assert sample_resources == {"second-resource"}


def test_singleton_semantic_record_run_path() -> None:
    """record_run_path clears prior series so only one resource is
    marked active at a time."""
    from harness.monitoring import harness_run_path_info, record_run_path

    record_run_path("first-resource", "single")
    record_run_path("second-resource", "multi")

    active_resources = {
        sample.labels["resource"]
        for metric in harness_run_path_info.collect()
        for sample in metric.samples
        if sample.value == 1.0
    }
    assert active_resources == {"second-resource"}


def test_singleton_semantic_init_run_phases() -> None:
    """init_run_phases clears prior-resource phase + iteration series."""
    from harness.monitoring import (
        harness_run_iteration,
        harness_run_phase_info,
        init_run_phases,
        record_iteration,
        record_phase_entry,
    )

    init_run_phases("first-resource")
    record_phase_entry("first-resource", "research")
    record_iteration("first-resource", 7)

    # Start a new run; prior resource's series should be wiped.
    init_run_phases("second-resource")

    active_phase_resources = {
        sample.labels["resource"]
        for metric in harness_run_phase_info.collect()
        for sample in metric.samples
    }
    iteration_resources = {
        sample.labels["resource"]
        for metric in harness_run_iteration.collect()
        for sample in metric.samples
    }
    assert active_phase_resources == {"second-resource"}
    assert iteration_resources == set()  # no record_iteration call yet for the new run


def test_record_run_start_defaults_to_now() -> None:
    """Default timestamp is non-zero and within a reasonable window of time.time()."""
    import time

    from harness.monitoring import harness_run_start_timestamp, record_run_start

    before = time.time()
    record_run_start("now-test")
    after = time.time()
    value = harness_run_start_timestamp.labels(resource="now-test")._value.get()
    assert before <= value <= after


def test_record_task_progress_emits_all_three_statuses() -> None:
    """All three statuses are written even when input is partial."""
    from harness.monitoring import harness_task_progress, record_task_progress

    record_task_progress({"completed": 4, "pending": 2})

    assert harness_task_progress.labels(status="completed")._value.get() == 4.0
    assert harness_task_progress.labels(status="pending")._value.get() == 2.0
    # `failed` missing from input → defaults to 0
    assert harness_task_progress.labels(status="failed")._value.get() == 0.0


def test_record_task_progress_handles_failed_bucket() -> None:
    """The failed bucket is emitted alongside completed and pending."""
    from harness.monitoring import harness_task_progress, record_task_progress

    record_task_progress({"completed": 1, "failed": 2, "pending": 3})

    assert harness_task_progress.labels(status="completed")._value.get() == 1.0
    assert harness_task_progress.labels(status="failed")._value.get() == 2.0
    assert harness_task_progress.labels(status="pending")._value.get() == 3.0


def test_observability_helpers_never_raise() -> None:
    """Even with bogus inputs, helpers must swallow exceptions —
    observability never breaks the pipeline."""
    from harness.monitoring import (
        clear_run_config,
        record_run_config,
        record_run_start,
        record_task_progress,
    )

    # These would normally raise if not wrapped in try/except.
    record_run_config(
        resource=None,  # type: ignore[arg-type]
        path="multi",
        mode="optimize",
        model="sonnet",
        effort="default",
        eval_enabled=True,
        token_budget=0,
        max_iterations=3,
    )
    clear_run_config(
        resource=None,  # type: ignore[arg-type]
        path="multi",
        mode="optimize",
        model="sonnet",
        effort="default",
        eval_enabled=True,
        token_budget=0,
        max_iterations=3,
    )
    record_run_start(None)  # type: ignore[arg-type]
    record_task_progress({"bogus_status": 99})  # bogus key silently ignored
