"""CGF (Claude Gradient Feedback) end-to-end tests.

Tests the complete CGF optimization pipeline:
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE

Test categories:
- Agent optimization (prompt_optimization strategy)
- Skill optimization (trigger_optimization strategy)
- Command optimization (schema_optimization strategy)
- Workflow optimization (workflow_optimization strategy)
"""
