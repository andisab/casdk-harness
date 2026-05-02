---
name: sample-test-skill
description: >
  Sample skill for CGF E2E testing. Tests trigger optimization.
trigger_patterns:
  - "/sample"
  - "sample test"
  - "run sample"
---

# Sample Test Skill

This skill demonstrates basic functionality for CGF testing.

## Trigger Conditions

Activate when user:
- Uses `/sample` command
- Says "sample test"
- Asks to "run sample"

## Behavior

1. Acknowledge the trigger
2. Perform sample action
3. Report results

## Output Format

```
Sample skill activated!
Action: [action performed]
Result: [success/failure]
```
