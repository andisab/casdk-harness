# Test Coverage TODO

This file tracks missing test coverage identified during the test suite cleanup (November 21, 2025).

## Priority: HIGH

### Unit Tests Needed

#### `test_monitoring.py` - MetricsCollector Tests
**Location**: `tests/unit/test_monitoring.py`

**Purpose**: Test the Prometheus metrics collection functionality.

**Tests to implement**:
- `test_metrics_collector_initialization` - Verify metrics server starts correctly
- `test_record_request` - Test request counter increments
- `test_record_duration` - Test duration histogram updates
- `test_record_tool_call` - Test tool call tracking
- `test_update_cache_metrics` - Test cache hit ratio calculation
- `test_token_tracking` - Test token usage and cost calculation
- `test_metrics_export` - Test Prometheus export format

**Estimated effort**: 2-3 hours
**Coverage impact**: +5% overall coverage

---

#### `test_cli_formatting.py` - CLI Display Tests
**Location**: `tests/unit/test_cli_formatting.py`

**Purpose**: Test Rich console formatting and message parsing.

**Tests to implement**:
- `test_parse_user_message` - Test user message formatting
- `test_parse_assistant_message` - Test assistant response formatting
- `test_parse_tool_use` - Test tool call display
- `test_parse_tool_result` - Test tool result display
- `test_code_syntax_highlighting` - Test code block rendering
- `test_json_formatting` - Test JSON prettification
- `test_error_message_formatting` - Test error display
- `test_session_stats_display` - Test statistics formatting

**Estimated effort**: 2-3 hours
**Coverage impact**: +4% overall coverage

---

## Priority: MEDIUM

### Integration Tests Needed

#### `test_agent_session.py` - AgentSession Lifecycle
**Location**: `tests/integration/test_agent_session.py`

**Purpose**: Test the AgentSession wrapper class lifecycle management.

**Tests to implement**:
- `test_session_start_shutdown` - Test basic lifecycle
- `test_session_checkpoint_integration` - Test auto-checkpointing
- `test_session_metrics_integration` - Test metrics collection
- `test_session_mcp_registration` - Test MCP server registration
- `test_session_error_handling` - Test error recovery
- `test_session_retry_logic` - Test retry with exponential backoff
- `test_multi_turn_conversation` - Test stateful conversation

**Estimated effort**: 3-4 hours
**Coverage impact**: +6% overall coverage

---

#### `test_interactive_mode.py` - Interactive Mode Tests
**Location**: `tests/integration/test_interactive_mode.py`

**Purpose**: Test the interactive conversation loop functionality.

**Tests to implement**:
- `test_interactive_loop_basic` - Test basic conversation flow
- `test_checkpoint_recovery_on_startup` - Test loading previous session
- `test_graceful_interrupt_handling` - Test Ctrl+C handling
- `test_stats_display_toggle` - Test --stats flag
- `test_quiet_mode` - Test --quiet flag for clean output
- `test_model_selection` - Test --model flag
- `test_streaming_message_display` - Test real-time message display

**Estimated effort**: 3-4 hours
**Coverage impact**: +5% overall coverage

**Note**: May require mocking user input - consider using `pytest-mock` or similar.

---

## Summary

**Total missing tests**: 4 test files
**Total estimated effort**: 10-14 hours
**Estimated coverage improvement**: +20% (from ~61% to ~81%)

**Target**: Achieve 80%+ test coverage before Phase 2 begins.

---

## Notes

- All unit tests should be fast (< 1 second each) and require no external dependencies
- Integration tests may make real API calls - mark with `@pytest.mark.slow` if > 30 seconds
- Focus on critical paths first: monitoring and agent session lifecycle
- CLI formatting tests can use snapshot testing (e.g., `pytest-snapshot`) for easier maintenance
- Interactive mode tests should mock stdin/stdout for reliable testing

---

**Last updated**: November 21, 2025
**Tracked in**: https://github.com/andisab/ab-casdk-harness/issues (create tracking issue)
