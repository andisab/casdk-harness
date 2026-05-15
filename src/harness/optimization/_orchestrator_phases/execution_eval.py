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

Phase F4: per-resource eval runs in parallel under an
``asyncio.Semaphore`` bounded by ``CGF_EXECUTION_EVAL_CONCURRENCY``
(default 2 — eval is more expensive than generate/iterate, so we cap
lower).  The promotion / regression / feedback-loop decision runs AFTER
the gather batch completes — it inspects the full aggregate, not
streaming partials.

This is NOT an agent delegation — :class:`EvalHarness` is invoked
directly.  Method name uses ``run_phase`` rather than ``delegate`` to
make that distinction visible at the call site.
"""

from __future__ import annotations

import asyncio
import json
import os
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

DEFAULT_EXECUTION_EVAL_CONCURRENCY = 4  # F18: bumped from 2; eval is I/O-bound on judge API


def _is_unwinnable(results: EvalResults) -> bool:
    """F21: detect resources where both arms score 0 on every scenario.

    When baseline.pass_rate AND candidate.pass_rate are both 0 across all
    scenarios, feedback iteration cannot help — either the scenarios are
    unwinnable for this resource type, or the rubric is mis-calibrated.
    Mark the resource ``unwinnable`` and skip feedback rounds; the
    operator can edit the resource scenarios / rubric and reset state.
    """
    if not results.scenarios:
        return False
    return all(
        sc.baseline.pass_rate == 0 and sc.candidate.pass_rate == 0
        for sc in results.scenarios
    )


def _resolve_concurrency(env_var: str, default: int) -> int:
    """Read an integer concurrency knob from the environment.

    Eval is more expensive than generate/iterate (two arms per resource,
    multiple scenarios per arm, judge calls), so the default cap is
    lower.  Invalid / non-positive values fall back to ``default``.
    """
    raw = os.environ.get(env_var)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


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
    concurrency = _resolve_concurrency(
        "CGF_EXECUTION_EVAL_CONCURRENCY", DEFAULT_EXECUTION_EVAL_CONCURRENCY
    )

    logger.info(
        "EXECUTION_EVAL: Starting per-resource eval",
        suite_path=str(suite_path),
        resources=len(iterated_resources),
        epsilon=epsilon,
        feedback_iteration=feedback_count + 1,
        max_feedback=max_feedback,
        concurrency=concurrency,
    )
    self._emit_progress("EXECUTION_EVAL", "all", "in_progress")

    # --- per-resource evaluation ---
    # Each coroutine appends a tuple to its own slot; gather collects all.
    # The promotion/regression decision happens AFTER the gather so the
    # ordering is deterministic regardless of completion order.
    harness = EvalHarness()  # in-process; Phase C adds ephemeral_container
    semaphore = asyncio.Semaphore(concurrency)

    async def _eval_one(
        resource: ResourceStatus,
    ) -> tuple[ResourceStatus, EvalResults] | None:
        async with semaphore:
            return await _eval_single_resource(
                self,
                resource=resource,
                workspace=workspace,
                suite_path=suite_path,
                harness=harness,
                epsilon=epsilon,
            )

    raw_outcomes = await asyncio.gather(
        *[_eval_one(r) for r in iterated_resources],
        return_exceptions=True,
    )

    per_resource_results: list[tuple[ResourceStatus, EvalResults]] = []
    regressions: list[tuple[ResourceStatus, EvalResults]] = []
    promotions: list[ResourceStatus] = []
    # F21: unwinnable resources (both arms scored 0 across all scenarios)
    # are tracked separately — they're neither promotions (no signal of
    # improvement) nor regressions (feedback iteration can't help).  The
    # gate treats them as non-blocking so a partial-unwinnable run can
    # still advance to VALIDATE on the strength of real promotions.
    unwinnable: list[ResourceStatus] = []
    # F8: track harness errors separately so the gate can't fail-OPEN
    # when every resource errored.  Previously, errors returned None or
    # were caught here without joining `regressions`, so `not regressions`
    # was True and the orchestrator logged "All resources promoted" with
    # promoted=0 and advanced silently.  Errors now block promotion.
    harness_errors: list[tuple[ResourceStatus, str]] = []

    for resource, outcome in zip(iterated_resources, raw_outcomes, strict=True):
        if isinstance(outcome, Exception):
            logger.error(
                "EXECUTION_EVAL: Unhandled exception in resource coroutine",
                path=resource.path,
                error=str(outcome)[:300],
            )
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    error=f"Unhandled exception: {outcome}",
                )
            harness_errors.append((resource, f"unhandled: {outcome}"))
            continue
        if outcome is None:
            # _eval_single_resource returned None.  Two cases:
            #   (a) candidate file missing → skipped (very rare; state
            #       was not modified, resource stays as-is)
            #   (b) harness raised → status already set to
            #       needs_refinement inside the helper
            # We treat both as harness_errors for gate purposes so the
            # missing-result can never be misread as "all promoted."
            res_state = self._state.resources.get(resource.path)
            err_reason = (
                res_state.error
                if res_state and res_state.error
                else "no evaluation result"
            )
            logger.warning(
                "EXECUTION_EVAL: No result returned; counting as error",
                path=resource.path,
                reason=err_reason[:200],
            )
            harness_errors.append((resource, err_reason))
            continue
        res, results = outcome
        per_resource_results.append((res, results))
        # F21: bucket unwinnable separately.  Reading the post-helper state
        # is the authoritative source of truth — the helper already set
        # status="unwinnable" if applicable.
        post_state = self._state.resources.get(resource.path)
        if post_state is not None and post_state.status == "unwinnable":
            unwinnable.append(res)
        elif _should_promote(results, epsilon):
            promotions.append(res)
        else:
            regressions.append((res, results))

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
    # F8: the gate must NEVER advance to VALIDATE with zero successful
    # promotions when something went wrong.  The forward branch now
    # requires both: (1) zero regressions AND (2) zero harness errors
    # AND (3) at least one resource ended in a non-blocking state
    # (promotion or F21-unwinnable; both mean "no actionable feedback
    # left for this resource").
    if not regressions and not harness_errors and (promotions or unwinnable):
        logger.info(
            "EXECUTION_EVAL: No regressions; advancing to VALIDATE",
            promoted=len(promotions),
            unwinnable=len(unwinnable),
        )
        self._emit_progress("EXECUTION_EVAL", "all", "complete")
        self._advance_phase(OptimizationPhase.VALIDATE)
        return

    if not promotions and (regressions or harness_errors):
        logger.error(
            "EXECUTION_EVAL: No resources promoted",
            regressions=len(regressions),
            harness_errors=len(harness_errors),
            unwinnable=len(unwinnable),
            promotions=0,
        )

    # F8: hard-abort when EVERY resource errored.  This usually means
    # eval-suite.yaml itself is broken (schema-invalid, missing fields)
    # or the harness has a config issue — looping back to ITERATE would
    # produce a new v{N+1} but hit the exact same suite-level error.
    # Better to fail loudly than burn another 30 minutes of LLM time.
    if (
        len(harness_errors) == len(iterated_resources)
        and not regressions
        and not promotions
    ):
        # Pick a representative error to surface.
        sample_error = (
            harness_errors[0][1] if harness_errors else "unknown"
        )
        logger.error(
            "EXECUTION_EVAL: ALL resources errored — aborting run",
            harness_errors=len(harness_errors),
            sample_error=sample_error[:300],
            hint=(
                "Inspect eval/eval-suite.yaml for schema violations. "
                "Looping back would not help — every retry will hit "
                "the same suite-level error."
            ),
        )
        self._emit_progress(
            "EXECUTION_EVAL", "all",
            f"aborted: all {len(harness_errors)} resources errored",
        )
        raise RuntimeError(
            f"EXECUTION_EVAL failed: all {len(harness_errors)} "
            f"resources errored (sample: {sample_error[:200]})"
        )

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


async def _eval_single_resource(
    self: MultiResourceOrchestrator,
    *,
    resource: ResourceStatus,
    workspace: Path,
    suite_path: Path,
    harness: EvalHarness,
    epsilon: float,
) -> tuple[ResourceStatus, EvalResults] | None:
    """Run EvalHarness for one resource and apply the promotion decision.

    Returns ``(resource, results)`` so the caller can build aggregate
    output, or ``None`` when the resource was skipped (candidate file
    missing).  State updates (``status``, promotion finalization,
    refinement count) happen inside ``self._state_lock``.
    """
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
        return None

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
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    error=f"Eval harness error: {exc}",
                )
            return None

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

        # F21: detect resources where feedback iteration cannot help.
        # Both arms scoring 0 across every scenario means either the
        # scenarios are unwinnable for this resource type, or the rubric
        # is mis-calibrated.  Either way, looping back to ITERATE will
        # produce another generation that scores the same 0/0 — burning
        # ~70k more tokens for guaranteed null result.  Mark and skip.
        if _is_unwinnable(results):
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="unwinnable",
                    last_evaluated_version=resource.version,
                    error=(
                        "all scenarios scored 0 on both arms; needs "
                        "human review of scenarios or rubric"
                    ),
                )
            resource_span.set_attribute("harness.eval.outcome", "unwinnable")
            self._emit_progress(
                "EXECUTION_EVAL", resource.path, "unwinnable",
                results.candidate_pass_rate,
            )
            logger.warning(
                "EXECUTION_EVAL: marking unwinnable",
                path=resource.path,
                scenarios=len(results.scenarios),
                hint=(
                    "baseline+candidate both scored 0 on every scenario; "
                    "scenarios or rubric need redesign"
                ),
            )
        elif _should_promote(results, epsilon):
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="optimized",
                    last_evaluated_version=resource.version,
                )
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
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    last_evaluated_version=resource.version,
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

    return (resource, results)


def _resources_to_evaluate(
    self: MultiResourceOrchestrator,
) -> list[ResourceStatus]:
    """Pick the resources whose latest version should be evaluated.

    A resource is in scope if:

    - It has at least one optimization iteration (``version >= 1``)
    - Its ``version`` is greater than ``last_evaluated_version`` (F17:
      avoid re-evaluating an identical (baseline, candidate) pair across
      feedback rounds — that wasted ~12 min + ~300k tokens per cycle in
      run #5i)
    - Its status is not ``failed`` (generation aborted) or ``unwinnable``
      (F21: both arms scored 0 across all scenarios; feedback can't help)

    Resources skipped for the version-unchanged reason are logged at
    ``info`` level so operators can see what was elided.
    """
    if not self._state:
        return []

    eligible: list[ResourceStatus] = []
    for r in self._state.resources.values():
        if r.version < 1:
            continue
        if r.status in {"failed", "unwinnable"}:
            continue
        if r.version <= r.last_evaluated_version:
            logger.info(
                "EXECUTION_EVAL: skipped (no version change since last eval)",
                path=r.path,
                version=r.version,
                last_evaluated_version=r.last_evaluated_version,
            )
            continue
        eligible.append(r)
    return eligible


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
