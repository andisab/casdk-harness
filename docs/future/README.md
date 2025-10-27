# Future Features - Low Priority

**Status**: Proposed, not currently scheduled for implementation
**Last Updated**: October 26, 2025

These features are deferred until core harness functionality is complete and polished.

## Current Focus

Before implementing these proposals, we're focused on:
- ✅ Completing Phase 1.5 (Enhanced Observability) testing
- ✅ Committing working changes to git
- ✅ Improving test coverage from 61% to 80%+
- ✅ Polishing core Docker orchestration
- ✅ Stabilizing interactive mode and monitoring

## Proposals in This Directory

### 1. External Repository Support
**File**: [external-repository-support.md](./external-repository-support.md)

**Overview**: Design for working with external codebases (both local and remote repositories). Includes three approaches: git clone, volume mounting, and automated workflows.

**Why Deferred**: Current workspace-only approach works for immediate needs. This adds complexity that can wait until core features are stable.

### 2. Frontend Web Application
**File**: [frontend-implementation.md](./frontend-implementation.md)

**Overview**: Guide for building a **separate** web application (React + FastAPI) that uses the harness as a backend service.

**Important**: This describes a completely separate project, not part of the harness itself. The harness is a CLI/Docker tool.

**Why Deferred**: Harness needs to be rock-solid before building UI on top of it.

### 3. Frontend Feature Roadmap
**File**: [frontend-roadmap.md](./frontend-roadmap.md)

**Overview**: Advanced UI features for the web frontend (artifacts, syntax highlighting, file uploads, etc.).

**Why Deferred**: Depends on #2 being implemented first.

## When Will These Be Implemented?

These proposals will be reconsidered after:
- [ ] Phase 1.5 fully complete (observability testing done)
- [ ] All implementation files committed to git
- [ ] Test coverage reaches 80%+
- [ ] Integration tests all passing
- [ ] Core harness has been used successfully for real projects

## Priority Order (If/When Implemented)

1. **External Repository Support** - Most relevant to harness core functionality
2. **Frontend Implementation** - Requires stable harness first
3. **Frontend Features** - Requires #2 complete

---

**Note to Contributors**: Please do not work on these features yet. Focus on completing current phase and improving test coverage first.
