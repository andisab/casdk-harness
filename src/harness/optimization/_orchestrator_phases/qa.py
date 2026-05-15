"""QA phase implementation.

For now, auto-accepts the proposed structure and writes a decisions
record.  In a full implementation, this would use interactive Q&A via
an initializer agent.

Function is mounted onto :class:`MultiResourceOrchestrator` as
``_run_qa_phase``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from harness.optimization._orchestrator_helpers import validate_write_path

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def run_phase(self: MultiResourceOrchestrator) -> None:
    """Run Q&A phase - gather user input on structure decisions.

    For now, auto-accept proposed structure. In full implementation,
    this would use interactive Q&A via an initializer agent.
    """
    if not self._spec or not self._state:
        return

    logger.info("Q&A: Auto-accepting proposed structure")

    # Create decisions file
    workspace = self.config.workspace_dir
    sessions_dir = workspace / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = sessions_dir / "qa-decisions.json"

    # Validate path
    validate_write_path(decisions_path, workspace)

    import json

    decisions = {
        "spec_name": self._spec.name,
        "decided_at": datetime.now(UTC).isoformat(),
        "structure_accepted": True,
        "modifications": [],
        "notes": "Auto-accepted proposed structure (no Q&A required)",
    }

    with open(decisions_path, "w") as f:
        json.dump(decisions, f, indent=2)

    self._state.user_decisions_path = str(decisions_path)
    self._save_state()

    logger.info("Q&A: Complete", decisions_path=str(decisions_path))
