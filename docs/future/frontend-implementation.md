# Frontend Implementation Guide for ClaudeSDKClient

This guide provides best practices for building a frontend wrapper for conversation loops with Claude Agent SDK: ClaudeSDKClient.

## Architecture Overview

**Backend (Python)**: ClaudeSDKClient handles the agent loop, tool execution, and message streaming

**Frontend (React/Next.js)**: Manages UI state, user input, and receives streamed responses via API routes

## Table of Contents

1. [Session Management Strategy](#1-session-management-strategy)
2. [Message Processing Loop](#2-message-processing-loop)
3. [API Route Implementation](#3-api-route-implementation-fastapi)
4. [React Hook for Conversation Management](#4-react-hook-for-conversation-management)
5. [Chat Component](#5-chat-component)
6. [Error Handling & Recovery](#6-error-handling--recovery)
7. [Performance Optimizations](#7-performance-optimizations)
8. [Production Considerations](#8-production-considerations)

---

## 1. Session Management Strategy

ClaudeSDKClient maintains conversation context across multiple exchanges, unlike `query()` which creates a new session each time.

### When to Use ClaudeSDKClient

- Building chat interfaces with context retention
- Users need follow-up conversations
- You want interrupt support during long-running tasks
- Custom tools and hooks are required

### Session Management Pattern

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class ConversationManager:
    def __init__(self):
        self.clients = {}  # session_id -> client mapping

    async def get_or_create_client(self, session_id: str):
        if session_id not in self.clients:
            options = ClaudeAgentOptions(
                model="claude-sonnet-4-20250514",
                system_prompt="Your system prompt",
                allowed_tools=["WebFetch", "Read", "Write"],
                permission_mode="acceptEdits"
            )
            client = ClaudeSDKClient(options=options)
            await client.connect()
            self.clients[session_id] = client
        return self.clients[session_id]

    async def cleanup_session(self, session_id: str):
        if session_id in self.clients:
            await self.clients[session_id].disconnect()
            del self.clients[session_id]
```

---

## 2. Message Processing Loop

The `receive_response()` method returns messages until and including a `ResultMessage`, while `receive_messages()` provides all messages as an async iterator.

### Message Handler

```python
from claude_agent_sdk import (
    AssistantMessage, TextBlock, ThinkingBlock,
    ToolUseBlock, ToolResultBlock, ResultMessage
)

async def chat_handler(client: ClaudeSDKClient, user_message: str):
    """Process messages and yield to frontend"""
    await client.query(user_message)

    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield {"type": "text", "content": block.text}
                elif isinstance(block, ThinkingBlock):
                    yield {"type": "thinking", "content": block.thinking}
                elif isinstance(block, ToolUseBlock):
                    yield {
                        "type": "tool_use",
                        "name": block.name,
                        "input": block.input
                    }

        elif isinstance(message, ToolResultBlock):
            yield {"type": "tool_result", "content": message.content}

        elif isinstance(message, ResultMessage):
            yield {
                "type": "result",
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens
                }
            }
```

---

## 3. API Route Implementation (FastAPI)

### Streaming Endpoint

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

app = FastAPI()
conversation_manager = ConversationManager()

class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Streaming endpoint for chat"""
    client = await conversation_manager.get_or_create_client(request.session_id)

    async def event_stream():
        try:
            async for event in chat_handler(client, request.message):
                # Server-Sent Events format
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.post("/api/chat/interrupt")
async def interrupt_endpoint(session_id: str):
    """Interrupt current operation"""
    client = await conversation_manager.get_or_create_client(session_id)
    await client.interrupt()
    return {"status": "interrupted"}

@app.post("/api/chat/end")
async def end_session_endpoint(session_id: str):
    """End a conversation session"""
    await conversation_manager.cleanup_session(session_id)
    return {"status": "session_ended"}
```

---

## 4. React Hook for Conversation Management

### Custom Hook Implementation

```typescript
// hooks/useClaudeConversation.ts
import { useState, useCallback, useRef } from 'react';

interface ToolUse {
  name: string;
  input: any;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  toolUses?: ToolUse[];
}

interface UsageStats {
  input_tokens: number;
  output_tokens: number;
}

export function useClaudeConversation(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentThinking, setCurrentThinking] = useState('');
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    setIsStreaming(true);

    // Add user message immediately
    const userMessage: Message = { role: 'user', content };
    setMessages(prev => [...prev, userMessage]);

    // Initialize assistant message
    let assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, session_id: sessionId }),
        signal: abortControllerRef.current.signal,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'text') {
              assistantMessage.content += data.content;
              setMessages(prev => [...prev.slice(0, -1), { ...assistantMessage }]);
            } else if (data.type === 'thinking') {
              setCurrentThinking(data.content);
            } else if (data.type === 'tool_use') {
              assistantMessage.toolUses = [
                ...(assistantMessage.toolUses || []),
                { name: data.name, input: data.input }
              ];
              setMessages(prev => [...prev.slice(0, -1), { ...assistantMessage }]);
            } else if (data.type === 'tool_result') {
              // Optional: Show tool results in UI
              console.log('Tool result:', data.content);
            } else if (data.type === 'result') {
              // Handle completion with usage stats
              setUsageStats(data.usage);
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Request cancelled');
      } else {
        console.error('Streaming error:', error);
        // Add error message to chat
        setMessages(prev => [
          ...prev.slice(0, -1),
          {
            role: 'assistant',
            content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
          }
        ]);
      }
    } finally {
      setIsStreaming(false);
      setCurrentThinking('');
      abortControllerRef.current = null;
    }
  }, [sessionId]);

  const interrupt = useCallback(async () => {
    // Cancel the fetch request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Also tell the backend to interrupt
    try {
      await fetch('/api/chat/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (error) {
      console.error('Interrupt error:', error);
    }
  }, [sessionId]);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setUsageStats(null);
  }, []);

  const endSession = useCallback(async () => {
    await fetch('/api/chat/end', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    clearConversation();
  }, [sessionId, clearConversation]);

  return {
    messages,
    isStreaming,
    currentThinking,
    usageStats,
    sendMessage,
    interrupt,
    clearConversation,
    endSession,
  };
}
```

---

## 5. Chat Component

### Main Chat Interface

```typescript
// components/ClaudeChat.tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import { useClaudeConversation } from '@/hooks/useClaudeConversation';

export function ClaudeChat() {
  const [input, setInput] = useState('');
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isStreaming,
    currentThinking,
    usageStats,
    sendMessage,
    interrupt,
    clearConversation,
    endSession
  } = useClaudeConversation(sessionId);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentThinking]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    await sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b p-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold">Claude Agent Chat</h1>
          <p className="text-sm text-gray-500">Session: {sessionId}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={clearConversation}
            className="px-3 py-1 text-sm border rounded hover:bg-gray-100"
          >
            Clear
          </button>
          <button
            onClick={endSession}
            className="px-3 py-1 text-sm border rounded hover:bg-gray-100"
          >
            End Session
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg">Start a conversation with Claude</p>
            <p className="text-sm mt-2">Your messages will appear here</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[70%] rounded-lg p-3 ${
              msg.role === 'user'
                ? 'bg-blue-500 text-white'
                : 'bg-white border shadow-sm'
            }`}>
              {/* Message content */}
              <div className="whitespace-pre-wrap">{msg.content}</div>

              {/* Show tool uses */}
              {msg.toolUses && msg.toolUses.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  {msg.toolUses.map((tool, i) => (
                    <div key={i} className="text-sm text-gray-600 flex items-center gap-2">
                      <span>🔧</span>
                      <span className="font-mono">{tool.name}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Show thinking if available */}
              {msg.thinking && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <div className="text-sm text-gray-600 italic">
                    💭 {msg.thinking}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Current thinking (streaming) */}
        {currentThinking && (
          <div className="flex justify-start">
            <div className="max-w-[70%] rounded-lg p-3 bg-gray-100 border border-gray-300">
              <div className="text-sm text-gray-600 italic">
                💭 {currentThinking}
              </div>
            </div>
          </div>
        )}

        {/* Streaming indicator */}
        {isStreaming && !currentThinking && (
          <div className="flex justify-start">
            <div className="bg-white border shadow-sm rounded-lg p-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
                <span className="text-sm text-gray-500">Claude is thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Usage Stats */}
      {usageStats && (
        <div className="px-4 py-2 bg-gray-100 border-t text-xs text-gray-600 flex gap-4">
          <span>Input tokens: {usageStats.input_tokens}</span>
          <span>Output tokens: {usageStats.output_tokens}</span>
          <span>Total: {usageStats.input_tokens + usageStats.output_tokens}</span>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t bg-white p-4">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            className="flex-1 border rounded px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            rows={1}
            style={{ minHeight: '42px', maxHeight: '200px' }}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStreaming ? 'Sending...' : 'Send'}
          </button>
          {isStreaming && (
            <button
              type="button"
              onClick={interrupt}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
            >
              Stop
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
```

---

## 6. Error Handling & Recovery

### Backend Error Handling

```python
from claude_agent_sdk import ClaudeSDKError, CLIConnectionError
import asyncio

async def robust_chat_handler(client: ClaudeSDKClient, message: str):
    """Error-resilient message handler with retry logic"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            await client.query(message)
            async for msg in client.receive_response():
                yield msg
            break
        except CLIConnectionError as e:
            if attempt < max_retries - 1:
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
                await client.disconnect()
                await client.connect()
            else:
                yield {
                    "type": "error",
                    "message": f"Connection failed after {max_retries} attempts: {str(e)}"
                }
        except ClaudeSDKError as e:
            yield {"type": "error", "message": f"SDK error: {str(e)}"}
            break
        except Exception as e:
            yield {"type": "error", "message": f"Unexpected error: {str(e)}"}
            break
```

### Frontend Error Boundaries

```typescript
// components/ErrorBoundary.tsx
import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded">
          <h2 className="text-red-800 font-bold">Something went wrong</h2>
          <p className="text-red-600 mt-2">{this.state.error?.message}</p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="mt-4 px-4 py-2 bg-red-500 text-white rounded"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

## 7. Performance Optimizations

### Backend Optimizations

```python
# Context Management
options = ClaudeAgentOptions(
    max_thinking_tokens=8000,     # Limit thinking tokens
    max_turns=50,                 # Prevent infinite loops
    permission_mode="acceptEdits" # Auto-accept to reduce latency
)

# Connection Pooling
class OptimizedConversationManager:
    def __init__(self, max_sessions=100, session_timeout_minutes=30):
        self.clients = {}
        self.max_sessions = max_sessions
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.last_used = {}

    async def get_or_create_client(self, session_id: str):
        # Check if we need to cleanup old sessions
        if len(self.clients) >= self.max_sessions:
            await self._cleanup_oldest_session()

        if session_id not in self.clients:
            options = ClaudeAgentOptions(
                model="claude-sonnet-4-20250514",
                system_prompt="Your system prompt",
                allowed_tools=["WebFetch", "Read", "Write"],
            )
            client = ClaudeSDKClient(options=options)
            await client.connect()
            self.clients[session_id] = client

        self.last_used[session_id] = datetime.now()
        return self.clients[session_id]

    async def _cleanup_oldest_session(self):
        """Remove the least recently used session"""
        if not self.last_used:
            return

        oldest_session = min(self.last_used.items(), key=lambda x: x[1])[0]
        await self.cleanup_session(oldest_session)
```

### Frontend Optimizations

```typescript
// Virtual scrolling for long conversations (using react-window)
import { FixedSizeList as List } from 'react-window';

function VirtualizedMessageList({ messages }: { messages: Message[] }) {
  const Row = ({ index, style }: any) => (
    <div style={style}>
      <MessageComponent message={messages[index]} />
    </div>
  );

  return (
    <List
      height={600}
      itemCount={messages.length}
      itemSize={100}
      width="100%"
    >
      {Row}
    </List>
  );
}

// Debounce typing indicators
import { useDebounce } from 'use-debounce';

function ChatInput() {
  const [input, setInput] = useState('');
  const [debouncedInput] = useDebounce(input, 300);

  useEffect(() => {
    if (debouncedInput) {
      // Send typing indicator
      sendTypingIndicator();
    }
  }, [debouncedInput]);

  // ... rest of component
}
```

---

## 8. Production Considerations

### Session Management with Cleanup

```python
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ProductionSessionManager:
    def __init__(
        self,
        timeout_minutes=30,
        max_sessions=1000,
        cleanup_interval_seconds=300
    ):
        self.sessions = {}  # session_id -> (client, last_used, created_at)
        self.timeout = timedelta(minutes=timeout_minutes)
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval_seconds
        self._cleanup_task = None

    async def start(self):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        """Stop background cleanup and close all sessions"""
        if self._cleanup_task:
            self._cleanup_task.cancel()

        for session_id in list(self.sessions.keys()):
            await self.cleanup_session(session_id)

    async def get_or_create_client(self, session_id: str) -> ClaudeSDKClient:
        now = datetime.now()

        # Check session limits
        if session_id not in self.sessions and len(self.sessions) >= self.max_sessions:
            await self._cleanup_oldest_sessions(1)

        if session_id not in self.sessions:
            options = ClaudeAgentOptions(
                model="claude-sonnet-4-20250514",
                max_thinking_tokens=8000,
                max_turns=100,
            )
            client = ClaudeSDKClient(options=options)
            await client.connect()
            self.sessions[session_id] = (client, now, now)
            logger.info(f"Created new session: {session_id}")
        else:
            client, _, created_at = self.sessions[session_id]
            self.sessions[session_id] = (client, now, created_at)

        return self.sessions[session_id][0]

    async def cleanup_session(self, session_id: str):
        """Cleanup a specific session"""
        if session_id in self.sessions:
            client, _, _ = self.sessions[session_id]
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting session {session_id}: {e}")
            del self.sessions[session_id]
            logger.info(f"Cleaned up session: {session_id}")

    async def _periodic_cleanup(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def _cleanup_expired_sessions(self):
        """Remove sessions that haven't been used recently"""
        now = datetime.now()
        expired = [
            sid for sid, (_, last_used, _) in self.sessions.items()
            if now - last_used > self.timeout
        ]

        for sid in expired:
            await self.cleanup_session(sid)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    async def _cleanup_oldest_sessions(self, count: int):
        """Remove the N oldest sessions by last_used time"""
        if not self.sessions:
            return

        sorted_sessions = sorted(
            self.sessions.items(),
            key=lambda x: x[1][1]  # Sort by last_used
        )

        for sid, _ in sorted_sessions[:count]:
            await self.cleanup_session(sid)

    def get_session_stats(self):
        """Get statistics about active sessions"""
        now = datetime.now()
        stats = {
            "total_sessions": len(self.sessions),
            "sessions_by_age": {
                "< 5min": 0,
                "5-15min": 0,
                "15-30min": 0,
                "> 30min": 0
            }
        }

        for _, (_, last_used, _) in self.sessions.items():
            age = (now - last_used).total_seconds() / 60
            if age < 5:
                stats["sessions_by_age"]["< 5min"] += 1
            elif age < 15:
                stats["sessions_by_age"]["5-15min"] += 1
            elif age < 30:
                stats["sessions_by_age"]["15-30min"] += 1
            else:
                stats["sessions_by_age"]["> 30min"] += 1

        return stats
```

### Rate Limiting

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests_per_minute=10):
        self.max_requests = max_requests_per_minute
        self.requests = defaultdict(list)

    def check_rate_limit(self, session_id: str) -> bool:
        """Check if request is within rate limit"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[session_id] = [
            req_time for req_time in self.requests[session_id]
            if req_time > minute_ago
        ]

        # Check limit
        if len(self.requests[session_id]) >= self.max_requests:
            return False

        self.requests[session_id].append(now)
        return True

# Usage in FastAPI
rate_limiter = RateLimiter(max_requests_per_minute=20)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not rate_limiter.check_rate_limit(request.session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # ... rest of endpoint
```

### Monitoring and Logging

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def monitored_chat_handler(client: ClaudeSDKClient, message: str, session_id: str):
    """Chat handler with monitoring"""
    start_time = datetime.now()
    total_tokens = {"input": 0, "output": 0}

    try:
        await client.query(message)

        async for msg in client.receive_response():
            yield msg

            # Track token usage
            if isinstance(msg, ResultMessage):
                total_tokens["input"] = msg.usage.input_tokens
                total_tokens["output"] = msg.usage.output_tokens

                duration = (datetime.now() - start_time).total_seconds()

                logger.info(
                    f"Session {session_id} completed - "
                    f"Duration: {duration:.2f}s, "
                    f"Tokens: {total_tokens['input']} in / {total_tokens['output']} out, "
                    f"Cost: ${msg.cost:.4f}"
                )

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(
            f"Session {session_id} failed after {duration:.2f}s - Error: {str(e)}"
        )
        raise

# Add monitoring endpoint
@app.get("/api/health")
async def health_check():
    stats = session_manager.get_session_stats()
    return {
        "status": "healthy",
        "sessions": stats,
        "timestamp": datetime.now().isoformat()
    }
```

### Security Considerations

```python
# Environment-based configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    max_sessions: int = 1000
    session_timeout_minutes: int = 30
    rate_limit_per_minute: int = 20
    allowed_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()

# CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session validation
import secrets

def generate_session_id() -> str:
    """Generate a secure session ID"""
    return f"session-{secrets.token_urlsafe(32)}"

def validate_session_id(session_id: str) -> bool:
    """Validate session ID format"""
    return session_id.startswith("session-") and len(session_id) > 20
```

---

## Additional Resources

### Key References

- [Claude Agent SDK Python Documentation](https://docs.claude.com/en/api/agent-sdk/python)
- [Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [GitHub - Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python)

### Example Projects

- [NoteSmith Tutorial](https://www.datacamp.com/tutorial/how-to-use-claude-agent-sdk)
- [Claude Agent SDK Intro Examples](https://github.com/kenneth-liao/claude-agent-sdk-intro)

### Next.js & React Resources

- [Next.js Streaming Documentation](https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming)
- [React Server Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)

---

## Quick Start Checklist

- [ ] Set up backend FastAPI server with ClaudeSDKClient
- [ ] Implement ConversationManager for session handling
- [ ] Create streaming API endpoints (`/api/chat`, `/api/chat/interrupt`)
- [ ] Build React hook (`useClaudeConversation`) for frontend state
- [ ] Create chat UI component with message display
- [ ] Add error handling and retry logic
- [ ] Implement rate limiting and session cleanup
- [ ] Add monitoring and logging
- [ ] Configure CORS and security settings
- [ ] Test with multiple concurrent sessions
- [ ] Deploy and monitor in production

---

## Future Features

For advanced capabilities like artifact downloads, file uploads, syntax highlighting, tool execution visibility, and more, see the companion document:

**[FRONTEND_FUTURE_FEATURES.md](./FRONTEND_FUTURE_FEATURES.md)** - Advanced features prioritized by value and frequency for engineering workflows

Key features covered:
- **Priority 1**: Artifact downloads, tool execution visibility, syntax highlighting
- **Priority 2**: File uploads, conversation export
- **Priority 3**: Manual tool approvals, session resume, token analytics
- **Priority 4**: Keyboard shortcuts, dark mode

---

*Last updated: October 2025*
