"""Unit tests for HookRegistry.

Tests hook registration, matching, and execution.
"""

import asyncio

import pytest
import structlog

from harness.hooks import HookEvent, HookRegistry, PluginHook

logger = structlog.get_logger(__name__)


@pytest.fixture
def sample_hooks():
    """Create sample hooks for testing."""
    return [
        PluginHook(
            event=HookEvent.SESSION_START,
            command="echo 'Session started'",
            plugin_name="test-plugin",
        ),
        PluginHook(
            event=HookEvent.POST_TOOL_USE,
            command="echo 'Tool used: $TOOL on $FILE'",
            plugin_name="test-plugin",
            matcher={"tool_name": "Write"},
        ),
        PluginHook(
            event=HookEvent.POST_TOOL_USE,
            command="echo 'Python file: $FILE'",
            plugin_name="test-plugin",
            matcher={"tool_name": "Write", "file_path": "*.py"},
        ),
        PluginHook(
            event=HookEvent.STOP,
            command="echo 'Session ended'",
            plugin_name="other-plugin",
            timeout=10,
        ),
    ]


class TestHookRegistration:
    """Test hook registration."""

    def test_register_hook(self, sample_hooks):
        """Test registering a single hook."""
        registry = HookRegistry()
        registry.register(sample_hooks[0])

        assert len(registry) == 1

    def test_register_all(self, sample_hooks):
        """Test registering multiple hooks."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        assert len(registry) == 4

    def test_clear(self, sample_hooks):
        """Test clearing all hooks."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)
        registry.clear()

        assert len(registry) == 0


class TestHookMatching:
    """Test hook event and context matching."""

    def test_get_hooks_by_event(self, sample_hooks):
        """Test getting hooks for a specific event."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        # POST_TOOL_USE hooks both have matchers, so without context they won't match
        post_tool_hooks = registry.get_hooks_for_event(HookEvent.POST_TOOL_USE)
        assert len(post_tool_hooks) == 0  # Matchers require context

        # With matching context, both should match
        context = {"tool_name": "Write", "file_path": "test.py"}
        post_tool_hooks = registry.get_hooks_for_event(HookEvent.POST_TOOL_USE, context)
        assert len(post_tool_hooks) == 2

        # SESSION_START hook has no matcher, so it matches
        session_start_hooks = registry.get_hooks_for_event(HookEvent.SESSION_START)
        assert len(session_start_hooks) == 1

    def test_get_hooks_with_tool_name_matcher(self, sample_hooks):
        """Test getting hooks that match tool name."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        # Should match both POST_TOOL_USE hooks when tool is Write
        context = {"tool_name": "Write", "file_path": "test.txt"}
        hooks = registry.get_hooks_for_event(HookEvent.POST_TOOL_USE, context)
        assert len(hooks) == 1  # Only the one without file_path matcher

        # Should match hook with file_path matcher for .py files
        context = {"tool_name": "Write", "file_path": "test.py"}
        hooks = registry.get_hooks_for_event(HookEvent.POST_TOOL_USE, context)
        assert len(hooks) == 2  # Both matchers match

    def test_get_hooks_no_match(self, sample_hooks):
        """Test getting hooks when no matcher matches."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        # Read tool shouldn't match Write matchers
        context = {"tool_name": "Read", "file_path": "test.py"}
        hooks = registry.get_hooks_for_event(HookEvent.POST_TOOL_USE, context)
        assert len(hooks) == 0

    def test_get_hooks_no_matcher(self, sample_hooks):
        """Test hooks without matcher always match."""
        registry = HookRegistry()
        registry.register(sample_hooks[0])  # SESSION_START, no matcher

        hooks = registry.get_hooks_for_event(HookEvent.SESSION_START)
        assert len(hooks) == 1

        # Even with context, should match (no matcher = match all)
        hooks = registry.get_hooks_for_event(
            HookEvent.SESSION_START,
            {"some": "context"}
        )
        assert len(hooks) == 1


class TestHookExecution:
    """Test hook execution."""

    def test_trigger_simple(self, sample_hooks):
        """Test triggering simple hook."""
        registry = HookRegistry()
        registry.register(sample_hooks[0])  # echo 'Session started'

        results = registry.trigger(HookEvent.SESSION_START)

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["exit_code"] == 0
        assert "Session started" in results[0]["stdout"]

    def test_trigger_with_variable_substitution(self, sample_hooks):
        """Test triggering hook with variable substitution."""
        registry = HookRegistry()
        registry.register(sample_hooks[1])  # echo 'Tool used: $TOOL on $FILE'

        context = {"tool_name": "Write", "file_path": "test.txt"}
        results = registry.trigger(HookEvent.POST_TOOL_USE, context)

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert "Tool used: Write on test.txt" in results[0]["stdout"]

    def test_trigger_no_matching_hooks(self, sample_hooks):
        """Test triggering when no hooks match."""
        registry = HookRegistry()
        registry.register(sample_hooks[1])  # POST_TOOL_USE with Write matcher

        # Trigger SESSION_START - no hooks for this event
        results = registry.trigger(HookEvent.SESSION_START)
        assert len(results) == 0

    def test_trigger_command_failure(self):
        """Test triggering hook with failing command."""
        registry = HookRegistry()
        registry.register(PluginHook(
            event=HookEvent.SESSION_START,
            command="exit 1",
            plugin_name="test",
        ))

        results = registry.trigger(HookEvent.SESSION_START)

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert results[0]["exit_code"] == 1

    def test_trigger_command_timeout(self):
        """Test triggering hook that times out."""
        registry = HookRegistry()
        registry.register(PluginHook(
            event=HookEvent.SESSION_START,
            command="sleep 10",
            plugin_name="test",
            timeout=1,  # 1 second timeout
        ))

        results = registry.trigger(HookEvent.SESSION_START)

        assert len(results) == 1
        assert results[0]["status"] == "timeout"


class TestHookAsyncExecution:
    """Test async hook execution."""

    @pytest.mark.asyncio
    async def test_trigger_async_simple(self, sample_hooks):
        """Test async triggering of hooks."""
        registry = HookRegistry()
        registry.register(sample_hooks[0])

        results = await registry.trigger_async(HookEvent.SESSION_START)

        assert len(results) == 1
        assert results[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_trigger_async_with_substitution(self, sample_hooks):
        """Test async triggering with variable substitution."""
        registry = HookRegistry()
        registry.register(sample_hooks[1])

        context = {"tool_name": "Write", "file_path": "test.txt"}
        results = await registry.trigger_async(HookEvent.POST_TOOL_USE, context)

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert "Tool used: Write on test.txt" in results[0]["stdout"]

    @pytest.mark.asyncio
    async def test_trigger_async_timeout(self):
        """Test async triggering with timeout."""
        registry = HookRegistry()
        registry.register(PluginHook(
            event=HookEvent.SESSION_START,
            command="sleep 10",
            plugin_name="test",
            timeout=1,
        ))

        results = await registry.trigger_async(HookEvent.SESSION_START)

        assert len(results) == 1
        assert results[0]["status"] == "timeout"


class TestHookListing:
    """Test hook listing methods."""

    def test_list_all(self, sample_hooks):
        """Test listing all hooks."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        all_hooks = registry.list_all()
        assert len(all_hooks) == 4

    def test_list_by_event(self, sample_hooks):
        """Test listing hooks by event."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        post_tool_hooks = registry.list_by_event(HookEvent.POST_TOOL_USE)
        assert len(post_tool_hooks) == 2

        stop_hooks = registry.list_by_event(HookEvent.STOP)
        assert len(stop_hooks) == 1

    def test_list_by_plugin(self, sample_hooks):
        """Test listing hooks by plugin."""
        registry = HookRegistry()
        registry.register_all(sample_hooks)

        test_plugin_hooks = registry.list_by_plugin("test-plugin")
        assert len(test_plugin_hooks) == 3

        other_plugin_hooks = registry.list_by_plugin("other-plugin")
        assert len(other_plugin_hooks) == 1
