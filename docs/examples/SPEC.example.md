# Example Spec: Simple Task API

> This is an example SPEC.md file demonstrating the format expected by autonomous mode.
> Copy this template to `workspace/SPEC.md` and customize for your project.

---

## Overview

Build a lightweight REST API for task management with basic CRUD operations.
The API should be production-ready with proper error handling, validation, and health checks.

**Target Users**: Developers learning the autonomous mode workflow
**Estimated Complexity**: Small (2-4 hours of agent work)

## Technical Requirements

### Stack
- **Language**: Python 3.12+
- **Framework**: FastAPI
- **Data Storage**: In-memory (dictionary-based, no database required)
- **Testing**: pytest with httpx for async tests

### Dependencies
```
fastapi>=0.115.0
uvicorn>=0.32.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27.0
```

## Features

### 1. Health Check Endpoint (Must-Have)
- `GET /health` returns `{"status": "healthy", "version": "1.0.0"}`
- Response time under 50ms
- Used for container orchestration readiness probes

### 2. Task CRUD Operations (Must-Have)

#### Create Task
- `POST /tasks` with JSON body: `{"title": "string", "description": "string (optional)"}`
- Returns created task with generated UUID and timestamps
- Validates title is non-empty (1-200 characters)

#### List Tasks
- `GET /tasks` returns array of all tasks
- Supports optional query param `?completed=true|false` for filtering

#### Get Single Task
- `GET /tasks/{task_id}` returns task by ID
- Returns 404 if task not found

#### Update Task
- `PUT /tasks/{task_id}` updates task fields
- Supports partial updates (only provided fields change)
- Updates `updated_at` timestamp

#### Delete Task
- `DELETE /tasks/{task_id}` removes task
- Returns 204 No Content on success
- Returns 404 if task not found

### 3. Task Completion Toggle (Should-Have)
- `POST /tasks/{task_id}/toggle` flips `completed` status
- Returns updated task

### 4. Error Handling (Must-Have)
- Consistent error response format: `{"error": "string", "detail": "string (optional)"}`
- Proper HTTP status codes (400, 404, 422, 500)
- Input validation with descriptive error messages

## Data Model

```python
Task:
  id: UUID (auto-generated)
  title: str (1-200 chars, required)
  description: str (optional, max 1000 chars)
  completed: bool (default: false)
  created_at: datetime (auto-set)
  updated_at: datetime (auto-updated)
```

## Project Structure

```
workspace/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app and routes
│   ├── models.py        # Pydantic models
│   └── store.py         # In-memory data store
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # pytest fixtures
│   └── test_api.py      # API tests
├── requirements.txt
└── README.md            # Usage instructions
```

## Acceptance Criteria

- [ ] Server starts with `uvicorn app.main:app --reload`
- [ ] Health endpoint returns 200 with correct JSON structure
- [ ] Can create a task and retrieve it by ID
- [ ] Can list all tasks and filter by completion status
- [ ] Can update task title and description
- [ ] Can toggle task completion status
- [ ] Can delete a task
- [ ] 404 returned for non-existent task IDs
- [ ] Validation errors return 422 with descriptive messages
- [ ] All tests pass with `pytest -v`
- [ ] Test coverage is 80%+ for core functionality

## Out of Scope

- Database persistence (PostgreSQL, SQLite, etc.)
- User authentication or authorization
- Pagination for task listing
- Task categories or tags
- Due dates or priority levels
- Docker containerization
- API documentation beyond auto-generated OpenAPI

## Notes for Autonomous Mode

This spec is designed to be completed in a single session. The agent should:

1. Create the project structure first
2. Implement models and data store
3. Build API endpoints incrementally
4. Write tests alongside implementation
5. Verify all acceptance criteria before marking complete

If any requirement is ambiguous, the Tech Lead agent will ask clarifying questions during the initialization phase.

---

## For External Repositories

When working on an existing repository, add a `branch` field at the top of your spec:

```markdown
# Project: Add Task API

branch: casdk-task-api

## Overview
...
```

The branch name must start with `casdk-` prefix and use lowercase letters, numbers, and hyphens only.
