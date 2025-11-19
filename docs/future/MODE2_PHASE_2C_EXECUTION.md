# MODE2 Phase 2C: Autonomous Execution

**Phase**: 2C - Execution
**Duration**: 1 week
**Dependencies**: Phase 2B (Orchestration) complete

## Goals

Implement end-to-end autonomous mode execution:
1. Create autonomous.py entry point for Mode 2
2. Add Make targets for autonomous commands
3. Implement graceful shutdown with checkpoint save
4. Add progress monitoring via Grafana
5. Document Mode 2 usage in README

## Deliverables

- [ ] `src/harness/autonomous.py` - Main entry point for Mode 2
- [ ] Update `Makefile` with autonomous mode targets
- [ ] Grafana dashboard updates for objective tracking
- [ ] End-to-end tests for complete workflows
- [ ] Documentation updates in README.md

## Component Specifications

### Component 7: Autonomous Execution Entry Point

**Purpose:** Main entry point for Mode 2 autonomous sessions

**Location:** `src/harness/autonomous.py` (new file)

**Key Responsibilities:**
- Load objective from YAML
- Initialize agents and orchestrator
- Start autonomous execution loop
- Handle graceful shutdown (SIGTERM, SIGINT)
- Save final checkpoint on exit
- Provide status updates via logs/metrics

**Interface:**
```python
async def run_autonomous_session(objective_path: Path) -> None:
    """Run autonomous session from objective file."""

async def main() -> None:
    """CLI entry point for autonomous mode."""
```

**Implementation Estimate:** ~200 lines

**Usage:**
```bash
# Via Make
make autonomous OBJ=objectives/feature-implementation.yaml

# Direct
python -m harness.autonomous objectives/feature-implementation.yaml
```

## User Journey Examples

### Journey 1: Quick Bug Fix (5 minutes)

**User Input:**
```bash
make objective
> "The logout endpoint isn't clearing Redis sessions properly"
```

**System Response:**
```
🔍 Analyzing issue...
✓ Found logout endpoint at api/auth/logout.py
✓ Identified potential issue with session.delete() call

📋 Bug Fix Plan:

I'll investigate and fix the session clearing issue:
1. Debug current session handling
2. Fix Redis session deletion
3. Add test to verify fix

Estimated: 5-10 minutes, < $0.50

Proceed? [Y/n]
```

**Result:** Bug fixed with proper session cleanup and test coverage.

### Journey 2: Feature with Discussion (3-4 hours)

**Phase 1 - Understanding:**
```bash
make objective
> "Add a user dashboard to the application"
```

**System:**
```
🔍 Analyzing your codebase...
✓ Found React frontend at src/components/
✓ Found Express API at src/api/
✓ Existing user model with basic profile
✓ No dashboard component found

I can help you build a user dashboard. Let me understand what you need...
```

**Phase 2 - Discussion:**
```
What should the dashboard include?

1. Profile section?
   [x] View profile
   [x] Edit profile
   [x] Avatar upload
   [ ] Account settings

2. Activity/Data displays?
   [x] Recent activity feed
   [x] Statistics/metrics
   [ ] Notifications
   [ ] Calendar

3. User preferences?
   [x] Dark mode toggle
   [ ] Language selection
   [ ] Email preferences

Any specific requirements?
> "Activity feed should show last 10 actions and auto-refresh"

Got it! Should this be mobile-responsive?
> "Yes, mobile-first design"

Perfect! Here's my implementation plan...
```

**Phase 3 - Approval:**
```
📋 User Dashboard Implementation Plan

Based on our discussion:

Backend (1-2 hours):
  ✓ Profile update endpoint with avatar
  ✓ Activity feed API with pagination
  ✓ Real-time updates via WebSocket
  ✓ User preferences endpoint

Frontend (1-2 hours):
  ✓ Dashboard layout (mobile-first)
  ✓ Profile component with edit mode
  ✓ Activity feed with auto-refresh
  ✓ Statistics cards
  ✓ Dark mode implementation

Testing & Polish (1 hour):
  ✓ Component tests
  ✓ API integration tests
  ✓ Mobile responsiveness testing
  ✓ Accessibility audit

Estimated: 3-4 hours, $4-7

Ready to start building?
[Y] Yes, let's build
[e] Edit the plan
[d] Discuss more
[s] Save for later
> Y
```

**Result:** Dashboard built exactly to specifications with all discussed features.

### Journey 3: GitHub Issue Integration (1-2 hours)

**User Input:**
```bash
make objective-from-issue ISSUE=https://github.com/user/repo/issues/42
```

**System Response:**
```
🔗 GitHub Issue #42: "Add rate limiting to API"

Labels: enhancement, security
Priority: high

📋 Rate Limiting Implementation:

Based on issue requirements:
- 100 requests/minute per user
- Redis-based counting
- 429 responses with Retry-After header

I will:
1. Add rate limiter middleware
2. Configure per-endpoint limits
3. Implement Redis counters
4. Add monitoring metrics
5. Write comprehensive tests

Estimated: 1-2 hours, $2-3

Proceed? [Y/n]
```

**Result:** Rate limiting implemented with monitoring and tests.

## Usage Examples

### Example 1: Natural Language Objective

```bash
# Simple natural language input
make objective
> "Fix the typo in README.md on line 42"

# System generates plan automatically
# Shows summary for approval
# Executes upon confirmation

# Monitor progress (in another terminal)
make status

# Output:
# ┌─────────────────────────────────────────┐
# │  Session: main_2025-11-11T10:30:45     │
# │  Objective: Fix Documentation Typo      │
# │  Phase: Fix (1/1)                       │
# │  Status: ✅ Completed                   │
# │  Duration: 45 seconds                   │
# │  Cost: $0.02                            │
# └─────────────────────────────────────────┘
```

### Example 2: PRD-Based Feature Implementation

```bash
# 1. Provide PRD document
make objective-from-prd PRD=docs/auth-api-spec.md

# 2. Review generated plan (shown in terminal)
# System analyzes PRD and creates multi-phase plan

# 3. Optionally edit before proceeding
# Press 'e' to edit, 'Y' to proceed

# 4. Run with monitoring
make dev  # Start all services in background
# Objective executes automatically after approval

# 5. View progress in Grafana
make metrics  # Opens http://localhost:3000
# Navigate to "Autonomous Sessions" dashboard

# 6. Check logs
make logs-autonomous

# 7. If interrupted, resume
make autonomous-resume SESSION=main_2025-11-11T10:30:45
```

### Example 3: Debugging a Failed Objective

```bash
# Session failed during testing phase
make show-failures SESSION=main_2025-11-11T10:30:45

# Output:
# ┌─────────────────────────────────────────────────┐
# │  Failure Report                                 │
# ├─────────────────────────────────────────────────┤
# │  Phase: Testing                                 │
# │  Task: Run integration tests                    │
# │  Retry: 2/3                                     │
# │  Error: AssertionError: test_login_endpoint     │
# │                                                 │
# │  Debugging Agent Analysis:                      │
# │  - JWT token validation missing timezone        │
# │  - Recommend: Add UTC timezone to timestamp     │
# │                                                 │
# │  Orchestrator Action:                           │
# │  - Updated task context with fix suggestion     │
# │  - Reassigned to development agent              │
# └─────────────────────────────────────────────────┘

# Review full logs
make logs-failures SESSION=main_2025-11-11T10:30:45
```

## Grafana Dashboard: Autonomous Sessions

**New Panels** (in addition to existing interactive session panels):

1. **Objective Progress** (Status Panel)
   - Shows current phase and completion percentage
   - Color-coded: Green (completed), Yellow (in progress), Red (failed)

2. **Phase Timeline** (Gantt Chart)
   - Visual timeline of phase start/end times
   - Shows which phases ran in parallel

3. **Task Queue Depth** (Graph)
   - Number of tasks in pending/in_progress/completed queues
   - Helps identify bottlenecks

4. **Agent Utilization** (Heatmap)
   - Shows which agents are active and idle
   - Helps optimize agent configuration

5. **Failure Rate by Phase** (Bar Chart)
   - Percentage of tasks that failed per phase
   - Identifies problematic phases

6. **Cost per Phase** (Stacked Area Chart)
   - API costs broken down by phase
   - Helps identify expensive operations

7. **Retry Rate** (Gauge)
   - Percentage of tasks that required retry
   - Lower is better (target: <10%)

8. **Testing Verification Time** (Graph)
   - Time taken for testing agent to verify each phase
   - Tracks test suite performance

9. **Checkpoint Frequency** (Timeline)
   - Shows when checkpoints were saved
   - Helps tune checkpoint interval

10. **Session Duration Estimate** (Stat)
    - Estimated time to completion based on current progress
    - Updates in real-time

## Make Targets for Mode 2

Add to `Makefile`:

```makefile
# ============================================================================
# Mode 2: Autonomous Sessions - Natural Language Interface
# ============================================================================

.PHONY: objective
objective: ## Interactive objective builder (natural language)
objective:
	@echo "🤖 Starting interactive objective builder..."
	@docker compose exec main-agent python -m harness.objective_builder --interactive

.PHONY: objective-from-text
objective-from-text: ## Create objective from text description
objective-from-text:
	@docker compose exec main-agent python -m harness.objective_builder --text "$(TEXT)"

.PHONY: objective-from-prd
objective-from-prd: ## Create objective from PRD document
objective-from-prd:
	@docker compose exec main-agent python -m harness.objective_builder --prd "$(PRD)"

.PHONY: objective-from-issue
objective-from-issue: ## Create objective from GitHub issue
objective-from-issue:
	@docker compose exec main-agent python -m harness.objective_builder --issue "$(ISSUE)"

.PHONY: autonomous
autonomous: ## Run autonomous session from generated objective (advanced)
autonomous:
	@echo "🤖 Starting autonomous session..."
	@docker compose exec main-agent python -m harness.autonomous $(OBJ)

.PHONY: status
status: ## Show current autonomous session status
status:
	@docker compose exec main-agent python -m harness.autonomous --status

.PHONY: autonomous-resume
autonomous-resume: ## Resume autonomous session from checkpoint
autonomous-resume:
	@echo "🔄 Resuming session $(SESSION)..."
	@docker compose exec main-agent python -m harness.autonomous --resume $(SESSION)

.PHONY: autonomous-pause
autonomous-pause: ## Pause running autonomous session
autonomous-pause:
	@docker compose exec main-agent python -m harness.autonomous --pause

.PHONY: autonomous-abort
autonomous-abort: ## Abort running autonomous session
autonomous-abort:
	@docker compose exec main-agent python -m harness.autonomous --abort

.PHONY: show-failures
show-failures: ## Show failure logs for session
show-failures:
	@cat logs/failures/$(SESSION)/*.log

.PHONY: logs-autonomous
logs-autonomous: ## Tail logs for autonomous session
logs-autonomous:
	@docker compose logs -f main-agent | grep autonomous

.PHONY: session-report
session-report: ## Generate session summary report
session-report:
	@docker compose exec main-agent python -m harness.autonomous --report $(SESSION)
```

## Testing Strategy for Phase 2C

### End-to-End Tests
```python
# tests/e2e/test_autonomous_execution.py
- test_simple_objective_end_to_end()
- test_multi_phase_objective()
- test_checkpoint_recovery()
- test_graceful_shutdown()
- test_parallel_task_execution()
- test_failure_and_retry_workflow()
```

### Integration Tests
```python
# tests/integration/test_autonomous_workflow.py
- test_objective_loading_and_validation()
- test_orchestrator_initialization()
- test_progress_monitoring()
- test_session_report_generation()
```

## Implementation Order

1. **Autonomous Entry Point** (autonomous.py)
   - Load objective file
   - Initialize orchestrator
   - Start execution loop
   - Handle signals

2. **CLI Commands**
   - Add argument parsing
   - Implement status command
   - Add resume capability
   - Session management

3. **Makefile Updates**
   - Add all Mode 2 targets
   - Test each command
   - Update help text

4. **Grafana Updates**
   - Add new panels
   - Create queries
   - Test visualizations

5. **Documentation**
   - Update README
   - Add examples
   - Document commands

## Success Criteria

- [ ] Can run autonomous session from start to finish
- [ ] Graceful shutdown saves checkpoint correctly
- [ ] Resume from checkpoint works properly
- [ ] Progress visible in Grafana dashboard
- [ ] All Make commands function correctly
- [ ] Session report provides useful summary
- [ ] E2E tests pass for complete workflows

## Next Phase Preview

Phase 2D (Polish & Observability) will enhance monitoring:
- Comprehensive Grafana dashboards
- Additional Prometheus metrics
- Session summary reports
- Cost tracking and enforcement
- Performance optimization