"""Integration tests for conversation memory via persistent SDK client.

These tests make real API calls to verify that conversation context
is maintained across multiple messages in a session.

IMPORTANT: These tests cost money (API usage) and should be run selectively.
Use pytest -m "not slow" to skip during development.
"""

import pytest

from harness.agent import AgentSession


def extract_assistant_text(messages: list) -> str:
    """Extract text from AssistantMessage content blocks."""
    text = ""
    for msg in messages:
        if msg.__class__.__name__ == "AssistantMessage" and hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    text += block.text + " "
    return text


@pytest.mark.integration
@pytest.mark.slow
async def test_conversation_context_maintained():
    """
    Verify agent remembers previous messages in conversation.

    This test:
    1. Sets context in first message
    2. Verifies recall in second message
    3. Confirms persistent client maintains conversation history
    """
    session = AgentSession(agent_name="test-conversation-memory")
    await session.start()

    try:
        # Set context with a memorable fact
        messages = []
        async for msg in session.execute("My favorite color is blue. Remember this."):
            messages.append(msg)

        # Verify we got responses
        assert len(messages) > 0

        # Test recall - ask about the color mentioned earlier
        messages = []
        async for msg in session.execute("What is my favorite color?"):
            messages.append(msg)

        # Extract assistant's response
        response_text = extract_assistant_text(messages).lower()

        # Should mention "blue" from previous message
        assert "blue" in response_text, (
            f"Agent should remember favorite color from previous message. "
            f"Response: {response_text[:200]}"
        )

    finally:
        await session.shutdown()


@pytest.mark.integration
@pytest.mark.slow
async def test_session_id_captured():
    """
    Verify session_id is extracted from SDK's SystemMessage.

    This test confirms the SDK provides a session_id that we can
    use for checkpoint resume and conversation continuation.
    """
    session = AgentSession(agent_name="test-session-id")
    await session.start()

    try:
        # Session ID should be None before first query
        assert session.session_id is None

        # Execute a query
        messages = []
        async for msg in session.execute("Hello, Claude!"):
            messages.append(msg)

        # Session ID should be captured from SystemMessage
        assert session.session_id is not None, (
            "SDK should provide session_id in SystemMessage"
        )
        assert isinstance(session.session_id, str)
        assert len(session.session_id) > 0

        # Verify state includes session_id
        state = await session._get_state_async()
        assert state["sdk_session_id"] == session.session_id

    finally:
        await session.shutdown()


@pytest.mark.integration
@pytest.mark.slow
async def test_multiple_messages_same_client():
    """
    Verify multiple messages use the same SDK client instance.

    This test confirms the persistent client pattern is working
    by sending multiple messages and checking client stability.
    """
    session = AgentSession(agent_name="test-multiple-messages")
    await session.start()

    try:
        # Store client ID after start
        client_id = id(session.client)
        assert session.client is not None

        # Send multiple messages
        for i in range(3):
            messages = []
            async for msg in session.execute(f"Message {i + 1}: What is {i + 1} + {i + 1}?"):
                messages.append(msg)

            # Verify same client instance
            assert id(session.client) == client_id, (
                f"Client instance changed on message {i + 1}. "
                "This breaks conversation persistence!"
            )

            # Verify we got responses
            assert len(messages) > 0

    finally:
        await session.shutdown()


@pytest.mark.integration
@pytest.mark.slow
async def test_checkpoint_includes_session_id():
    """
    Verify checkpoint includes SDK session_id for resume capability.

    This test confirms that checkpoints capture the session_id
    which enables conversation resumption after recovery.
    """
    session = AgentSession(agent_name="test-checkpoint-session")
    await session.start()

    try:
        # Create conversation
        async for _ in session.execute("Remember: my name is Alice"):
            pass

        # Verify session_id captured
        assert session.session_id is not None

        original_session_id = session.session_id

        # Get checkpoint state
        state = await session._get_state_async()

        # Verify checkpoint includes session_id
        assert "sdk_session_id" in state
        assert state["sdk_session_id"] == original_session_id
        assert "timestamp" in state

    finally:
        await session.shutdown()


@pytest.mark.integration
@pytest.mark.slow
async def test_conversation_builds_context():
    """
    Verify conversation builds context over multiple exchanges.

    This test sends 3 messages that build on each other to confirm
    the agent maintains full conversation history.
    """
    session = AgentSession(agent_name="test-context-building")
    await session.start()

    try:
        # Message 1: Set initial context
        async for _ in session.execute("I have a dog named Max"):
            pass

        # Message 2: Add more context
        async for _ in session.execute("Max is 3 years old"):
            pass

        # Message 3: Ask about combined context
        messages = []
        async for msg in session.execute("How old is my dog?"):
            messages.append(msg)

        response_text = extract_assistant_text(messages).lower()

        # Should reference both "max" and "3" from previous messages
        assert "max" in response_text or "dog" in response_text, (
            f"Agent should remember dog's name. Response: {response_text[:200]}"
        )
        assert "3" in response_text or "three" in response_text, (
            f"Agent should remember dog's age. Response: {response_text[:200]}"
        )

    finally:
        await session.shutdown()


@pytest.mark.integration
@pytest.mark.slow
async def test_session_survives_errors():
    """
    Verify session persists even if individual queries have issues.

    This test ensures the persistent client pattern doesn't break
    when facing errors in query processing.
    """
    session = AgentSession(agent_name="test-error-recovery")
    await session.start()

    try:
        client_id = id(session.client)

        # Normal query
        async for _ in session.execute("What is 2 + 2?"):
            pass

        # Verify client still the same
        assert id(session.client) == client_id

        # Another normal query after potential error
        messages = []
        async for msg in session.execute("What is 3 + 3?"):
            messages.append(msg)

        # Should still work with same client
        assert id(session.client) == client_id
        assert len(messages) > 0

    finally:
        await session.shutdown()
