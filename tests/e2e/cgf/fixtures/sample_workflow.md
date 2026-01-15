---
name: sample-test-workflow
description: Sample workflow for CGF E2E testing
type: workflow
steps:
  - name: init
    description: Initialize workflow
  - name: process
    description: Process input
  - name: finalize
    description: Complete workflow
---

# Sample Test Workflow

A multi-step workflow for CGF workflow optimization testing.

## Steps

### 1. Init
Initialize the workflow state.

### 2. Process
Process the input data.

### 3. Finalize
Complete the workflow and report results.

## State Machine

```
init → process → finalize → complete
```

## Error Handling

- Step failure: Retry up to 3 times
- Unrecoverable: Abort and report
