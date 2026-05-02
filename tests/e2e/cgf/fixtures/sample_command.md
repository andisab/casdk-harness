---
name: sample-test-command
description: Sample command for CGF E2E testing
command: /sample-cmd
arguments:
  - name: input
    required: true
    description: Input value for the command
  - name: --verbose
    required: false
    description: Enable verbose output
---

# Sample Test Command

A test command for CGF schema optimization testing.

## Usage

```
/sample-cmd <input> [--verbose]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| input | Yes | Input value to process |
| --verbose | No | Show detailed output |

## Examples

```
/sample-cmd "test input"
/sample-cmd "test input" --verbose
```

## Error Handling

- Invalid input: Report error with expected format
- Missing required arg: Show usage help
