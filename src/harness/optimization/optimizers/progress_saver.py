"""Progressive save utility for optimization runs.

Saves candidates and drafts as they are generated during optimization,
allowing recovery and comparison even if the process is interrupted.

Directory structure created:
    progress_dir/
    ├── candidates/
    │   ├── iter0_cand0_score0.91.md
    │   ├── iter0_cand1_score0.87.md
    │   └── ...
    ├── drafts/
    │   ├── draft_v1_score0.91.md   # Best after iteration 0
    │   ├── draft_v2_score0.95.md   # Best after iteration 1
    │   └── ...
    ├── baseline.md                  # Original prompt
    └── progress.json               # Running summary
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from harness.optimization.optimizers.protocol import PromptCandidate

logger = structlog.get_logger(__name__)


class ProgressSaver:
    """Saves optimization progress incrementally.

    Enables recovery from interrupted optimization runs and
    comparison of different candidates.
    """

    def __init__(self, progress_dir: str | Path, agent_name: str) -> None:
        """Initialize the progress saver.

        Args:
            progress_dir: Directory to save progress files.
            agent_name: Name of the agent being optimized.
        """
        self.progress_dir = Path(progress_dir)
        self.agent_name = agent_name
        self.candidates_dir = self.progress_dir / "candidates"
        self.drafts_dir = self.progress_dir / "drafts"

        # Create directories
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

        # Track progress
        self.progress: dict[str, Any] = {
            "agent_name": agent_name,
            "started_at": datetime.now().isoformat(),
            "baseline_score": None,
            "current_best_score": None,
            "current_draft_version": 0,
            "iterations_completed": 0,
            "total_candidates_evaluated": 0,
            "candidates": [],
            "drafts": [],
        }

        logger.info(
            "Progress saver initialized",
            progress_dir=str(self.progress_dir),
            agent_name=agent_name,
        )

    def save_baseline(self, prompt: str, score: float) -> Path:
        """Save the baseline prompt before optimization.

        Saves clean prompt file (ready to use) with metadata only in progress.json.

        Args:
            prompt: The original prompt text.
            score: Baseline evaluation score.

        Returns:
            Path to saved baseline file.
        """
        baseline_path = self.progress_dir / "baseline.md"

        # Save clean prompt - no metadata in the file
        baseline_path.write_text(prompt)

        # All metadata goes to progress.json
        self.progress["baseline_score"] = score
        self.progress["current_best_score"] = score
        self.progress["baseline_file"] = "baseline.md"
        self.progress["baseline_saved_at"] = datetime.now().isoformat()
        self._save_progress()

        logger.info(
            "Baseline saved",
            path=str(baseline_path),
            score=score,
        )

        return baseline_path

    def save_candidate(
        self,
        candidate: PromptCandidate,
        iteration: int,
        candidate_index: int,
    ) -> Path:
        """Save a candidate prompt after evaluation.

        Saves clean prompt file (ready to use) with metadata only in progress.json.

        Args:
            candidate: The evaluated candidate.
            iteration: Current iteration number.
            candidate_index: Index within the iteration.

        Returns:
            Path to saved candidate file.
        """
        filename = f"iter{iteration}_cand{candidate_index}_score{candidate.score:.2f}.md"
        candidate_path = self.candidates_dir / filename

        # Save clean prompt - no metadata in the file
        candidate_path.write_text(candidate.prompt)

        # All metadata goes to progress.json
        self.progress["total_candidates_evaluated"] += 1
        self.progress["candidates"].append({
            "iteration": iteration,
            "candidate_index": candidate_index,
            "score": candidate.score,
            "filename": filename,
            "saved_at": datetime.now().isoformat(),
            "metadata": candidate.metadata,
        })
        self._save_progress()

        logger.debug(
            "Candidate saved",
            path=str(candidate_path),
            iteration=iteration,
            candidate=candidate_index,
            score=candidate.score,
        )

        return candidate_path

    def save_draft(
        self,
        prompt: str,
        score: float,
        iteration: int,
        improvement: float,
    ) -> Path:
        """Save a new best draft when improvement is found.

        Saves clean prompt file (ready to use) with metadata only in progress.json.

        Args:
            prompt: The new best prompt text.
            score: Score of this draft.
            iteration: Iteration where improvement was found.
            improvement: Score improvement over previous best.

        Returns:
            Path to saved draft file.
        """
        self.progress["current_draft_version"] += 1
        version = self.progress["current_draft_version"]

        filename = f"draft_v{version}_score{score:.2f}.md"
        draft_path = self.drafts_dir / filename

        # Save clean prompt - no metadata in the file
        draft_path.write_text(prompt)

        # All metadata goes to progress.json
        self.progress["current_best_score"] = score
        self.progress["drafts"].append({
            "version": version,
            "score": score,
            "improvement": improvement,
            "improvement_percent": improvement * 100,
            "iteration": iteration,
            "filename": filename,
            "saved_at": datetime.now().isoformat(),
        })
        self._save_progress()

        logger.info(
            "New draft saved",
            path=str(draft_path),
            version=version,
            score=score,
            improvement=f"+{improvement:.4f}",
        )

        return draft_path

    def mark_iteration_complete(self, iteration: int, best_score: float) -> None:
        """Mark an iteration as complete.

        Args:
            iteration: The completed iteration number.
            best_score: Best score at end of iteration.
        """
        self.progress["iterations_completed"] = iteration + 1
        self.progress["current_best_score"] = best_score
        self.progress["last_updated"] = datetime.now().isoformat()
        self._save_progress()

        logger.info(
            "Iteration marked complete",
            iteration=iteration,
            best_score=best_score,
        )

    def finalize(self, final_score: float, success: bool) -> None:
        """Finalize the progress tracking.

        Args:
            final_score: Final optimization score.
            success: Whether optimization succeeded.
        """
        self.progress["completed_at"] = datetime.now().isoformat()
        self.progress["final_score"] = final_score
        self.progress["success"] = success
        self.progress["improvement_total"] = (
            final_score - (self.progress["baseline_score"] or 0)
        )
        self._save_progress()

        logger.info(
            "Progress finalized",
            final_score=final_score,
            success=success,
            total_candidates=self.progress["total_candidates_evaluated"],
            total_drafts=len(self.progress["drafts"]),
        )

    def _save_progress(self) -> None:
        """Save the progress summary to JSON."""
        progress_path = self.progress_dir / "progress.json"
        progress_path.write_text(json.dumps(self.progress, indent=2))

    def get_summary(self) -> str:
        """Get a human-readable summary of progress.

        Returns:
            Formatted summary string.
        """
        lines = [
            f"Optimization Progress for {self.agent_name}",
            "=" * 50,
            f"Baseline Score: {self.progress.get('baseline_score', 'N/A')}",
            f"Current Best: {self.progress.get('current_best_score', 'N/A')}",
            f"Drafts Saved: {len(self.progress.get('drafts', []))}",
            f"Candidates Evaluated: {self.progress.get('total_candidates_evaluated', 0)}",
            f"Iterations Completed: {self.progress.get('iterations_completed', 0)}",
            "",
            "Files:",
            f"  Progress: {self.progress_dir / 'progress.json'}",
            f"  Candidates: {self.candidates_dir}",
            f"  Drafts: {self.drafts_dir}",
        ]

        if self.progress.get("drafts"):
            lines.append("")
            lines.append("Draft History:")
            for draft in self.progress["drafts"]:
                lines.append(
                    f"  v{draft['version']}: {draft['score']:.4f} "
                    f"(+{draft['improvement']:.4f}) @ iter {draft['iteration']}"
                )

        return "\n".join(lines)
