# Future Features - Low Priority

**Status**: Proposed, not currently scheduled for implementation
**Last Updated**: October 26, 2025

These features are deferred until core harness functionality is complete and polished.

## Current Focus

Before implementing these proposals, we're focused on:
- ✅ Completing Phase 0.7 (Enhanced Observability) testing
- ✅ Committing working changes to git
- ✅ Improving test coverage from 61% to 80%+
- ✅ Polishing core Docker orchestration
- ✅ Stabilizing interactive mode and monitoring

## Proposals in This Directory

### 1. Frontend Web Application
**File**: [frontend-implementation.md](./frontend-implementation.md)

**Overview**: Guide for building a **separate** web application (React + FastAPI) that uses the harness as a backend service.

**Important**: This describes a completely separate project, not part of the harness itself. The harness is a CLI/Docker tool.

**Why Deferred**: Harness needs to be rock-solid before building UI on top of it.

### 2. Frontend Feature Roadmap
**File**: [frontend-roadmap.md](./frontend-roadmap.md)

**Overview**: Advanced UI features for the web frontend (artifacts, syntax highlighting, file uploads, etc.).

**Why Deferred**: Depends on #1 being implemented first.

## When Will These Be Implemented?

These proposals will be reconsidered after:
- [ ] Phase 0.7 fully complete (observability testing done)
- [ ] All implementation files committed to git
- [ ] Test coverage reaches 80%+
- [ ] Integration tests all passing
- [ ] Core harness has been used successfully for real projects

## Priority Order (If/When Implemented)

1. **Frontend Implementation** - Requires stable harness first
2. **Frontend Features** - Requires #1 complete

Note: External Repository Support has been promoted to **Phase 1A** as it's essential infrastructure for Mode 2. See [MODE2_PHASE_1A_REPOSITORY_SUPPORT.md](./MODE2_PHASE_1A_REPOSITORY_SUPPORT.md).

---

**Note to Contributors**: Please do not work on these features yet. Focus on completing current phase and improving test coverage first.
