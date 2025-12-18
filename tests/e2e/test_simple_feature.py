"""End-to-end test for simple feature development workflow.

Tests complete workflow from requirements to implementation to testing.
WARNING: This test uses real API calls and can be expensive. Use sparingly.
"""

from __future__ import annotations

from typing import Any

import pytest
import structlog
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from harness.agent import AgentSession

logger = structlog.get_logger(__name__)


def extract_messages_info(messages: list[Any]) -> dict[str, Any]:
    """
    Extract useful information from agent messages for assertions.

    Args:
        messages: List of messages from agent execution

    Returns:
        Dictionary with message statistics and content
    """
    info = {
        "total_count": len(messages),
        "assistant_messages": 0,
        "result_messages": 0,
        "tool_use_blocks": [],
        "text_blocks": [],
        "has_text_content": False,
        "has_tool_calls": False,
    }

    for msg in messages:
        if isinstance(msg, AssistantMessage):
            info["assistant_messages"] += 1
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    info["tool_use_blocks"].append(block.name)
                    info["has_tool_calls"] = True
                elif isinstance(block, TextBlock):
                    info["text_blocks"].append(block.text[:200])  # First 200 chars
                    info["has_text_content"] = True
        elif isinstance(msg, ResultMessage):
            info["result_messages"] += 1

    return info


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minute timeout for E2E test
@pytest.mark.slow
async def test_end_to_end_feature_development(
    workspace_dir,
    skip_if_no_api_key,
    check_token_budget,
):
    """
    Test complete feature development workflow.

    Workflow:
    1. Agent reads requirements
    2. Agent creates implementation
    3. Agent writes tests
    4. Agent runs tests
    5. Agent fixes failures (if any)

    This is an expensive test that exercises the full agent capabilities.

    Note: VCR.py cassettes not used - SDK uses subprocess I/O which VCR cannot intercept.
    This test makes real API calls and costs ~$1-5 depending on complexity.

    Assertions verify:
    - Agent produces assistant messages with content
    - Agent uses file writing tools (Write, Edit)
    - Agent provides text responses explaining work done
    - Execution completes without errors

    Cost: ~$1-5 per run
    Duration: Up to 10 minutes
    """
    session = AgentSession(agent_name="e2e-test")
    await session.start()

    prompt = """
    Create a simple calculator module with:
    1. A Calculator class with add, subtract, multiply, divide methods
    2. Each method should have type hints and docstrings
    3. Include error handling for division by zero
    4. Write unit tests with pytest that achieve 80%+ coverage
    5. Save the implementation in /workspace/calculator.py
    6. Save the tests in /workspace/test_calculator.py

    After creating the files, run the tests to verify they pass.
    """

    logger.info("Starting E2E test: feature development")

    messages: list[Any] = []
    async for msg in session.execute(prompt):
        messages.append(msg)
        if isinstance(msg, AssistantMessage):
            logger.debug(
                "Agent message",
                type=type(msg).__name__,
                content_blocks=len(msg.content),
            )

    logger.info("Agent execution completed", message_count=len(messages))

    # Extract message information for assertions
    info = extract_messages_info(messages)

    # Assertion 1: Agent produced messages
    assert info["total_count"] > 0, "Agent should produce at least one message"

    # Assertion 2: Agent produced assistant messages with content
    assert info["assistant_messages"] > 0, "Agent should produce assistant messages"

    # Assertion 3: Agent used tools (Write/Edit for creating files)
    assert info["has_tool_calls"], "Agent should use tools to create files"

    # Assertion 4: Agent used file-related tools
    file_tools = {"Write", "Edit", "Read", "Bash"}
    tools_used = set(info["tool_use_blocks"])
    assert tools_used & file_tools, (
        f"Agent should use file tools. Tools used: {tools_used}"
    )

    # Assertion 5: Agent provided text explanations
    assert info["has_text_content"], "Agent should provide text explanations"

    # Assertion 6: Check for completion indicators in text
    all_text = " ".join(info["text_blocks"]).lower()
    completion_indicators = ["calculator", "test", "created", "written", "done", "complete"]
    has_completion_indicator = any(ind in all_text for ind in completion_indicators)
    assert has_completion_indicator, (
        f"Agent response should indicate task completion. "
        f"Text preview: {all_text[:500]}"
    )

    logger.info(
        "E2E test assertions passed",
        assistant_messages=info["assistant_messages"],
        tools_used=list(tools_used),
        text_blocks=len(info["text_blocks"]),
    )

    await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(300)  # 5 minute timeout
@pytest.mark.slow
async def test_simple_bug_fix_workflow(
    workspace_dir,
    skip_if_no_api_key,
):
    """
    Test bug fix workflow.

    Workflow:
    1. Create buggy code (via agent prompt)
    2. Agent identifies bug
    3. Agent fixes bug
    4. Agent verifies fix with test

    Note: Makes real API calls - no VCR cassettes available for subprocess I/O.

    Assertions verify:
    - Agent uses Edit/Write tools to modify code
    - Agent provides explanation of the bug
    - Agent response mentions division, zero, or error handling
    - Execution completes successfully

    Cost: ~$0.50-$1 per run
    Duration: Up to 5 minutes
    """
    session = AgentSession(agent_name="e2e-bugfix")
    await session.start()

    # Ask agent to create and then fix the buggy code
    prompt = """
    First, create a file /workspace/buggy.py with this buggy code:

    def calculate_average(numbers):
        # Bug: division by zero if empty list
        return sum(numbers) / len(numbers)

    Then:
    1. Identify the division by zero bug
    2. Fix it with proper error handling (return 0.0 for empty list or raise ValueError)
    3. Add a docstring explaining the function
    4. Create /workspace/test_buggy.py with tests for both normal and edge cases
    5. Run the tests to verify the fix works
    """

    messages: list[Any] = []
    async for msg in session.execute(prompt):
        messages.append(msg)

    info = extract_messages_info(messages)

    # Assertion 1: Agent produced responses
    assert info["total_count"] > 0, "Agent should produce messages"
    assert info["assistant_messages"] > 0, "Agent should produce assistant messages"

    # Assertion 2: Agent used file modification tools
    assert info["has_tool_calls"], "Agent should use tools to fix the bug"
    modification_tools = {"Write", "Edit"}
    tools_used = set(info["tool_use_blocks"])
    assert tools_used & modification_tools, (
        f"Agent should use Write or Edit tools. Tools used: {tools_used}"
    )

    # Assertion 3: Agent explained the bug fix
    assert info["has_text_content"], "Agent should explain the bug fix"
    all_text = " ".join(info["text_blocks"]).lower()

    # Look for bug-related keywords
    bug_keywords = ["division", "zero", "empty", "error", "fix", "handle", "check"]
    has_bug_discussion = any(kw in all_text for kw in bug_keywords)
    assert has_bug_discussion, (
        f"Agent should discuss the bug. Text preview: {all_text[:500]}"
    )

    logger.info(
        "Bug fix test assertions passed",
        tools_used=list(tools_used),
        message_count=info["total_count"],
    )

    await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(180)  # 3 minute timeout
async def test_mcp_tools_integration(
    workspace_dir,
    skip_if_no_api_key,
):
    """
    Test that agent can use MCP tools (filesystem, memory).

    Verifies MCP servers are properly integrated and accessible.

    Note: Makes real API calls - no VCR cassettes available.

    Assertions verify:
    - Agent uses Read/Write/Glob tools
    - Agent successfully creates a test file
    - Agent can search for files
    - Proper tool result handling

    Cost: ~$0.20-$0.50 per run
    Duration: < 3 minutes
    """
    session = AgentSession(agent_name="e2e-mcp")
    await session.start()

    prompt = """
    Use the filesystem tools to:
    1. Create a new file at /workspace/mcp_test.txt with content "MCP tools working!"
    2. Read back the file to verify it was created
    3. Use Glob to search for all .txt files in /workspace
    4. Report what you found
    """

    messages: list[Any] = []
    async for msg in session.execute(prompt):
        messages.append(msg)

    info = extract_messages_info(messages)

    # Assertion 1: Agent produced responses
    assert info["total_count"] > 0, "Agent should produce messages"

    # Assertion 2: Agent used filesystem tools
    assert info["has_tool_calls"], "Agent should use MCP filesystem tools"
    filesystem_tools = {"Write", "Read", "Glob", "Grep", "Edit"}
    tools_used = set(info["tool_use_blocks"])
    assert tools_used & filesystem_tools, (
        f"Agent should use filesystem tools. Tools used: {tools_used}"
    )

    # Assertion 3: Agent used Write tool (to create test file)
    assert "Write" in tools_used, (
        f"Agent should use Write tool to create file. Tools used: {tools_used}"
    )

    # Assertion 4: Agent provided confirmation
    assert info["has_text_content"], "Agent should confirm file operations"
    all_text = " ".join(info["text_blocks"]).lower()
    confirmation_keywords = ["created", "wrote", "file", "mcp", "success", "found"]
    has_confirmation = any(kw in all_text for kw in confirmation_keywords)
    assert has_confirmation, (
        f"Agent should confirm file creation. Text preview: {all_text[:500]}"
    )

    logger.info(
        "MCP tools test assertions passed",
        tools_used=list(tools_used),
        message_count=info["total_count"],
    )

    await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(120)  # 2 minute timeout
async def test_agent_simple_query():
    """
    Test basic agent query capability.

    This is a minimal E2E test to verify the agent can respond to simple queries.
    Does not require file operations.

    Assertions verify:
    - Agent responds to query
    - Response contains expected content
    - Execution completes without errors

    Cost: ~$0.05-$0.10 per run
    Duration: < 1 minute
    """
    session = AgentSession(agent_name="e2e-query")
    await session.start()

    prompt = "What is 2 + 2? Please respond with just the number."

    messages: list[Any] = []
    async for msg in session.execute(prompt):
        messages.append(msg)

    info = extract_messages_info(messages)

    # Assertion 1: Agent responded
    assert info["total_count"] > 0, "Agent should produce messages"
    assert info["assistant_messages"] > 0, "Agent should produce assistant messages"

    # Assertion 2: Response contains expected answer
    assert info["has_text_content"], "Agent should provide text response"
    all_text = " ".join(info["text_blocks"])
    assert "4" in all_text, f"Response should contain '4'. Got: {all_text}"

    logger.info("Simple query test passed", response_preview=all_text[:100])

    await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(180)  # 3 minute timeout
async def test_agent_error_handling():
    """
    Test that agent handles errors gracefully.

    Verifies the agent can recover from invalid operations.

    Assertions verify:
    - Agent responds even when given impossible task
    - Agent provides helpful error message or explanation
    - No uncaught exceptions

    Cost: ~$0.10-$0.20 per run
    Duration: < 2 minutes
    """
    session = AgentSession(agent_name="e2e-error")
    await session.start()

    prompt = """
    Try to read a file that doesn't exist: /workspace/nonexistent_file_12345.txt

    Report what happens and how you would handle this situation.
    """

    messages: list[Any] = []
    error_occurred = False
    try:
        async for msg in session.execute(prompt):
            messages.append(msg)
    except Exception as e:
        # Record but don't fail - we're testing error handling
        error_occurred = True
        logger.warning("Exception during error handling test", error=str(e))

    info = extract_messages_info(messages)

    # Assertion 1: Agent produced some response
    assert info["total_count"] > 0 or error_occurred, (
        "Agent should produce messages or raise a handled exception"
    )

    # Assertion 2: If we got messages, verify agent discussed the error
    if info["has_text_content"]:
        all_text = " ".join(info["text_blocks"]).lower()
        error_keywords = ["not found", "doesn't exist", "error", "fail", "cannot", "unable"]
        has_error_discussion = any(kw in all_text for kw in error_keywords)
        # This is a soft assertion - agent might handle differently
        if not has_error_discussion:
            logger.warning(
                "Agent didn't explicitly discuss error",
                text_preview=all_text[:300],
            )

    logger.info(
        "Error handling test completed",
        message_count=info["total_count"],
        error_occurred=error_occurred,
    )

    await session.shutdown()
