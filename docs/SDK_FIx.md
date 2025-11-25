    Overview

     Fix conversation memory by using the SDK's intended pattern: persistent ClaudeSDKClient with connect() → multiple query() calls → disconnect().

     ---
     Core Changes

     1. AgentSession.init() - Add Client Storage

     File: src/harness/agent.py (lines ~40-90)

     Add:
     self.client: ClaudeSDKClient | None = None
     self.session_id: str | None = None  # Track SDK session ID for resume

     Purpose: Store persistent client and session ID

     ---
     2. AgentSession.start() - Connect Once

     File: src/harness/agent.py (lines ~285-301)

     Replace existing start() with:
     async def start(self) -> None:
         """Start agent session with persistent SDK client."""
         logger.info("Starting agent session", agent=self.agent_name)
         
         # Create and connect SDK client (persistent for entire session)
         options = self._build_sdk_options()
         self.client = ClaudeSDKClient(options=options)
         await self.client.connect()
         logger.info("SDK client connected", agent=self.agent_name)
         
         # Start metrics collection
         self.metrics.start()
         self.metrics.set_active_sessions(self.agent_name, 1)
         
         # Start auto-checkpoint task
         asyncio.create_task(
             self.checkpoint_manager.auto_checkpoint(get_state_fn=self._get_state_async)
         )
         
         # Start metrics collection task
         asyncio.create_task(self.metrics.collect_system_metrics())

     Changes:
     - Create ClaudeSDKClient once
     - Use connect() instead of context manager
     - Remove async with pattern

     ---
     3. AgentSession._execute_with_retry() - Reuse Client

     File: src/harness/agent.py (lines ~367-427)

     Replace entire method:
     @retry(
         stop=stop_after_attempt(3),
         wait=wait_exponential(multiplier=1, min=4, max=10),
         reraise=True,
     )
     async def _execute_with_retry(
         self,
         prompt: str,
         **kwargs: Any,
     ) -> AsyncGenerator[dict[str, Any], None]:
         """Execute using persistent SDK client (maintains conversation history)."""
         
         if not self.client:
             raise RuntimeError("SDK client not connected. Call start() first.")
         
         logger.debug("Sending query to persistent SDK client", prompt_length=len(prompt))
         
         try:
             # Send query to persistent client (maintains conversation context)
             await self.client.query(prompt)
             logger.debug("Query sent to SDK client", agent=self.agent_name)
             
             # Receive messages from persistent client
             first_message = True
             async for message in self.client.receive_response():
                 logger.debug(
                     "Message received from SDK",
                     message_type=type(message).__name__,
                     agent=self.agent_name,
                 )
                 
                 # Capture session ID from first system message
                 if first_message and message.__class__.__name__ == "SystemMessage":
                     if hasattr(message, 'data'):
                         self.session_id = message.data.get("session_id")
                         logger.info(
                             "Captured SDK session ID",
                             session_id=self.session_id,
                             agent=self.agent_name
                         )
                     first_message = False
                 
                 # Track token usage from ResultMessage
                 if isinstance(message, ResultMessage) and hasattr(message, "usage"):
                     usage = message.usage
                     self.metrics.record_tokens(
                         agent=self.agent_name,
                         model=self.config.claude_model,
                         usage=usage,
                     )
                 
                 yield message
                 
         except (CLIConnectionError, CLINotFoundError) as e:
             logger.error(
                 "SDK client connection error",
                 error=str(e),
                 exc_info=True,
             )
             # Let retry decorator handle reconnection
             raise

     Key Changes:
     - Remove async with ClaudeSDKClient() block
     - Use existing self.client (persistent)
     - Capture session_id from first system message
     - Simplified error handling (retry handles it)

     ---
     4. AgentSession.shutdown() - Disconnect Once

     File: src/harness/agent.py (lines ~450-470)

     Add client disconnect at start of shutdown():
     async def shutdown(self) -> None:
         """Shutdown agent session and cleanup SDK client."""
         logger.info("Shutting down agent session", agent=self.agent_name)
         
         # Disconnect SDK client
         if self.client:
             try:
                 await self.client.disconnect()
                 logger.info("SDK client disconnected", agent=self.agent_name)
             except Exception as e:
                 logger.warning("Error disconnecting SDK client", error=str(e))
             finally:
                 self.client = None
                 self.session_id = None
         
         # ... existing cleanup code (metrics, message broker, etc.)

     Purpose: Clean shutdown of persistent client

     ---
     5. Add Session Resume Capability (Optional Enhancement)

     File: src/harness/agent.py (new method)

     async def resume_from_session_id(self, session_id: str) -> None:
         """Resume conversation from a previous session ID.
         
         Args:
             session_id: SDK session ID to resume from
             
         Note: Call this BEFORE first execute() after start()
         """
         if not self.client:
             raise RuntimeError("SDK client not connected. Call start() first.")
         
         logger.info("Resuming from session", session_id=session_id, agent=self.agent_name)
         self.session_id = session_id
         
         # Next query() will automatically use this session_id if we pass it
         # (Implementation note: SDK handles resume automatically when session_id is known)

     Purpose: Enable checkpoint recovery with conversation context

     ---
     6. Update _get_state_async() - Include Session ID

     File: src/harness/agent.py (existing method, add session_id)

     Add to state dict:
     async def _get_state_async(self) -> dict[str, Any]:
         """Get current session state for checkpointing."""
         return {
             **self.state,
             "sdk_session_id": self.session_id,  # ← Add this
             "timestamp": datetime.now().isoformat(),
         }

     Purpose: Checkpoint includes SDK session ID for resume

     ---
     7. Update recover_from_checkpoint() - Resume Session

     File: src/harness/agent.py (existing method, enhance)

     After loading checkpoint state:
     async def recover_from_checkpoint(self) -> bool:
         """Recover session from latest checkpoint."""
         latest = self.checkpoint_manager.load_latest_checkpoint()
         
         if not latest:
             return False
         
         logger.info("Recovering from checkpoint", timestamp=latest.get("timestamp"))
         
         # Restore state
         self.state.update(latest)
         
         # Resume SDK session if session_id exists
         if "sdk_session_id" in latest and latest["sdk_session_id"]:
             try:
                 await self.resume_from_session_id(latest["sdk_session_id"])
                 logger.info(
                     "Resumed SDK conversation from checkpoint",
                     session_id=latest["sdk_session_id"]
                 )
             except Exception as e:
                 logger.warning(
                     "Could not resume SDK session, starting fresh",
                     error=str(e)
                 )
         
         return True

     Purpose: Automatic conversation resume on recovery

     ---
     What Gets Removed

     DELETE: Entire context manager pattern

     # REMOVE this entire block from _execute_with_retry():
     async with ClaudeSDKClient(options=options) as client:
         await client.query(prompt)
         async for message in client.receive_response():
             yield message

     DELETE: _build_sdk_options() call from _execute_with_retry()

     It's now only called once in start(), not every execute.

     ---
     Benefits

     ✅ Conversation Memory

     - Claude remembers all previous messages in the session
     - Natural multi-turn conversations work

     ✅ Proper SDK Usage

     - Follows official SDK design pattern
     - Uses built-in session management
     - Leverages SDK's conversation context

     ✅ Performance Improvement

     - No subprocess creation overhead per message
     - Persistent connection reduces latency
     - Options built once, not per-message

     ✅ Enhanced Fault Tolerance

     - Session IDs captured for resume
     - Can recover conversations from checkpoints
     - Graceful degradation (fresh session if resume fails)

     ✅ Future-Proof

     - Enables fork_session (explore alternative paths)
     - Enables mid-conversation model switching
     - Compatible with SDK evolution

     ---
     Testing Strategy

     1. Unit Test - Client Persistence

     File: tests/unit/test_agent_conversation.py (new)

     async def test_client_created_once():
         """Verify client is created once and reused."""
         session = AgentSession(agent_name="test")
         await session.start()
         
         client_id = id(session.client)
         
         # Multiple executes use same client
         async for _ in session.execute("Message 1"):
             pass
         async for _ in session.execute("Message 2"):
             pass
         
         assert id(session.client) == client_id  # Same instance
         
         await session.shutdown()

     2. Integration Test - Conversation Memory

     File: tests/integration/test_conversation_memory.py (new)

     @pytest.mark.integration
     async def test_conversation_context_maintained():
         """Verify agent remembers previous messages."""
         session = AgentSession(agent_name="test")
         await session.start()
         
         # Set context
         async for _ in session.execute("My favorite color is blue"):
             pass
         
         # Test recall
         messages = []
         async for msg in session.execute("What is my favorite color?"):
             messages.append(msg)
         
         # Should mention "blue"
         response_text = extract_assistant_text(messages)
         assert "blue" in response_text.lower()
         
         await session.shutdown()

     3. Integration Test - Session ID Capture

     async def test_session_id_captured():
         """Verify session_id is extracted from SDK."""
         session = AgentSession(agent_name="test")
         await session.start()
         
         assert session.session_id is None  # Before first query
         
         async for _ in session.execute("Hello"):
             pass
         
         assert session.session_id is not None  # Captured from SystemMessage
         assert isinstance(session.session_id, str)
         
         await session.shutdown()

     4. Integration Test - Checkpoint Resume

     async def test_checkpoint_resume_with_session():
         """Verify checkpoint includes and restores session_id."""
         session = AgentSession(agent_name="test")
         await session.start()
         
         # Create conversation
         async for _ in session.execute("Remember: my name is Alice"):
             pass
         
         original_session_id = session.session_id
         
         # Save checkpoint
         checkpoint_file = session.checkpoint_manager.save_checkpoint(
             await session._get_state_async()
         )
         
         await session.shutdown()
         
         # New session, recover from checkpoint
         session2 = AgentSession(agent_name="test")
         await session2.start()
         recovered = await session2.recover_from_checkpoint()
         
         assert recovered
         assert session2.session_id == original_session_id
         
         await session2.shutdown()

     ---
     Migration & Rollback

     No Data Migration Required

     - Existing checkpoints work (just won't have session_id)
     - New checkpoints will include session_id
     - Backward compatible

     Rollback Strategy

     If issues arise:
     1. Git revert the commit
     2. Restart containers: make down && make dev
     3. Old pattern resumes (stateless conversations)

     ---
     Implementation Checklist

       a. Add self.client and self.session_id to __init__
       b. Update start() with connect()
       c. Refactor _execute_with_retry() to reuse client
       d. Update shutdown() with disconnect()
       e. Add resume_from_session_id() method
       f. Update _get_state_async() to include session_id
       g. Update recover_from_checkpoint() to resume session
       h. Write unit tests
       i. Write integration tests
       j. Manual testing with make interactive
       k. Update CLAUDE.md (remove "stateless" warnings)

     Estimated Time: 2-3 hours
     Risk: Low (well-documented SDK pattern, good test coverage)
     Impact: High (fixes major UX issue, aligns with SDK design)