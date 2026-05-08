"""Phase implementations for :class:`MultiResourceOrchestrator`.

Each module in this package owns one phase of the optimization pipeline:

- :mod:`research` — RESEARCH phase (delegates to ``cgf-research-lead``)
- :mod:`design` — DESIGN phase (delegates to ``cgf-resource-architect``)
- :mod:`qa` — QA phase (currently auto-accepts)
- :mod:`generate` — GENERATE phase (delegates to ``context-engineer``)
- :mod:`iterate` — ITERATE phase (delegates to ``cgf-prompt-optimizer``)
- :mod:`validate` — VALIDATE phase (delegates to ``cgf-coherence-validator``)

Phase functions are mounted onto :class:`MultiResourceOrchestrator` as
methods via class-attribute assignment in
``multi_resource_orchestrator.py`` (Python's descriptor protocol binds
``self`` correctly when a regular function is assigned as a class
attribute).  The ``self`` parameter type-checks via the forward
reference ``"MultiResourceOrchestrator"``.

This split is a pure-refactor cleanup of what was a 2157-LoC orchestrator
file; behavior is unchanged.
"""
