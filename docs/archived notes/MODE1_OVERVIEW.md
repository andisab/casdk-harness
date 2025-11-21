# Future Features & Advanced Capabilities

This appendix to FRONTEND.md covers advanced features that mirror Claude Desktop's capabilities. Features are prioritized by value/impact for software engineering workflows, especially data engineering and AI/ML development.

## Priority Matrix

| Priority | Value | Frequency | Features |
|----------|-------|-----------|----------|
| **P1: High/High** | ⭐⭐⭐⭐⭐ | 🔄🔄🔄🔄🔄 | Artifacts, Tool Visibility, Syntax Highlighting |
| **P2: High/Med** | ⭐⭐⭐⭐ | 🔄🔄🔄 | File Upload, Conversation Export |
| **P3: Med/Variable** | ⭐⭐⭐ | 🔄🔄 | Manual Approvals, Session Resume, Token Analytics |
| **P4: Nice-to-Have** | ⭐⭐ | 🔄-🔄🔄🔄🔄 | Keyboard Shortcuts, Dark Mode |

---

## Priority 1: High Value, High Frequency

### 9.1 Artifact Creation & Downloads

**Use Case**: Generate code files, notebooks, data pipelines, and documentation that users can download directly.

**Backend Implementation**:

```python
from typing import Literal
import base64
import mimetypes

class ArtifactBlock:
    """Represents a downloadable artifact"""
    def __init__(
        self, 
        identifier: str,
        type: Literal["code", "document", "notebook", "data"],
        language: str | None,
        title: str,
        content: str
    ):
        self.identifier = identifier
        self.type = type
        self.language = language
        self.title = title
        self.content = content

async def enhanced_chat_handler(client: ClaudeSDKClient, user_message: str):
    """Process messages including artifact detection"""
    await client.query(user_message)
    
    artifacts = []
    
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Parse artifacts from text (you may need custom logic)
                    # Look for patterns like "I've created a file..."
                    content = block.text
                    
                    # Detect code blocks in markdown
                    if "```" in content:
                        artifact = extract_artifact_from_markdown(content)
                        if artifact:
                            artifacts.append(artifact)
                            yield {
                                "type": "artifact",
                                "artifact": {
                                    "id": artifact.identifier,
                                    "type": artifact.type,
                                    "language": artifact.language,
                                    "title": artifact.title,
                                    "content": artifact.content
                                }
                            }
                    
                    yield {"type": "text", "content": content}
        
        # ... rest of message handling

def extract_artifact_from_markdown(text: str) -> ArtifactBlock | None:
    """Extract code artifact from markdown code blocks"""
    import re
    
    # Match ```language\n...code...\n```
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        language, code = matches[0]
        return ArtifactBlock(
            identifier=f"artifact-{hash(code)}",
            type="code",
            language=language or "text",
            title=f"Generated {language or 'code'}",
            content=code.strip()
        )
    return None

@app.get("/api/artifacts/{artifact_id}")
async def download_artifact(artifact_id: str, session_id: str):
    """Download an artifact as a file"""
    # Retrieve artifact from session storage (implement your storage)
    artifact = await get_artifact(session_id, artifact_id)
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Determine file extension
    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "html": ".html",
        "css": ".css",
        "sql": ".sql",
        "bash": ".sh",
        "markdown": ".md",
    }
    
    extension = ext_map.get(artifact.language, ".txt")
    filename = f"{artifact.title.replace(' ', '_')}{extension}"
    
    return StreamingResponse(
        iter([artifact.content.encode()]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
```

**Frontend Implementation**:

```typescript
// Enhanced hook to handle artifacts
interface Artifact {
  id: string;
  type: 'code' | 'document' | 'notebook' | 'data';
  language: string;
  title: string;
  content: string;
}

export function useClaudeConversationWithArtifacts(sessionId: string) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  
  const sendMessage = useCallback(async (content: string) => {
    // ... existing code ...
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        if (data.type === 'artifact') {
          setArtifacts(prev => [...prev, data.artifact]);
        }
        // ... handle other types
      }
    }
  }, [sessionId]);
  
  const downloadArtifact = useCallback(async (artifactId: string) => {
    const response = await fetch(
      `/api/artifacts/${artifactId}?session_id=${sessionId}`
    );
    const blob = await response.blob();
    
    // Trigger download
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = response.headers.get('content-disposition')
      ?.split('filename=')[1] || 'download.txt';
    a.click();
    window.URL.revokeObjectURL(url);
  }, [sessionId]);
  
  return {
    // ... existing returns
    artifacts,
    downloadArtifact,
  };
}

// Artifact display component
function ArtifactCard({ artifact, onDownload }: { 
  artifact: Artifact; 
  onDownload: (id: string) => void; 
}) {
  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-semibold">{artifact.title}</h4>
          <p className="text-sm text-gray-600">{artifact.language}</p>
        </div>
        <button
          onClick={() => onDownload(artifact.id)}
          className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
        >
          ⬇️ Download
        </button>
      </div>
      <pre className="bg-gray-900 text-gray-100 p-3 rounded text-sm overflow-x-auto">
        <code>{artifact.content}</code>
      </pre>
    </div>
  );
}
```

**Value**: ⭐⭐⭐⭐⭐ (Essential for code generation workflows)  
**Frequency**: 🔄🔄🔄🔄🔄 (Every coding session)

---

### 9.2 File Operations Visibility & Real-time Tool Execution

**Use Case**: Show users when Claude is reading/writing files, running bash commands, or executing other tools.

```typescript
interface ToolExecution {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed';
  input: any;
  output?: string;
  startTime: Date;
  endTime?: Date;
}

// Enhanced message processing
const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([]);

if (data.type === 'tool_use') {
  const execution: ToolExecution = {
    id: data.tool_use_id || `tool-${Date.now()}`,
    name: data.name,
    status: 'running',
    input: data.input,
    startTime: new Date(),
  };
  setToolExecutions(prev => [...prev, execution]);
} else if (data.type === 'tool_result') {
  setToolExecutions(prev => prev.map(exec => 
    exec.id === data.tool_use_id
      ? { ...exec, status: 'completed', output: data.content, endTime: new Date() }
      : exec
  ));
}

// Tool execution panel component
function ToolExecutionPanel({ executions }: { executions: ToolExecution[] }) {
  return (
    <div className="border-l-4 border-blue-500 bg-blue-50 p-3 my-2">
      <h4 className="font-semibold text-sm mb-2">🔧 Tool Executions</h4>
      {executions.map(exec => (
        <div key={exec.id} className="mb-2 text-sm">
          <div className="flex items-center gap-2">
            {exec.status === 'running' && <span className="animate-spin">⚙️</span>}
            {exec.status === 'completed' && <span>✅</span>}
            {exec.status === 'failed' && <span>❌</span>}
            <span className="font-mono font-semibold">{exec.name}</span>
            {exec.status === 'running' && <span className="text-gray-600">Running...</span>}
          </div>
          {exec.status === 'completed' && exec.output && (
            <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
              {exec.output}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
```

**Value**: ⭐⭐⭐⭐⭐ (Critical for understanding what Claude is doing)  
**Frequency**: 🔄🔄🔄🔄🔄 (Every agentic interaction)

---

### 9.3 Syntax Highlighting & Code Formatting

**Use Case**: Properly display code with syntax highlighting in multiple languages.

```typescript
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <div className="relative my-4">
      <div className="flex justify-between items-center bg-gray-800 px-4 py-2 rounded-t">
        <span className="text-sm text-gray-300">{language}</span>
        <button
          onClick={handleCopy}
          className="text-sm text-gray-300 hover:text-white flex items-center gap-2"
        >
          {copied ? '✓ Copied!' : '📋 Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// Markdown renderer with code support
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function MessageContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          return !inline && match ? (
            <CodeBlock
              code={String(children).replace(/\n$/, '')}
              language={match[1]}
            />
          ) : (
            <code className="bg-gray-100 px-1 rounded" {...props}>
              {children}
            </code>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
```

**Install dependencies**:
```bash
npm install react-syntax-highlighter react-markdown remark-gfm
npm install --save-dev @types/react-syntax-highlighter
```

**Value**: ⭐⭐⭐⭐⭐ (Essential for code readability)  
**Frequency**: 🔄🔄🔄🔄🔄 (Every code-related conversation)

---

## Priority 2: High Value, Medium Frequency

### 9.4 File Upload & Multi-modal Input

**Use Case**: Upload documents, images, CSVs for analysis; attach context files to conversations.

```python
from fastapi import File, UploadFile
import os

@app.post("/api/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """Upload a file for the session"""
    # Create session upload directory
    upload_dir = f"/tmp/sessions/{session_id}/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    
    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {
        "filename": file.filename,
        "path": file_path,
        "size": len(content),
        "type": file.content_type
    }

# Enhanced chat handler with file context
async def chat_with_files(client: ClaudeSDKClient, message: str, file_paths: list[str]):
    """Send message with file context"""
    # Read file contents
    file_contents = []
    for path in file_paths:
        with open(path, 'r') as f:
            file_contents.append(f"File: {os.path.basename(path)}\n{f.read()}")
    
    # Prepend file context to message
    enhanced_message = "\n\n".join(file_contents) + "\n\n" + message
    
    await client.query(enhanced_message)
    async for msg in client.receive_response():
        yield msg
```

```typescript
function FileUpload({ sessionId, onUpload }: { 
  sessionId: string; 
  onUpload: (filename: string) => void; 
}) {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(`/api/upload?session_id=${sessionId}`, {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      onUpload(data.filename);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleUpload}
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="p-2 border rounded hover:bg-gray-100"
      >
        {uploading ? '📤 Uploading...' : '📎 Attach File'}
      </button>
    </div>
  );
}
```

**Value**: ⭐⭐⭐⭐ (Very useful for data analysis, document Q&A)  
**Frequency**: 🔄🔄🔄 (Regular, especially for data work)

---

### 9.5 Conversation Export & History

**Use Case**: Save conversations for documentation, sharing, or resuming later.

```python
from datetime import datetime
import json

@app.get("/api/conversation/{session_id}/export")
async def export_conversation(session_id: str, format: Literal["json", "markdown"] = "json"):
    """Export conversation history"""
    # Retrieve conversation from storage
    conversation = await get_conversation_history(session_id)
    
    if format == "markdown":
        content = conversation_to_markdown(conversation)
        return StreamingResponse(
            iter([content.encode()]),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=conversation-{session_id}.md"
            }
        )
    else:
        return JSONResponse(conversation)

def conversation_to_markdown(conversation: dict) -> str:
    """Convert conversation to markdown format"""
    lines = [
        f"# Conversation Export",
        f"**Session ID**: {conversation['session_id']}",
        f"**Started**: {conversation['started_at']}",
        f"**Messages**: {len(conversation['messages'])}",
        "",
        "---",
        ""
    ]
    
    for msg in conversation['messages']:
        role = msg['role'].upper()
        lines.append(f"### {role}")
        lines.append("")
        lines.append(msg['content'])
        lines.append("")
        
        if msg.get('tool_uses'):
            lines.append("**Tools Used:**")
            for tool in msg['tool_uses']:
                lines.append(f"- {tool['name']}")
            lines.append("")
    
    return "\n".join(lines)
```

```typescript
function ExportButton({ sessionId }: { sessionId: string }) {
  const [exporting, setExporting] = useState(false);
  
  const handleExport = async (format: 'json' | 'markdown') => {
    setExporting(true);
    try {
      const response = await fetch(
        `/api/conversation/${sessionId}/export?format=${format}`
      );
      const blob = await response.blob();
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation-${sessionId}.${format === 'json' ? 'json' : 'md'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };
  
  return (
    <div className="flex gap-2">
      <button
        onClick={() => handleExport('markdown')}
        disabled={exporting}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-100"
      >
        Export as Markdown
      </button>
      <button
        onClick={() => handleExport('json')}
        disabled={exporting}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-100"
      >
        Export as JSON
      </button>
    </div>
  );
}
```

**Value**: ⭐⭐⭐⭐ (Important for documentation and knowledge retention)  
**Frequency**: 🔄🔄🔄 (Per project or important conversation)

---

## Priority 3: Medium Value, Variable Frequency

### 9.6 Manual Tool Approval & Permission Controls

**Use Case**: Review and approve tool executions before they run (alternative to `acceptEdits` mode).

```python
from enum import Enum
from asyncio import Queue

class PermissionDecision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    PENDING = "pending"

class PermissionRequest:
    def __init__(self, tool_name: str, tool_input: dict, tool_use_id: str):
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self.decision = PermissionDecision.PENDING
        self.response_queue = Queue()

permission_requests = {}  # tool_use_id -> PermissionRequest

async def check_tool_permission(input_data, tool_use_id, context):
    """Hook to request permission for tool use"""
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]
    
    # Create permission request
    request = PermissionRequest(tool_name, tool_input, tool_use_id)
    permission_requests[tool_use_id] = request
    
    # Notify frontend
    yield {
        "type": "permission_request",
        "tool_use_id": tool_use_id,
        "tool_name": tool_name,
        "tool_input": tool_input
    }
    
    # Wait for decision
    decision = await request.response_queue.get()
    
    if decision == PermissionDecision.DENY:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "User denied permission"
            }
        }
    
    return {}  # Approve

@app.post("/api/permission/{tool_use_id}")
async def respond_to_permission(tool_use_id: str, decision: PermissionDecision):
    """User responds to permission request"""
    if tool_use_id in permission_requests:
        request = permission_requests[tool_use_id]
        await request.response_queue.put(decision)
        del permission_requests[tool_use_id]
        return {"status": "ok"}
    
    return {"status": "not_found"}
```

```typescript
interface PermissionRequest {
  tool_use_id: string;
  tool_name: string;
  tool_input: any;
}

function PermissionDialog({ request, onDecide }: {
  request: PermissionRequest;
  onDecide: (toolUseId: string, approved: boolean) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-lg">
        <h3 className="text-lg font-bold mb-4">Tool Permission Required</h3>
        <div className="mb-4">
          <p className="font-semibold">Tool: {request.tool_name}</p>
          <pre className="mt-2 p-3 bg-gray-100 rounded text-sm overflow-auto">
            {JSON.stringify(request.tool_input, null, 2)}
          </pre>
        </div>
        <div className="flex gap-3 justify-end">
          <button
            onClick={() => onDecide(request.tool_use_id, false)}
            className="px-4 py-2 border rounded hover:bg-gray-100"
          >
            Deny
          </button>
          <button
            onClick={() => onDecide(request.tool_use_id, true)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Value**: ⭐⭐⭐ (Useful for sensitive operations)  
**Frequency**: 🔄🔄 (Depends on automation comfort level)

---

### 9.7 Session Resume & Context Persistence

**Use Case**: Resume conversations from previous sessions without losing context.

```python
import pickle
from pathlib import Path

class PersistentSessionManager:
    def __init__(self, storage_dir="/tmp/sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
    
    async def save_session(self, session_id: str, conversation_history: list):
        """Save session to disk"""
        session_file = self.storage_dir / f"{session_id}.pkl"
        with open(session_file, 'wb') as f:
            pickle.dump(conversation_history, f)
    
    async def load_session(self, session_id: str) -> list | None:
        """Load session from disk"""
        session_file = self.storage_dir / f"{session_id}.pkl"
        if not session_file.exists():
            return None
        
        with open(session_file, 'rb') as f:
            return pickle.load(f)
    
    async def resume_session(self, session_id: str) -> ClaudeSDKClient:
        """Resume a saved session"""
        history = await self.load_session(session_id)
        
        options = ClaudeAgentOptions(
            resume=session_id if history else None
        )
        
        client = ClaudeSDKClient(options=options)
        await client.connect()
        return client

@app.post("/api/session/resume")
async def resume_session_endpoint(session_id: str):
    """Resume a previous session"""
    manager = PersistentSessionManager()
    history = await manager.load_session(session_id)
    
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "message_count": len(history),
        "resumed": True
    }
```

**Value**: ⭐⭐⭐ (Convenient for long-running projects)  
**Frequency**: 🔄🔄 (Weekly basis for ongoing work)

---

### 9.8 Token Usage Analytics & Cost Tracking

**Use Case**: Monitor API costs and optimize token usage across sessions.

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class UsageMetrics:
    session_id: str
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    cost: float
    model: str

class UsageTracker:
    def __init__(self):
        self.metrics: list[UsageMetrics] = []
    
    def record_usage(self, session_id: str, usage: dict, model: str):
        metric = UsageMetrics(
            session_id=session_id,
            timestamp=datetime.now(),
            input_tokens=usage['input_tokens'],
            output_tokens=usage['output_tokens'],
            cost=self._calculate_cost(usage, model),
            model=model
        )
        self.metrics.append(metric)
    
    def _calculate_cost(self, usage: dict, model: str) -> float:
        """Calculate cost based on model pricing"""
        # Claude Sonnet 4.5 pricing (as of Oct 2025)
        pricing = {
            "claude-sonnet-4-20250514": {
                "input": 3.0 / 1_000_000,   # $3 per million tokens
                "output": 15.0 / 1_000_000  # $15 per million tokens
            }
        }
        
        rates = pricing.get(model, pricing["claude-sonnet-4-20250514"])
        return (
            usage['input_tokens'] * rates['input'] +
            usage['output_tokens'] * rates['output']
        )
    
    def get_stats(self, session_id: str | None = None, days: int = 7):
        cutoff = datetime.now() - timedelta(days=days)
        filtered = [
            m for m in self.metrics
            if m.timestamp > cutoff and (session_id is None or m.session_id == session_id)
        ]
        
        return {
            "total_sessions": len(set(m.session_id for m in filtered)),
            "total_tokens": sum(m.input_tokens + m.output_tokens for m in filtered),
            "total_cost": sum(m.cost for m in filtered),
            "average_tokens_per_session": (
                sum(m.input_tokens + m.output_tokens for m in filtered) / len(filtered)
                if filtered else 0
            )
        }

usage_tracker = UsageTracker()

@app.get("/api/analytics/usage")
async def get_usage_analytics(session_id: str | None = None, days: int = 7):
    """Get usage analytics"""
    return usage_tracker.get_stats(session_id, days)
```

```typescript
function UsageAnalytics({ sessionId }: { sessionId?: string }) {
  const [stats, setStats] = useState<any>(null);
  
  useEffect(() => {
    const fetchStats = async () => {
      const url = `/api/analytics/usage?days=7${
        sessionId ? `&session_id=${sessionId}` : ''
      }`;
      const response = await fetch(url);
      setStats(await response.json());
    };
    
    fetchStats();
    const interval = setInterval(fetchStats, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [sessionId]);
  
  if (!stats) return null;
  
  return (
    <div className="bg-white border rounded-lg p-4">
      <h3 className="font-bold mb-3">Usage Analytics (Last 7 Days)</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm text-gray-600">Total Sessions</p>
          <p className="text-2xl font-bold">{stats.total_sessions}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Total Tokens</p>
          <p className="text-2xl font-bold">{stats.total_tokens.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Total Cost</p>
          <p className="text-2xl font-bold">${stats.total_cost.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">Avg Tokens/Session</p>
          <p className="text-2xl font-bold">{Math.round(stats.average_tokens_per_session).toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}
```

**Value**: ⭐⭐⭐ (Important for cost control)  
**Frequency**: 🔄 (Periodic review, weekly/monthly)

---

## Priority 4: Nice-to-Have Features

### 9.9 Keyboard Shortcuts

```typescript
function KeyboardShortcuts() {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K: Focus input
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.querySelector<HTMLTextAreaElement>('#chat-input')?.focus();
      }
      
      // Cmd/Ctrl + Shift + C: Clear conversation
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'c') {
        e.preventDefault();
        // Trigger clear
      }
      
      // Escape: Stop current generation
      if (e.key === 'Escape') {
        // Trigger interrupt
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
  
  return null;
}
```

**Value**: ⭐⭐ (Quality of life improvement)  
**Frequency**: 🔄🔄🔄🔄 (Every interaction for power users)

---

### 9.10 Dark Mode

```typescript
import { useState, useEffect } from 'react';

function useDarkMode() {
  const [darkMode, setDarkMode] = useState(false);
  
  useEffect(() => {
    const isDark = localStorage.getItem('darkMode') === 'true';
    setDarkMode(isDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    }
  }, []);
  
  const toggleDarkMode = () => {
    const newMode = !darkMode;
    setDarkMode(newMode);
    localStorage.setItem('darkMode', String(newMode));
    document.documentElement.classList.toggle('dark');
  };
  
  return { darkMode, toggleDarkMode };
}
```

**Value**: ⭐⭐ (Preference-based)  
**Frequency**: 🔄 (Set once, benefits all sessions)

---

## Feature Implementation Roadmap

### Phase 1 (MVP+)
1. ✅ Basic streaming chat
2. ✅ Session management
3. ✅ Error handling
4. ⬜ **Artifact downloads** (9.1)
5. ⬜ **Syntax highlighting** (9.3)
6. ⬜ **Tool execution visibility** (9.2)

### Phase 2 (Enhanced UX)
7. ⬜ File uploads (9.4)
8. ⬜ Conversation export (9.5)
9. ⬜ Keyboard shortcuts (9.9)
10. ⬜ Token usage tracking (9.8)

### Phase 3 (Advanced Features)
11. ⬜ Manual tool approval (9.6)
12. ⬜ Session resume (9.7)
13. ⬜ Dark mode (9.10)
14. ⬜ Advanced analytics

---

## Integration Notes

### Updating the Main Chat Component

To integrate these features into your main chat component from FRONTEND.md:

```typescript
// Enhanced ClaudeChat with future features
export function EnhancedClaudeChat() {
  const [sessionId] = useState(() => `session-${Date.now()}`);
  
  // Use enhanced hook with artifacts
  const { 
    messages, 
    isStreaming, 
    artifacts,        // NEW
    toolExecutions,   // NEW
    downloadArtifact, // NEW
    // ... other existing hooks
  } = useClaudeConversationWithArtifacts(sessionId);
  
  return (
    <div className="flex flex-col h-screen">
      {/* Existing header with export button */}
      <div className="bg-white border-b p-4 flex justify-between items-center">
        {/* ... existing header content ... */}
        <ExportButton sessionId={sessionId} />  {/* NEW */}
      </div>
      
      {/* Messages with enhanced rendering */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx}>
            {/* Use MessageContent component for syntax highlighting */}
            <MessageContent content={msg.content} />  {/* ENHANCED */}
            
            {/* Show tool execution panel */}
            {msg.toolUses && msg.toolUses.length > 0 && (
              <ToolExecutionPanel executions={toolExecutions} />  {/* NEW */}
            )}
          </div>
        ))}
        
        {/* Artifact cards */}
        {artifacts.map(artifact => (
          <ArtifactCard 
            key={artifact.id}
            artifact={artifact}
            onDownload={downloadArtifact}
          />
        ))}  {/* NEW */}
      </div>
      
      {/* Input with file upload */}
      <form className="border-t bg-white p-4">
        <FileUpload sessionId={sessionId} onUpload={handleFileUpload} />  {/* NEW */}
        {/* ... existing input ... */}
      </form>
    </div>
  );
}
```

---

*This appendix is a companion to FRONTEND.md - Last updated: October 2025*
