"""EXECUTION_EVAL phase implementation (CGF Stage 3 Phase A.5).

Runs :class:`EvalHarness` once per iterated resource (baseline = original
v0, candidate = current v{N}).  Promotes the candidate when the gate
condition holds; otherwise marks the resource ``needs_refinement`` and
loops back to ITERATE with feedback in ``state.feedback_history`` (max
``max_feedback_iterations`` rounds before escalating to VALIDATE).

Phase A gate (simple threshold):
    candidate.pass_rate ≥ baseline.pass_rate + ε

where ε is :data:`harness.optimization._orchestrator_helpers.DEFAULT_EVAL_PROMOTION_EPSILON`
(default 0.0), overridable per-config and via ``CGF_EVAL_PROMOTION_EPSILON``
env var.  Phase B replaces with bootstrap CI on win rate.

This is NOT an agent delegation — :class:`EvalHarness` is invoked
directly.  Method name uses ``run_phase`` rather than ``delegate`` to
make that distinction visible at the call site.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from harness.monitoring import (
    harness_eval_arm_score,
    harness_eval_phase_duration_seconds,
    harness_eval_scenarios_total,
    harness_eval_tokens_to_goal,
)
from harness.optimization._orchestrator_helpers import (
    DEFAULT_EVAL_PROMOTION_EPSILON,
    DEFAULT_MAX_FEEDBACK_ITERATIONS,
    eval_phase_span,
    new_eval_task_id,
    versioned_path,
)
from harness.optimization.eval_harness import EvalHarness, EvalResults
from harness.progress import OptimizationPhase, ResourceStatus

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def run_phase(self: MultiResourceOrchestrator) -> None:
    """Run EvalHarness for each iterated resource and decide promotions.

    Three exit paths:

    1. **Forward** to VALIDATE when every iterated resource promotes (or
       when no eval suite exists / no resources to evaluate).
    2. **Loop back** to ITERATE when at least one resource regressed AND
       ``state.feedback_history`` length < ``max_feedback_iterations``.
       Saves a feedback entry that the optimizer reads on its next pass.
    3. **Escalate forward** to VALIDATE when regressions remain but max
       feedback iterations have been spent — completion proceeds with
       ``needs_refinement`` resources flagged for human attention.
    """
    if not self._state or not self._spec:
        return

    phase_start = time.time()
    task_id = new_eval_task_id()
    try:
        async with eval_phase_span(
            "eval.execution",
            task_id=task_id,
            phase="EXECUTION_EVAL",
        ) as span:
            # Stash task_id on the orchestrator so per-resource sub-spans
            # can correlate without threading it through every helper.
            self._eval_task_id = task_id  # type: ignore[attr-defined]
            await _run_phase_body(self)
            # Final outcome attribute is set after the body decides
            # forward / loop / escalate; record here for the wrap-up.
            # contextlib.suppress: span ops must never break the flow.
            import contextlib

            with contextlib.suppress(Exception):
                span.set_attribute(
                    "harness.eval.feedback_history_length",
                    len(self._state.feedback_history) if self._state else 0,
                )
    finally:
        # Phase A.6: record duration for every exit path.
        harness_eval_phase_duration_seconds.labels(
            phase="EXECUTION_EVAL"
        ).observe(time.time() - phase_start)


async def _run_phase_body(self: MultiResourceOrchestrator) -> None:
    """The actual phase logic; wrapped by run_phase for timing."""
    workspace = self.config.workspace_dir

    # --- precondition checks ---
    suite_relpath = self._state.eval_suite_path
    if not suite_relpath:
        logger.warning(
            "EXECUTION_EVAL: No eval-suite.yaml in state; skipping",
        )
        return  # caller advances phase forward

    suite_path = workspace / suite_relpath
    if not suite_path.exists():
        logger.warning(
            "EXECUTION_EVAL: Eval suite missing on disk; skipping",
            suite_path=str(suite_path),
        )
        return

    iterated_resources = _resources_to_evaluate(self)
    if not iterated_resources:
        logger.info(
            "EXECUTION_EVAL: No iterated resources to evaluate; skipping",
        )
        return

    epsilon = _resolve_epsilon(self)
    max_feedback = _resolve_max_feedback(self)
    feedback_count = len(self._state.feedback_history)

    logger.info(
        "EXECUTION_EVAL: Starting per-resource eval",
        suite_path=str(suite_path),
        resources=len(iterated_resources),
        epsilon=epsilon,
        feedback_iteration=feedback_count + 1,
        max_feedback=max_feedback,
    )
    self._emit_progress("EXECUTION_EVAL", "all", "in_progress")

    # --- per-resource evaluation ---
    per_resource_results: list[tuple[ResourceStatus, EvalResults]] = []
    regressions: list[tuple[ResourceStatus, EvalResults]] = []
    promotions: list[ResourceStatus] = []

    harness = EvalHarness()  # in-process; Phase C adds ephemeral_container

    for resource in iterated_resources:
        baseline_path = _resolve_baseline_path(workspace, resource)
        candidate_path = workspace / versioned_path(
            resource.path, resource.version
        )

        if not candidate_path.exists():
            logger.warning(
                "EXECUTION_EVAL: Candidate file missing; skipping",
                path=resource.path,
                expected=str(candidate_path),
            )
            continue

        results_dir = workspace / "eval" / "results" / f"{resource.path}-v{resource.version}"

        # Per-resource sub-span (Phase A.7).  Captures the eval task_id
        # from the parent span via self._eval_task_id, plus per-resource
        # attributes that show up in OTel trace explorers.
        per_resource_task_id = getattr(self, "_eval_task_id", "unknown")
        async with eval_phase_span(
            "eval.execution.resource",
            task_id=per_resource_task_id,
            phase="EXECUTION_EVAL",
            extra={
                "harness.eval.resource_path": resource.path,
                "harness.eval.resource_type": resource.resource_type,
                "harness.eval.resource_version": resource.version,
            },
        ) as resource_span:
            try:
                results = await harness.run(
                    eval_suite_path=suite_path,
                    baseline_resource=baseline_path,
                    candidate_resource=candidate_path,
                    results_dir=results_dir,
                )
            except Exception as exc:  # noqa: BLE001 — surface but don't crash phase
                logger.error(
                    "EXECUTION_EVAL: Harness raised; treating as regression",
                    path=resource.path,
                    error=str(exc),
                )
                resource_span.set_attribute("harness.eval.outcome", "error")
                resource_span.set_attribute("harness.eval.error", str(exc)[:200])
                self._emit_progress(
                    "EXECUTION_EVAL", resource.path, f"harness error: {exc}",
                )
                # Mark for refinement so the loop has a chance to recover.
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    error=f"Eval harness error: {exc}",
                )
                continue

            per_resource_results.append((resource, results))

            # Per-scenario / per-arm telemetry (Phase A.6).
            _emit_scenario_metrics(results)

            # Span outcome attributes set after we know the verdict.
            resource_span.set_attribute(
                "harness.eval.candidate_pass_rate", results.candidate_pass_rate
            )
            resource_span.set_attribute(
                "harness.eval.baseline_pass_rate", results.baseline_pass_rate
            )
            resource_span.set_attribute("harness.eval.win_rate", results.win_rate)

            if _should_promote(results, epsilon):
                promotions.append(resource)
                self._state.update_resource(resource.path, status="optimized")
                self._finalize_single_resource(resource.path)
                # Tokens-to-goal: at promotion, observe the cumulative tokens
                # for this resource.  Phase A approximation: per-run total only;
                # cumulative across feedback iterations is a Phase B refinement.
                harness_eval_tokens_to_goal.labels(
                    resource_type=resource.resource_type
                ).observe(results.total_tokens)
                resource_span.set_attribute("harness.eval.outcome", "promoted")
                self._emit_progress(
                    "EXECUTION_EVAL", resource.path, "promoted",
                    results.candidate_pass_rate,
                )
                logger.info(
                    "EXECUTION_EVAL: Promoted",
                    path=resource.path,
                    candidate_pass_rate=f"{results.candidate_pass_rate:.2f}",
                    baseline_pass_rate=f"{results.baseline_pass_rate:.2f}",
                    win_rate=f"{results.win_rate:.2f}",
                )
            else:
                regressions.append((resource, results))
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    refinement_count=resource.refinement_count + 1,
                )
                resource_span.set_attribute("harness.eval.outcome", "regressed")
                self._emit_progress(
                    "EXECUTION_EVAL", resource.path, "regression",
                    results.candidate_pass_rate,
                )
                logger.warning(
                    "EXECUTION_EVAL: Regression",
                    path=resource.path,
                    candidate_pass_rate=f"{results.candidate_pass_rate:.2f}",
                    baseline_pass_rate=f"{results.baseline_pass_rate:.2f}",
                    win_rate=f"{results.win_rate:.2f}",
                )

    # --- aggregate write ---
    aggregate_path = _write_aggregate_results(
        workspace=workspace,
        per_resource_results=per_resource_results,
        feedback_iteration=feedback_count + 1,
    )
    if aggregate_path is not None:
        # Path stored relative to workspace for portability.
        self._state.eval_results_path = str(
            aggregate_path.relative_to(workspace)
        )

    # --- decision: forward, loop, or escalate ---
    if not regressions:
        logger.info(
            "EXECUTION_EVAL: All resources promoted; advancing to VALIDATE",
            promoted=len(promotions),
        )
        self._emit_progress("EXECUTION_EVAL", "all", "complete")
        self._advance_phase(OptimizationPhase.VALIDATE)
        return

    if feedback_count >= max_feedback:
        logger.warning(
            "EXECUTION_EVAL: Max feedback iterations reached; escalating",
            regressions=len(regressions),
            feedback_count=feedback_count,
            max_feedback=max_feedback,
        )
        self._emit_progress(
            "EXECUTION_EVAL", "all",
            f"escalating with {len(regressions)} regression(s)",
        )
        self._advance_phase(OptimizationPhase.VALIDATE)
        return

    # Loop back to ITERATE with feedback in state.
    feedback_entry = _build_feedback_entry(
        regressions, feedback_iteration=feedback_count + 1
    )
    self._state.feedback_history.append(feedback_entry)
    self._state.current_phase = OptimizationPhase.ITERATE
    self._save_state()

    logger.info(
        "EXECUTION_EVAL: Looping back to ITERATE with feedback",
        feedback_iteration=feedback_count + 1,
        regressions=len(regressions),
    )
    self._emit_progress(
        "EXECUTION_EVAL", "all",
        f"refining {len(regressions)} resource(s) (round {feedback_count + 1})",
    )


# ---------------------------------------------------------------------------
# Helpers (module-level, not mounted on the orchestrator class)
# ---------------------------------------------------------------------------


def _resources_to_evaluate(
    self: MultiResourceOrchestrator,
) -> list[ResourceStatus]:
    """Pick the resources whose latest version should be evaluated.

    A resource is in scope if it has at least one optimization iteration
    (``version >= 1``) and has a candidate file on disk.  Resources that
    failed generation outright (``status == "failed"`` and ``version == 0``)
    are skipped.
    """
    if not self._state:
        return []

    return [
        r
        for r in self._state.resources.values()
        if r.version >= 1 and r.status not in {"failed"}
    ]


def _resolve_baseline_path(workspace: Path, resource: ResourceStatus) -> Path:
    """Pick the file to use as the baseline arm.

    Preference order:
    1. ``{resource}-v0.md`` (backed-up original from GENERATE phase)
    2. ``{resource}.md`` (in-tree original / canonical path)

    The orchestrator's ``_backup_original_resource`` already copies the
    original to ``-v0`` before generation, so option 1 is the default for
    workspaces where an original existed.  Option 2 covers fresh plugins
    where no prior version was on disk.
    """
    v0_path = workspace / versioned_path(resource.path, 0)
    if v0_path.exists():
        return v0_path
    return workspace / resource.path


def _resolve_epsilon(self: MultiResourceOrchestrator) -> float:
    """Promotion epsilon: config wins over env, env wins over default."""
    if self.config.eval_promotion_epsilon is not None:
        return float(self.config.eval_promotion_epsilon)
    import os

    raw = os.environ.get("CGF_EVAL_PROMOTION_EPSILON")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_EVAL_PROMOTION_EPSILON


def _resolve_max_feedback(self: MultiResourceOrchestrator) -> int:
    """Max feedback-driven ITERATE loops: config wins over default."""
    if self.config.max_feedback_iterations is not None:
        return int(self.config.max_feedback_iterations)
    return DEFAULT_MAX_FEEDBACK_ITERATIONS


def _should_promote(results: EvalResults, epsilon: float) -> bool:
    """Phase A simple-threshold gate.

    Promote when candidate.pass_rate strictly exceeds baseline by ε.
    Equality is treated as failure to promote — we want a clear signal
    of improvement, not a coin-flip tie.
    """
    return results.candidate_pass_rate >= results.baseline_pass_rate + epsilon


def _build_feedback_entry(
    regressions: list[tuple[ResourceStatus, EvalResults]],
    feedback_iteration: int,
) -> dict[str, Any]:
    """Assemble a feedback record for ``state.feedback_history``.

    The entry is later read by the ITERATE phase's prompt builder to
    show the optimizer which scenarios it failed and what the baseline
    handled correctly.  Held-out scenarios are explicitly stripped so
    the optimizer never sees them.
    """
    resources_data: list[dict[str, Any]] = []
    for resource, results in regressions:
        failing = []
        for sr in results.scenarios:
            if sr.held_out:
                continue
            if sr.outcome != "candidate_win":
                # Include only scenario-level details — the optimizer
                # doesn't need full transcripts in its prompt.
                failing.append(
                    {
                        "scenario_id": sr.scenario_id,
                        "level": sr.level,
                        "outcome": sr.outcome,
                        "baseline_pass_rate": sr.baseline.pass_rate,
                        "candidate_pass_rate": sr.candidate.pass_rate,
                        "tags": list(sr.tags),
                    }
                )
        resources_data.append(
            {
                "path": resource.path,
                "candidate_pass_rate": results.candidate_pass_rate,
                "baseline_pass_rate": results.baseline_pass_rate,
                "win_rate": results.win_rate,
                "failing_scenarios": failing,
            }
        )

    return {
        "feedback_iteration": feedback_iteration,
        "timestamp": datetime.now(UTC).isoformat(),
        "regressions": resources_data,
    }


def _write_aggregate_results(
    *,
    workspace: Path,
    per_resource_results: list[tuple[ResourceStatus, EvalResults]],
    feedback_iteration: int,
) -> Path | None:
    """Write a top-level summary of this EXECUTION_EVAL run.

    Returns the path written, or None if nothing to write.  Per-resource
    detailed results are already on disk under
    ``eval/results/{resource_path}-v{N}/eval-results.json`` (written by
    each :class:`EvalHarness` invocation).  This summary file is the
    one-glance view across all resources.
    """
    if not per_resource_results:
        return None

    aggregate = {
        "timestamp": datetime.now(UTC).isoformat(),
        "feedback_iteration": feedback_iteration,
        "resources": [
            {
                "path": resource.path,
                "version": resource.version,
                "win_rate": results.win_rate,
                "baseline_pass_rate": results.baseline_pass_rate,
                "candidate_pass_rate": results.candidate_pass_rate,
                "no_decision_rate": results.no_decision_rate,
                "scenarios": len(results.scenarios),
                "promoted": results.candidate_pass_rate
                >= results.baseline_pass_rate,
            }
            for resource, results in per_resource_results
        ],
    }

    eval_dir = workspace / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    out_path = eval_dir / f"execution-eval-round-{feedback_iteration}.json"
    out_path.write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("EXECUTION_EVAL: Wrote aggregate", path=str(out_path))
    return out_path


def _emit_scenario_metrics(results: EvalResults) -> None:
    """Emit per-scenario / per-arm Prometheus telemetry (Phase A.6).

    Walks the scenarios in ``results`` and records:

    - ``harness_eval_scenarios_total{level, status, arm}`` for each
      (scenario, arm) pair.  Status is one of ``pass | fail | no_decision``;
      derived from the arm's ``pass_caret_k`` (all decisive trials passed)
      and ``decisive`` count (any decisive trial at all).
    - ``harness_eval_arm_score{arm, level}`` histogram observation of
      the arm's pass-rate.

    Held-out scenarios are NOT excluded — operators monitoring the gate
    want visibility into held-out outcomes too.  The optimizer-feedback
    layer is what filters held_out, not telemetry.
    """
    for sr in results.scenarios:
        for arm_name, arm in (
            ("baseline", sr.baseline),
            ("candidate", sr.candidate),
        ):
            if arm.decisive == 0:
                status = "no_decision"
            elif arm.pass_caret_k >= 1.0:
                status = "pass"
            else:
                status = "fail"
            harness_eval_scenarios_total.labels(
                level=sr.level, status=status, arm=arm_name
            ).inc()
            harness_eval_arm_score.labels(
                arm=arm_name, level=sr.level
            ).observe(arm.pass_rate)
