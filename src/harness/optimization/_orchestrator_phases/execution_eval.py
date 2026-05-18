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
from typing import TYPE_CHECKING, Any, Literal

import structlog

from harness.monitoring import (
    harness_eval_arm_score,
    harness_eval_cost_gate_total,
    harness_eval_cost_per_success_usd,
    harness_eval_phase_duration_seconds,
    harness_eval_scenarios_total,
    harness_eval_tokens_to_goal,
)
from harness.optimization._orchestrator_helpers import (
    DEFAULT_EVAL_PROMOTION_EPSILON,
    DEFAULT_MAX_FEEDBACK_ITERATIONS,
    DEFAULT_MIN_GAIN_PER_ROUND,
    eval_phase_span,
    eval_suite_sha256,
    new_eval_task_id,
    versioned_path,
)
from harness.optimization._orchestrator_phases._baseline_floor import (
    build_floor_resource,
)
from harness.optimization.eval_harness import EvalHarness, EvalResults
from harness.optimization.eval_harness.runner import _resource_target_key
from harness.optimization.gating import (
    GateInputs,
    _resolve_cost_quality_bonus,
    effective_cost_tolerance,
    is_first_promotion,
)
from harness.optimization.gating import Verdict as GateVerdict
from harness.optimization.gating import decide as gate_decide
from harness.progress import OptimizationPhase, ResourceStatus

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)

DEFAULT_EXECUTION_EVAL_CONCURRENCY = 4  # F18: bumped from 2; eval is I/O-bound on judge API

# Per-resource verdict surfaced into the aggregate JSON.  Superset of
# ``gating.Verdict`` (adds ``"unwinnable"`` for the F21 short-circuit
# branch where the gate is never consulted).  Operators reading
# ``execution-eval-round-N.json`` see the same vocabulary the gate uses.
AggregateVerdict = Literal[
    "promote", "refine", "reject_floor", "reject_cost", "unwinnable"
]


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

    # Phase A refinement 4.4.a: refuse to run if the live suite hash
    # differs from what EVAL_DESIGN recorded.  Guards against mid-loop
    # scenario rewrites (intentional or accidental) leaking optimizer
    # reasoning into the gate.  Hard abort — looping back wouldn't fix
    # the violation, and continuing would invalidate the comparison.
    expected_hash = self._state.eval_suite_hash
    if expected_hash:
        live_hash = eval_suite_sha256(suite_path)
        if live_hash != expected_hash:
            logger.error(
                "EXECUTION_EVAL: eval-suite.yaml hash changed mid-loop — "
                "aborting",
                expected=expected_hash[:16] + "...",
                live=live_hash[:16] + "...",
                hint=(
                    "The eval suite was modified after EVAL_DESIGN. "
                    "Refusing to run because the gate would no longer "
                    "be comparing against the suite the candidate was "
                    "iterated against.  Reset sessions/ and re-run if "
                    "the modification was intentional."
                ),
            )
            self._emit_progress(
                "EXECUTION_EVAL", "all",
                "aborted: eval-suite hash mismatch",
            )
            raise RuntimeError(
                "EXECUTION_EVAL aborted: eval-suite.yaml hash "
                f"{live_hash[:16]} differs from EVAL_DESIGN hash "
                f"{expected_hash[:16]}"
            )

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
    ) -> tuple[ResourceStatus, EvalResults, AggregateVerdict] | None:
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

    # Per-resource results carry the gate verdict (or "unwinnable") so
    # _write_aggregate_results can record the actual decision instead
    # of re-deriving an approximation from pass-rate deltas.
    per_resource_results: list[
        tuple[ResourceStatus, EvalResults, AggregateVerdict]
    ] = []
    # I15: include verdict in regression tuples so ``_build_feedback_entry``
    # can surface the failure-mode (reject_floor / refine / reject_cost) to
    # the optimizer's per-call prompt.  ``unwinnable`` is filtered out
    # earlier via the post-helper status check, so the type here uses
    # ``gating.Verdict`` (no "unwinnable") rather than ``AggregateVerdict``.
    regressions: list[tuple[ResourceStatus, EvalResults, GateVerdict]] = []
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
        res, results, verdict = outcome
        per_resource_results.append((res, results, verdict))
        # F21 + Phase A refinement 4.2: bucket from post-helper state.
        # ``_eval_single_resource`` already wrote the authoritative
        # status (optimized / unwinnable / needs_refinement) under the
        # state lock; reading it here keeps the bucketing in lockstep
        # with the gate verdict (incl. reject_floor → needs_refinement).
        post_state = self._state.resources.get(resource.path)
        post_status = post_state.status if post_state is not None else None
        if post_status == "unwinnable":
            unwinnable.append(res)
        elif post_status == "optimized":
            promotions.append(res)
        else:
            # needs_refinement covers both Phase A regressions and the
            # new reject_floor verdict.  Treated identically by the
            # downstream feedback-loop logic, but the verdict carries
            # through so the optimizer's per-call prompt can branch
            # by failure-mode (I15).
            #
            # ``verdict`` is one of ``promote|refine|reject_floor|reject_cost``
            # here — ``unwinnable`` already went into ``unwinnable`` above
            # via the ``post_status == "unwinnable"`` branch.  A
            # defensive narrow keeps the type stable.
            assert verdict != "unwinnable"
            regressions.append((res, results, verdict))

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

    # Phase A refinement 4.4.c: held-out scenario usage bookkeeping.
    # Best-effort sidecar write — separate file so it doesn't trip the
    # 4.4.a suite-hash check.  Phase D will rotate held-out on contact
    # using this data.
    _record_held_out_usage(workspace, per_resource_results)

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

    # Phase A refinement 4.4.b: stagnation early-stop.  Compute this
    # round's mean candidate pass-rate across all per-resource results
    # and compare against the previous round (if any).  When the gain
    # is below the threshold, escalate to VALIDATE rather than burn
    # another round on lateral drift.
    round_mean_cpr = _round_mean_candidate_pass_rate(per_resource_results)
    min_gain = _resolve_min_gain()
    if feedback_count > 0 and self._state.feedback_history:
        prev_round_mean = self._state.feedback_history[-1].get(
            "round_mean_candidate_pass_rate"
        )
        if prev_round_mean is not None:
            delta = round_mean_cpr - prev_round_mean
            if delta < min_gain:
                logger.warning(
                    "EXECUTION_EVAL: Stagnation early-stop — escalating "
                    "to VALIDATE without further ITERATE",
                    round_mean_candidate_pass_rate=f"{round_mean_cpr:.3f}",
                    previous_round_mean=f"{prev_round_mean:.3f}",
                    delta=f"{delta:.3f}",
                    min_gain=f"{min_gain:.3f}",
                    hint=(
                        "iteration is no longer improving meaningfully. "
                        "Raise CGF_MIN_GAIN_PER_ROUND if you want more "
                        "rounds, or lower it to let smaller gains through."
                    ),
                )
                self._emit_progress(
                    "EXECUTION_EVAL", "all",
                    f"stagnation early-stop (Δ={delta:.3f}<{min_gain})",
                )
                self._advance_phase(OptimizationPhase.VALIDATE)
                return

    # Loop back to ITERATE with feedback in state.
    feedback_entry = _build_feedback_entry(
        regressions,
        feedback_iteration=feedback_count + 1,
        round_mean_candidate_pass_rate=round_mean_cpr,
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
) -> tuple[ResourceStatus, EvalResults, AggregateVerdict] | None:
    """Run EvalHarness for one resource and apply the promotion decision.

    Returns ``(resource, results, verdict)`` so the caller can build
    aggregate output that records the *actual* gate decision, or
    ``None`` when the resource was skipped (candidate file missing) or
    the harness errored.  State updates (``status``, promotion
    finalization, refinement count) happen inside ``self._state_lock``.

    ``verdict`` is one of ``{"promote", "refine", "reject_floor",
    "reject_cost", "unwinnable"}`` — superset of ``gating.Verdict`` to
    cover the F21 short-circuit branch where the gate is never
    consulted.
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

    # Phase A refinement 4.2: build floor arm exactly once per resource,
    # only on the first-time-promotion path.  Once a resource has any
    # promoted version (``last_promoted_version > 0``), the floor is
    # never re-evaluated within this branch — the model is the
    # experimental control and does not change mid-branch.
    floor_path: Path | None = None
    if is_first_promotion(resource.last_promoted_version):
        floor_dir = workspace / "eval" / "floor" / Path(resource.path).parent
        floor_path = build_floor_resource(
            candidate_path=candidate_path,
            output_dir=floor_dir,
        )

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
                baseline_floor=floor_path,
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

        # No applicable scenarios → fail closed.  This happens when the
        # eval-architect didn't author scenarios for this resource's
        # ``target_resource`` key, or when the architect's
        # ``target_resource`` field doesn't match the resource path
        # produced by GENERATE.  Pre-fix the gate would silently
        # promote on (0 ≥ 0) — a false success with no eval signal.
        # Returning None here joins the F8 ``harness_errors`` path so
        # the run hard-aborts when ALL resources hit this condition
        # (typically a broken eval-suite.yaml).
        if not results.scenarios:
            target_key = _resource_target_key(candidate_path)
            err_msg = (
                "no scenarios applicable to this resource"
                f" (target_key={target_key})"
            )
            logger.error(
                "EXECUTION_EVAL: No scenarios applicable to resource — "
                "refusing to gate",
                path=resource.path,
                target_key=target_key,
                suite_path=str(suite_path),
                hint=(
                    "eval-architect didn't author scenarios for this "
                    "target_resource, or the architect's target_resource "
                    "key doesn't match the GENERATE-produced path. "
                    "Inspect eval/eval-suite.yaml for matching "
                    "target_resource entries."
                ),
            )
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="needs_refinement",
                    error=err_msg,
                )
            resource_span.set_attribute(
                "harness.eval.outcome", "no_scenarios"
            )
            self._emit_progress(
                "EXECUTION_EVAL", resource.path, err_msg,
            )
            return None  # joins harness_errors via the outer collector

        # F21: detect resources where feedback iteration cannot help.
        # Both arms scoring 0 across every scenario means either the
        # scenarios are unwinnable for this resource type, or the rubric
        # is mis-calibrated.  Either way, looping back to ITERATE will
        # produce another generation that scores the same 0/0 — burning
        # ~70k more tokens for guaranteed null result.  Mark and skip.
        verdict_for_aggregate: AggregateVerdict
        if _is_unwinnable(results):
            verdict_for_aggregate = "unwinnable"
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
        else:
            # Phase A refinement 4.2 + 4.3: dual-baseline quality gate
            # plus cost-per-success gate.  Verdict is one of
            # {"promote", "refine", "reject_floor", "reject_cost"}.
            tau = _resolve_cost_tolerance()
            verdict = gate_decide(
                GateInputs(
                    candidate_pass_rate=results.candidate_pass_rate,
                    incumbent_pass_rate=results.baseline_pass_rate,
                    floor_pass_rate=results.floor_pass_rate,
                    is_first_promotion=is_first_promotion(
                        resource.last_promoted_version
                    ),
                    epsilon=epsilon,
                    candidate_cost_per_success=results.candidate_cost_per_success,
                    incumbent_cost_per_success=results.baseline_cost_per_success,
                    tau=tau,
                )
            )
            verdict_for_aggregate = verdict
            resource_span.set_attribute(
                "harness.eval.floor_pass_rate",
                results.floor_pass_rate if results.floor_pass_rate is not None else -1.0,
            )
            # Phase A refinement 4.3: cost telemetry.
            #
            # Histogram observations are emitted on every verdict where
            # cost data is present — they're an arm-cost observability
            # signal independent of the gate decision.
            if results.candidate_cost_per_success is not None:
                harness_eval_cost_per_success_usd.labels(
                    resource_type=resource.resource_type, arm="candidate"
                ).observe(results.candidate_cost_per_success)
            if results.baseline_cost_per_success is not None:
                harness_eval_cost_per_success_usd.labels(
                    resource_type=resource.resource_type, arm="baseline"
                ).observe(results.baseline_cost_per_success)
            # The cost-gate counter only fires when the cost stage was
            # actually consulted.  ``gate_decide`` short-circuits inside
            # the quality stages: ``reject_floor`` and ``refine`` exit
            # before the cost stage runs.  Counting those as "promote"
            # or "auto_pass" would mislabel quality-rejected outcomes as
            # cost-gate successes.
            if verdict in ("promote", "reject_cost"):
                if verdict == "reject_cost":
                    harness_eval_cost_gate_total.labels(
                        outcome="reject_cost"
                    ).inc()
                elif (
                    results.candidate_cost_per_success is None
                    or results.baseline_cost_per_success is None
                ):
                    # Cost stage auto-passed because one side had no signal.
                    harness_eval_cost_gate_total.labels(
                        outcome="auto_pass"
                    ).inc()
                else:
                    harness_eval_cost_gate_total.labels(
                        outcome="promote"
                    ).inc()

            if verdict == "promote":
                async with self._state_lock:
                    self._state.update_resource(
                        resource.path,
                        status="optimized",
                        last_evaluated_version=resource.version,
                        last_promoted_version=resource.version,
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
                    floor_pass_rate=(
                        f"{results.floor_pass_rate:.2f}"
                        if results.floor_pass_rate is not None
                        else "n/a"
                    ),
                    win_rate=f"{results.win_rate:.2f}",
                )
            else:
                # "refine", "reject_floor", and "reject_cost" all share
                # the needs_refinement transition — downstream
                # feedback-loop logic handles them identically.  The
                # distinction surfaces in span.outcome + the structured
                # log line for operator diagnosis.
                outcome_label = {
                    "refine": "regressed",
                    "reject_floor": "rejected_floor",
                    "reject_cost": "rejected_cost",
                }[verdict]
                async with self._state_lock:
                    self._state.update_resource(
                        resource.path,
                        status="needs_refinement",
                        last_evaluated_version=resource.version,
                        refinement_count=resource.refinement_count + 1,
                    )
                resource_span.set_attribute(
                    "harness.eval.outcome", outcome_label
                )
                progress_msg = {
                    "refine": "regression",
                    "reject_floor": "rejected (below floor)",
                    "reject_cost": "rejected (cost regression)",
                }[verdict]
                self._emit_progress(
                    "EXECUTION_EVAL", resource.path, progress_msg,
                    results.candidate_pass_rate,
                )
                if verdict == "reject_floor":
                    logger.warning(
                        "EXECUTION_EVAL: Below floor — prompt engineering "
                        "is net-negative vs bare model",
                        path=resource.path,
                        candidate_pass_rate=f"{results.candidate_pass_rate:.2f}",
                        floor_pass_rate=(
                            f"{results.floor_pass_rate:.2f}"
                            if results.floor_pass_rate is not None
                            else "n/a"
                        ),
                    )
                elif verdict == "reject_cost":
                    logger.warning(
                        "EXECUTION_EVAL: Quality passed but cost regressed "
                        "beyond τ",
                        path=resource.path,
                        candidate_pass_rate=f"{results.candidate_pass_rate:.2f}",
                        baseline_pass_rate=f"{results.baseline_pass_rate:.2f}",
                        candidate_cps=(
                            f"${results.candidate_cost_per_success:.4f}"
                            if results.candidate_cost_per_success is not None
                            else "n/a"
                        ),
                        baseline_cps=(
                            f"${results.baseline_cost_per_success:.4f}"
                            if results.baseline_cost_per_success is not None
                            else "n/a"
                        ),
                        tau=f"{tau:.2f}",
                    )
                else:
                    logger.warning(
                        "EXECUTION_EVAL: Regression",
                        path=resource.path,
                        candidate_pass_rate=f"{results.candidate_pass_rate:.2f}",
                        baseline_pass_rate=f"{results.baseline_pass_rate:.2f}",
                        win_rate=f"{results.win_rate:.2f}",
                    )

    return (resource, results, verdict_for_aggregate)


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


# Phase A refinement 4.3: cost-gate tolerance.  ``τ`` is the fractional
# headroom the candidate has above the incumbent's cost_per_success;
# 0.10 = candidate may cost up to 10% more per success than incumbent.
# Tighten over time as the gate matures.
DEFAULT_TOKEN_REGRESSION_TOLERANCE = 0.10


def _resolve_cost_tolerance() -> float:
    """Read ``CGF_TOKEN_REGRESSION_TOLERANCE`` from the environment.

    Invalid / non-positive values fall back to ``0.10``.  Operators can
    set ``0.0`` for "no cost regression allowed" or e.g. ``0.5`` for a
    looser gate during early calibration.
    """
    raw = os.environ.get("CGF_TOKEN_REGRESSION_TOLERANCE")
    if not raw:
        return DEFAULT_TOKEN_REGRESSION_TOLERANCE
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TOKEN_REGRESSION_TOLERANCE
    return max(0.0, value)


def _should_promote(results: EvalResults, epsilon: float) -> bool:
    """Backwards-compat shim — delegates to :mod:`gating`.

    Pre-refinement-4.2 callers (and the existing unit tests) expect a
    boolean.  Internally we route through :func:`gate_decide` so that
    the floor stage is honoured whenever floor_pass_rate is recorded
    on the results.  Callers that need the richer 3-way verdict
    should use :func:`gate_decide` directly.

    ``is_first_promotion=True`` is assumed when floor data exists —
    EvalHarness only emits ``floor_pass_rate`` on first-promotion runs
    by construction, so this is exact, not heuristic.
    """
    verdict = gate_decide(
        GateInputs(
            candidate_pass_rate=results.candidate_pass_rate,
            incumbent_pass_rate=results.baseline_pass_rate,
            floor_pass_rate=results.floor_pass_rate,
            is_first_promotion=results.floor_pass_rate is not None,
            epsilon=epsilon,
        )
    )
    return verdict == "promote"


def _record_held_out_usage(
    workspace: Path,
    per_resource_results: list[
        tuple[ResourceStatus, EvalResults, AggregateVerdict]
    ],
) -> None:
    """Phase A refinement 4.4.c: held-out scenario usage bookkeeping.

    For every held-out scenario that was decisive (baseline+candidate
    each had ≥1 decisive trial), increment its ``uses`` counter and
    set ``first_used_at`` if still null.  Written to
    ``eval/held-out-usage.json`` as a sidecar — NOT back to
    eval-suite.yaml, which would trip 4.4.a's hash check.

    Phase A is bookkeeping only.  Phase D will read this file to
    rotate held-out scenarios on contact.

    Best-effort: file IO failures are logged but never break the
    pipeline (this is observability, not a gate).
    """
    if not per_resource_results:
        return
    usage_path = workspace / "eval" / "held-out-usage.json"
    try:
        existing: dict[str, dict[str, Any]] = {}
        if usage_path.exists():
            existing = json.loads(usage_path.read_text(encoding="utf-8"))
        now = datetime.now(UTC).isoformat()
        for _, results, _verdict in per_resource_results:
            for sr in results.scenarios:
                if not sr.held_out:
                    continue
                # "Decisive" = both arms produced at least one decisive
                # trial.  Matches compare_arms' no_decision detection.
                if sr.baseline.decisive == 0 or sr.candidate.decisive == 0:
                    continue
                entry = existing.get(sr.scenario_id, {"uses": 0, "first_used_at": None})
                entry["uses"] = int(entry.get("uses", 0)) + 1
                if entry.get("first_used_at") is None:
                    entry["first_used_at"] = now
                existing[sr.scenario_id] = entry
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        usage_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "EXECUTION_EVAL: held-out usage updated",
            path=str(usage_path),
            tracked_scenarios=len(existing),
        )
    except Exception as exc:  # noqa: BLE001 — bookkeeping must not break gate
        logger.warning(
            "EXECUTION_EVAL: held-out usage bookkeeping failed (non-fatal)",
            error=str(exc)[:200],
        )


def _round_mean_candidate_pass_rate(
    per_resource_results: list[
        tuple[ResourceStatus, EvalResults, AggregateVerdict]
    ],
) -> float:
    """Phase A refinement 4.4.b: mean candidate pass-rate across all
    resources in this round.

    Used by the stagnation early-stop check.  Computed over the FULL
    per-resource set (not just regressions) so the signal is stable
    across rounds even as different resources move in and out of
    refinement.  Empty list → 0.0 (safe default; the caller short-
    circuits before computing if there's nothing to evaluate).
    """
    if not per_resource_results:
        return 0.0
    return sum(
        r.candidate_pass_rate for _, r, _v in per_resource_results
    ) / len(per_resource_results)


def _resolve_min_gain() -> float:
    """Phase A refinement 4.4.b: parse ``CGF_MIN_GAIN_PER_ROUND``.

    Default 0.02 (2pp).  Negative values are clamped to 0 (= "any
    non-regression survives").  Invalid → default.
    """
    raw = os.environ.get("CGF_MIN_GAIN_PER_ROUND")
    if not raw:
        return DEFAULT_MIN_GAIN_PER_ROUND
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_MIN_GAIN_PER_ROUND
    return max(0.0, value)


def _build_feedback_entry(
    regressions: list[tuple[ResourceStatus, EvalResults, GateVerdict]],
    feedback_iteration: int,
    round_mean_candidate_pass_rate: float | None = None,
) -> dict[str, Any]:
    """Assemble a feedback record for ``state.feedback_history``.

    The entry is later read by the ITERATE phase's prompt builder to
    show the optimizer which scenarios it failed and what the baseline
    handled correctly.  Held-out scenarios are explicitly stripped so
    the optimizer never sees them.

    Phase A refinement 4.4.b: ``round_mean_candidate_pass_rate`` is
    recorded so the next round's stagnation check can compare against
    it cheaply (no recomputation needed).

    I15: each regression entry now carries the gate verdict and the
    full cost-gate inputs so the optimizer's per-call refinement prompt
    can branch by failure-mode:

      - ``verdict``: ``"refine"`` / ``"reject_floor"`` / ``"reject_cost"``
      - ``baseline_cost_per_success`` / ``candidate_cost_per_success``
      - ``floor_pass_rate``: populated on first-time-promotion rounds
      - ``cost_tolerance``: the base τ at gate time
      - ``effective_cost_tolerance``: τ_eff after quality-scaled bonus
      - ``cost_per_success_delta_pct``: candidate cps minus incumbent
        cps as a fraction of incumbent (positive = regressed)

    Without these the optimizer can't tell whether to TRIM (cost
    rejection) vs ADD-COVERAGE (quality rejection) vs DROP-STRUCTURE
    (floor rejection).  Run #7 demonstrated the failure mode: cost-
    rejected candidates got re-bloated in r2 because the optimizer
    saw only pass-rate equality and concluded "quality is fine."
    """
    base_tau = _resolve_cost_tolerance()
    bonus_factor = _resolve_cost_quality_bonus()

    resources_data: list[dict[str, Any]] = []
    for resource, results, verdict in regressions:
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

        # I15: compute effective τ at feedback-write time so the
        # optimizer sees the same number the gate used.  ``decide``
        # recomputes it during evaluation; we mirror that here rather
        # than threading the value through the helper signature.
        quality_delta = (
            results.candidate_pass_rate - results.baseline_pass_rate
        )
        eff_tau = effective_cost_tolerance(
            base_tau=base_tau,
            quality_delta=quality_delta,
            bonus_factor=bonus_factor,
        )

        # cps delta — only meaningful when both sides have signal.
        b_cps = results.baseline_cost_per_success
        c_cps = results.candidate_cost_per_success
        if b_cps is not None and c_cps is not None and b_cps > 0:
            cps_delta_pct = (c_cps - b_cps) / b_cps
        else:
            cps_delta_pct = None

        resources_data.append(
            {
                "path": resource.path,
                "verdict": verdict,
                "candidate_pass_rate": results.candidate_pass_rate,
                "baseline_pass_rate": results.baseline_pass_rate,
                "floor_pass_rate": results.floor_pass_rate,
                "win_rate": results.win_rate,
                "baseline_cost_per_success": b_cps,
                "candidate_cost_per_success": c_cps,
                "cost_per_success_delta_pct": cps_delta_pct,
                "cost_tolerance": base_tau,
                "effective_cost_tolerance": eff_tau,
                "failing_scenarios": failing,
            }
        )

    return {
        "feedback_iteration": feedback_iteration,
        "timestamp": datetime.now(UTC).isoformat(),
        "regressions": resources_data,
        "round_mean_candidate_pass_rate": round_mean_candidate_pass_rate,
    }


def _write_aggregate_results(
    *,
    workspace: Path,
    per_resource_results: list[
        tuple[ResourceStatus, EvalResults, AggregateVerdict]
    ],
    feedback_iteration: int,
) -> Path | None:
    """Write a top-level summary of this EXECUTION_EVAL run.

    Returns the path written, or None if nothing to write.  Per-resource
    detailed results are already on disk under
    ``eval/results/{resource_path}-v{N}/eval-results.json`` (written by
    each :class:`EvalHarness` invocation).  This summary file is the
    one-glance view across all resources.

    Records the actual gate verdict (``"promote"``, ``"refine"``,
    ``"reject_floor"``, ``"reject_cost"``, ``"unwinnable"``) per
    resource.  ``promoted`` is preserved as a back-compat boolean
    derived strictly from the verdict — old readers (``run_report``,
    pre-refinement post-mortem scripts) keep working; new readers can
    inspect ``verdict`` for the full distinction (e.g. floor vs cost
    rejection).
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
                "floor_pass_rate": results.floor_pass_rate,
                "no_decision_rate": results.no_decision_rate,
                "scenarios": len(results.scenarios),
                # Phase A refinement 4.3: surface cost-per-success +
                # gate inputs so post-mortem analysis doesn't need to
                # re-derive them from per-resource eval-results.json.
                "baseline_cost_per_success": results.baseline_cost_per_success,
                "candidate_cost_per_success": results.candidate_cost_per_success,
                "total_cost_usd": results.total_cost_usd,
                # Authoritative gate verdict — agrees with
                # ``optimization-state.json``'s per-resource ``status``
                # (promote↔optimized, refine/reject_*↔needs_refinement,
                # unwinnable↔unwinnable). Set even when status was
                # written by a different code path.
                "verdict": verdict,
                # Back-compat boolean for older readers; derived strictly
                # from verdict so it can never disagree with status.
                "promoted": verdict == "promote",
            }
            for resource, results, verdict in per_resource_results
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
