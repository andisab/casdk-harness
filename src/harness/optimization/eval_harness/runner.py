"""EvalHarness — runs an :class:`EvalSuite` against a (baseline, candidate)
resource pair and produces :class:`EvalResults` (Phase A.4).

Per scenario, runs ``trials_per_scenario`` trials on each arm, materializes
each scenario's setup files in an isolated temp directory, invokes the
resource as an ad-hoc agent via the SDK ``query()`` function (NOT through
:mod:`harness.subagent` — that module's registry lookup is for named
agents, but eval candidates are unregistered file paths), captures the
message stream into an :class:`AgentTranscript`, runs every grader
against the transcript, and assembles a :class:`TrialResult`.

Aggregation lives in :mod:`harness.optimization.eval_harness.aggregate`.

Phase A ships ``runtime="in_process"`` only — Phase C will add an
``"ephemeral_container"`` runtime that wraps each trial in
``docker compose run --rm`` for SWE-bench-style determinism.

F12: Scenarios within a single ``run()`` execute in parallel under an
``asyncio.Semaphore`` bounded by ``CGF_EVAL_SCENARIO_CONCURRENCY``
(default 6).  The two arms of a scenario also run concurrently — they
are independent SDK calls and gain a free 2x on top of the
inter-scenario fan-out.  Set the concurrency env var to ``1`` to
restore sequential behavior (useful for rate-limit debugging).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
import yaml

from harness.optimization.eval_harness.aggregate import (
    aggregate_arm,
    aggregate_subset,
    compare_arms,
    group_by_level,
    group_by_tag,
)
from harness.optimization.eval_harness.loader import load_eval_suite
from harness.optimization.eval_harness.models import (
    Arm,
    ArmResults,
    EvalResults,
    EvalSuite,
    ScenarioResult,
    ScenarioWithGraders,
    SubsetStats,
    TrialResult,
)
from harness.optimization.graders import (
    AgentTranscript,
    BaseGrader,
    EvalScenario,
    GraderResult,
    TranscriptBuilder,
)

logger = structlog.get_logger(__name__)

Runtime = Literal["in_process", "ephemeral_container"]


# ---------------------------------------------------------------------------
# Resource file parsing — matches plugin_manager._parse_agent_file but
# deliberately decoupled (eval works on bare file paths, not registry).
# ---------------------------------------------------------------------------


_VALID_MODELS = {"sonnet", "opus", "haiku"}


DEFAULT_EVAL_SCENARIO_CONCURRENCY = 6

# F19: per-level trial-timeout defaults.  Unit + e2e get the tighter
# 180s; trajectory gets 300s because it needs to elicit multi-step tool
# sequences.  Both fall back to the suite's ``config.timeout_seconds``
# when the matching env var is unset.
DEFAULT_EVAL_TRIAL_TIMEOUT_SECONDS = 180
DEFAULT_EVAL_TRAJECTORY_TRIAL_TIMEOUT_SECONDS = 300


def _resolve_trial_timeout(level: str, suite_default: int) -> int:
    """F19: pick per-trial timeout based on scenario level.

    Trajectory scenarios get a separate, more generous default because
    they typically need to coordinate multiple tool calls.  Both kinds
    fall back to ``suite.config.timeout_seconds`` when the matching env
    var is unset (preserves pre-F19 behavior for existing suites).

    Resolution order:

    1. Env var matching the level (``CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT``
       for trajectory, ``CGF_EVAL_TRIAL_TIMEOUT`` for unit / e2e).
    2. Module-level default (180 or 300).
    3. Suite config (``timeout_seconds``) — only used when both the
       env var and module default are deemed unset by the caller; in
       practice we always return one of the first two.

    Invalid env values fall through to the module default.
    """
    if level == "trajectory":
        env_var = "CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT"
        builtin = DEFAULT_EVAL_TRAJECTORY_TRIAL_TIMEOUT_SECONDS
    else:
        env_var = "CGF_EVAL_TRIAL_TIMEOUT"
        builtin = DEFAULT_EVAL_TRIAL_TIMEOUT_SECONDS

    raw = os.environ.get(env_var)
    if raw is not None:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass

    # Suite default takes precedence over the module builtin only when
    # the suite specifies something less permissive (suites authored
    # before F19 expected the global to apply); otherwise use the
    # tighter F19 default.
    if suite_default > 0 and suite_default < builtin:
        return suite_default
    return builtin


def _resolve_scenario_concurrency() -> int:
    """Read ``CGF_EVAL_SCENARIO_CONCURRENCY`` from the environment.

    F12: bounds the per-resource fan-out across scenarios.  Default
    6 gives ~12 in-flight SDK calls per resource (6 scenarios × 2
    arms parallel).  Combined with ``CGF_EXECUTION_EVAL_CONCURRENCY=2``
    that's up to 24 concurrent calls — well below typical SDK
    rate limits but enough to amortize the per-call overhead.

    Invalid or non-positive values fall back to the default.  Set
    to 1 to restore the strict-sequential pre-F12 behavior.
    """
    raw = os.environ.get("CGF_EVAL_SCENARIO_CONCURRENCY")
    if not raw:
        return DEFAULT_EVAL_SCENARIO_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_EVAL_SCENARIO_CONCURRENCY
    return max(1, value)


def _resource_target_key(candidate_path: Path) -> str:
    """Reduce a candidate file path to the canonical key used by
    scenario.target_resource.

    Scenarios target the BASE resource path (e.g.
    ``skills/aws-cli/SKILL.md``), but the candidate file on disk has
    a version suffix (e.g. ``skills/aws-cli/SKILL-v1.md``).  Strip
    ``-v{N}`` from the stem before matching, and return a path
    relative to the workspace root.

    F16: workspace-root detection MUST use a marker only the true
    workspace root has — ``SPEC.md``.  Previous logic walked up
    looking for ``sessions/`` or ``eval/``, but per-resource
    ``sessions/`` directories (created by ProgressManager during
    optimization rounds) exist nested *inside* resource dirs (e.g.
    ``skills/aws-cli/sessions/``).  Detection picked the resource dir
    itself as root, dropping the type prefix from the returned key
    (``SKILL.md`` instead of ``skills/aws-cli/SKILL.md``).  The result
    was: every resource produced ``target_key`` equal to just the
    filename, no scenarios matched the filter, and every resource
    reported 0-vs-0 ties.  See run #5h log for the failure mode.

    Examples::

        /workspace/iac-team/skills/aws-cli/SKILL-v1.md
            → skills/aws-cli/SKILL.md
        /workspace/iac-team/agents/iac-analyzer-v3.md
            → agents/iac-analyzer.md
    """
    import re

    name = candidate_path.name
    # Strip "-v{N}" from the stem while keeping the suffix.
    stripped = re.sub(r"-v\d+(\.[^/]+)$", r"\1", name)
    base = candidate_path.with_name(stripped)

    # F16: ``SPEC.md`` is the workspace-root marker because (a) it's
    # required at the workspace root for the orchestrator to find the
    # spec and (b) no per-resource subdirectory carries one.  ``.claude-plugin/``
    # is the secondary marker for plugin-style layouts where SPEC.md
    # has been renamed.  Fall back to ``resource-plan.yaml`` last
    # since it appears mid-pipeline.
    workspace_root: Path | None = None
    for parent in base.parents:
        if (parent / "SPEC.md").exists():
            workspace_root = parent
            break
        if (parent / ".claude-plugin").is_dir():
            workspace_root = parent
            break
        if (parent / "resource-plan.yaml").exists():
            workspace_root = parent
            break

    if workspace_root is not None:
        try:
            return str(base.relative_to(workspace_root))
        except ValueError:
            pass

    # Fallback: return the last 2-3 components.  Keeps unit tests
    # happy when run against ephemeral tmp_path layouts that don't
    # have SPEC.md.
    parts = base.parts
    if len(parts) >= 3 and parts[-3] == "skills":
        return str(Path(*parts[-3:]))
    if len(parts) >= 2:
        return str(Path(*parts[-2:]))
    return base.name


def _filter_scenarios_for_resource(
    suite: EvalSuite,
    target_key: str,
) -> list[ScenarioWithGraders]:
    """Return scenarios whose effective target_resource matches ``target_key``.

    "Effective" means: per-scenario override if set, otherwise the
    suite-level default.  Matching is exact-string against the
    workspace-relative path.  Scenarios that resolve to neither match
    nor the suite default are dropped — they were authored for a
    different resource and have no place running against this one.
    """
    out: list[ScenarioWithGraders] = []
    for swg in suite.scenarios:
        effective = swg.scenario.target_resource or suite.target_resource
        if effective == target_key:
            out.append(swg)
    return out


def _parse_resource_file(resource_path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter + body of a resource markdown file.

    Returns a dict with keys ``name``, ``description``, ``model``,
    ``tools`` (list[str] or None), ``max_turns`` (int), and ``prompt``
    (the body).  Falls back gracefully when frontmatter is missing —
    treats the whole file as the system prompt.
    """
    text = resource_path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        return {
            "name": resource_path.stem,
            "description": "",
            "model": "sonnet",
            "tools": None,
            "max_turns": 100,
            "prompt": text.strip(),
        }
    try:
        _, frontmatter, body = text.split("---", 2)
        meta = yaml.safe_load(frontmatter) or {}
    except Exception as exc:  # noqa: BLE001 — corrupt frontmatter, fall through
        logger.warning(
            "resource frontmatter parse failed; using whole file as prompt",
            path=str(resource_path),
            error=str(exc),
        )
        return {
            "name": resource_path.stem,
            "description": "",
            "model": "sonnet",
            "tools": None,
            "max_turns": 100,
            "prompt": text.strip(),
        }

    model_raw = str(meta.get("model") or "sonnet").lower().split()[0]
    model = model_raw if model_raw in _VALID_MODELS else "sonnet"
    tools_raw = meta.get("tools") or ""
    tools = (
        [t.strip() for t in tools_raw.split(",") if t.strip()]
        if isinstance(tools_raw, str) and tools_raw
        else None
    )
    return {
        "name": str(meta.get("name") or resource_path.stem),
        "description": str(meta.get("description") or ""),
        "model": model,
        "tools": tools,
        "max_turns": int(meta.get("max_turns") or 100),
        "prompt": body.strip(),
    }


# ---------------------------------------------------------------------------
# Workspace materialization
# ---------------------------------------------------------------------------


def _materialize_setup(
    workspace: Path,
    scenario: EvalScenario,
) -> dict[str, str]:
    """Write scenario.setup.files into ``workspace`` and return env overrides.

    The schema's pattern already rejects ``..`` traversal and absolute
    paths, but we double-check at runtime as defense-in-depth.
    """
    for setup_file in scenario.setup.files:
        rel = Path(setup_file.path)
        if rel.is_absolute() or any(part == ".." for part in rel.parts):
            raise ValueError(
                f"Refusing to write {setup_file.path!r}: must be relative without ..",
            )
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(setup_file.content, encoding="utf-8")
    return dict(scenario.setup.env)


# ---------------------------------------------------------------------------
# EvalHarness
# ---------------------------------------------------------------------------


class EvalHarness:
    """Runs eval suites against (baseline, candidate) resource pairs.

    Methods are layered for testability:

    - :meth:`run` — top-level: loads suite, runs all scenarios both arms,
      writes ``eval-results.json``.
    - :meth:`run_scenario` — runs one scenario's K trials per arm.
    - :meth:`_run_one_trial` — runs a single trial: setup → invoke →
      transcript → grade → :class:`TrialResult`.
    - :meth:`_invoke_from_resource` — async-yields SDK messages from a
      resource file invocation.  Tests stub this to return canned message
      streams.
    """

    def __init__(self, runtime: Runtime = "in_process") -> None:
        if runtime != "in_process":
            raise NotImplementedError(
                f"runtime={runtime!r} not yet implemented — Phase C adds "
                "ephemeral_container support"
            )
        self.runtime: Runtime = runtime

    # ----- public API -----

    async def run(
        self,
        eval_suite_path: str | Path,
        baseline_resource: str | Path,
        candidate_resource: str | Path,
        results_dir: str | Path | None = None,
        baseline_floor: str | Path | None = None,
    ) -> EvalResults:
        """Run the full eval suite against both arms and return results.

        When ``results_dir`` is provided, the harness writes
        ``eval-results.json`` to that directory.  When omitted, the
        results are returned in-memory only — useful for tests.

        F12: scenarios run in parallel under a semaphore bounded by
        ``CGF_EVAL_SCENARIO_CONCURRENCY`` (default 6).

        F13: scenarios are filtered by ``target_resource`` — only
        scenarios whose ``target_resource`` matches the candidate file
        (after stripping any ``-v{N}`` suffix) actually execute.
        Pre-F13 every resource ran every scenario in the suite, so
        the same 5-out-of-54 scenarios fired for every resource pair
        and the pass-rate signal was meaningless cross-resource
        accidents.  Scenarios with no explicit ``target_resource``
        fall back to the suite-level default.

        Phase A refinement 4.2: when ``baseline_floor`` is provided,
        a third arm runs concurrently with the other two for each
        scenario.  This is the bare-model sanity check, used only at
        the moment a resource is trying to promote its first version
        (see :mod:`harness.optimization.gating`).  Pass ``None`` (or
        omit) for the steady-state candidate-vs-incumbent case.
        """
        suite_path = Path(eval_suite_path)
        baseline_path = Path(baseline_resource)
        candidate_path = Path(candidate_resource)
        floor_path = Path(baseline_floor) if baseline_floor is not None else None

        suite = load_eval_suite(suite_path)
        concurrency = _resolve_scenario_concurrency()

        # F13: filter to scenarios targeting THIS resource.
        target_key = _resource_target_key(candidate_path)
        applicable = _filter_scenarios_for_resource(
            suite, target_key
        )
        if not applicable:
            logger.warning(
                "eval_harness.run no applicable scenarios; returning empty",
                candidate=str(candidate_path),
                target_key=target_key,
                suite_default=suite.target_resource,
                total_in_suite=len(suite.scenarios),
            )

        logger.info(
            "eval_harness.run start",
            suite=str(suite_path),
            baseline=str(baseline_path),
            candidate=str(candidate_path),
            scenarios=len(applicable),
            scenarios_in_suite=len(suite.scenarios),
            target_key=target_key,
            trials_per_scenario=suite.config.trials_per_scenario,
            scenario_concurrency=concurrency,
        )

        semaphore = asyncio.Semaphore(concurrency)

        async def _one(swg: ScenarioWithGraders) -> ScenarioResult:
            async with semaphore:
                return await self.run_scenario(
                    swg, baseline_path, candidate_path, suite,
                    floor_resource=floor_path,
                )

        # asyncio.gather preserves input order, so `scenarios` ends up
        # in the same order as the filtered list regardless of which
        # coroutine finishes first.  Downstream aggregation relies on
        # this for deterministic by_level / by_tag reports.
        scenarios: list[ScenarioResult] = list(
            await asyncio.gather(*[_one(swg) for swg in applicable])
        )

        results = self._assemble_results(
            scenarios, suite_path, baseline_path, candidate_path, suite
        )

        if results_dir is not None:
            self._write_results(results, Path(results_dir))

        logger.info(
            "eval_harness.run complete",
            win_rate=results.win_rate,
            baseline_pass=results.baseline_pass_rate,
            candidate_pass=results.candidate_pass_rate,
            no_decision_rate=results.no_decision_rate,
        )
        return results

    async def run_scenario(
        self,
        scenario_with_graders: ScenarioWithGraders,
        baseline_resource: Path,
        candidate_resource: Path,
        suite: EvalSuite,
        floor_resource: Path | None = None,
    ) -> ScenarioResult:
        """Run K trials of each arm against one scenario.

        F12: baseline and candidate arms are independent SDK calls —
        no shared state, no causal dependency — so we run them
        concurrently to halve scenario wall time.  Trials within an
        arm remain sequential (their results are aggregated by
        :func:`aggregate_arm`; sequential is the safer default for
        rate-limit friendliness).

        Phase A refinement 4.2: ``floor_resource`` adds a third arm
        when provided.  All three arms run concurrently — they are
        independent SDK calls.  The ``outcome`` decision still
        compares baseline-vs-candidate (the floor arm informs the
        promotion gate downstream but does not change the
        per-scenario win/tie classification).
        """
        if floor_resource is not None:
            baseline_trials, candidate_trials, floor_trials = await asyncio.gather(
                self._run_arm(
                    scenario_with_graders, baseline_resource, "baseline", suite
                ),
                self._run_arm(
                    scenario_with_graders, candidate_resource, "candidate", suite
                ),
                self._run_arm(
                    scenario_with_graders, floor_resource, "floor", suite
                ),
            )
        else:
            baseline_trials, candidate_trials = await asyncio.gather(
                self._run_arm(
                    scenario_with_graders, baseline_resource, "baseline", suite
                ),
                self._run_arm(
                    scenario_with_graders, candidate_resource, "candidate", suite
                ),
            )
            floor_trials = None

        baseline_results = aggregate_arm("baseline", baseline_trials)
        candidate_results = aggregate_arm("candidate", candidate_trials)
        floor_results = (
            aggregate_arm("floor", floor_trials) if floor_trials is not None else None
        )
        outcome = compare_arms(baseline_results, candidate_results)

        scenario = scenario_with_graders.scenario
        return ScenarioResult(
            scenario_id=scenario.id,
            level=scenario.level,
            held_out=scenario.held_out,
            tags=list(scenario.tags),
            difficulty=scenario.difficulty,
            baseline=baseline_results,
            candidate=candidate_results,
            outcome=outcome,
            floor=floor_results,
        )

    # ----- per-arm / per-trial -----

    async def _run_arm(
        self,
        scenario_with_graders: ScenarioWithGraders,
        resource: Path,
        arm: Arm,
        suite: EvalSuite,
    ) -> list[TrialResult]:
        trials: list[TrialResult] = []
        for trial_index in range(suite.config.trials_per_scenario):
            trials.append(
                await self._run_one_trial(
                    scenario_with_graders,
                    resource,
                    arm,
                    trial_index,
                    suite,
                )
            )
        return trials

    async def _run_one_trial(
        self,
        scenario_with_graders: ScenarioWithGraders,
        resource: Path,
        arm: Arm,
        trial_index: int,
        suite: EvalSuite,
    ) -> TrialResult:
        scenario = scenario_with_graders.scenario
        graders = scenario_with_graders.graders

        with tempfile.TemporaryDirectory(prefix=f"eval-{scenario.id}-{arm}-") as tmp:
            workspace = Path(tmp)
            try:
                env_overrides = _materialize_setup(workspace, scenario)
            except ValueError as exc:
                return self._error_trial(arm, trial_index, str(exc))

            # F19: per-level timeout — trajectory scenarios elicit
            # multi-step tool sequences and need more wall time than
            # unit / e2e graders.
            trial_timeout = _resolve_trial_timeout(
                scenario.level, suite.config.timeout_seconds
            )
            transcript = await self._collect_transcript(
                resource=resource,
                prompt=scenario.prompt,
                cwd=workspace,
                env=env_overrides,
                timeout=trial_timeout,
            )

        # Grading happens after the temp dir is torn down — graders work
        # on the in-memory transcript only.
        grader_results = await self._run_graders(graders, transcript, scenario)
        passed = (
            len(grader_results) > 0
            and all(g.passed for g in grader_results)
            and not any(g.no_decision for g in grader_results)
        )
        no_decision = (
            any(g.no_decision for g in grader_results)
            or transcript.is_error
        )
        return TrialResult(
            arm=arm,
            trial_index=trial_index,
            transcript=transcript,
            grader_results=grader_results,
            passed=passed,
            no_decision=no_decision,
            error=transcript.error_message if transcript.is_error else "",
        )

    async def _run_graders(
        self,
        graders: list[BaseGrader],
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> list[GraderResult]:
        results: list[GraderResult] = []
        for g in graders:
            try:
                results.append(await g.grade(transcript, scenario))
            except Exception as exc:  # noqa: BLE001 — surface as failed grader
                logger.warning(
                    "grader raised; treating as failure",
                    grader=type(g).__name__,
                    error=str(exc),
                )
                results.append(
                    GraderResult(
                        passed=False,
                        score=0.0,
                        details=f"grader error: {type(exc).__name__}: {exc}",
                        grader_type=g.grader_type,
                    )
                )
        return results

    async def _collect_transcript(
        self,
        resource: Path,
        prompt: str,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> AgentTranscript:
        """Wrap _invoke_from_resource with TranscriptBuilder + timeout."""
        builder = TranscriptBuilder()
        try:
            async with asyncio.timeout(timeout):
                async for msg in self._invoke_from_resource(
                    resource=resource, prompt=prompt, cwd=cwd, env=env
                ):
                    builder.add_message(msg)
        except TimeoutError:
            transcript = builder.build()
            transcript.is_error = True
            transcript.error_message = f"timeout after {timeout}s"
            return transcript
        except Exception as exc:  # noqa: BLE001 — surface in transcript
            logger.warning(
                "_invoke_from_resource raised",
                resource=str(resource),
                error=str(exc),
            )
            transcript = builder.build()
            transcript.is_error = True
            transcript.error_message = f"{type(exc).__name__}: {exc}"
            return transcript
        return builder.build()

    async def _invoke_from_resource(
        self,
        resource: Path,
        prompt: str,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> AsyncIterator[Any]:
        """Yield SDK messages from invoking a resource file as an ad-hoc agent.

        Reads the resource's YAML frontmatter for ``model`` / ``tools`` /
        ``max_turns``, uses the body as the system prompt, and calls the
        SDK's ``query()`` directly (not through ``harness.subagent``).
        Tests override this method to return canned message streams.

        F10 fix: mirrors the F2 wiring from ``harness.subagent`` — passes
        ``plugins=`` so plugin agents/skills are surfaced, ``skills="all"``
        so the Skill tool accepts plugin skills, and ``setting_sources=
        ["project"]`` so ``.claude/agents/`` is discoverable.  Without
        this, ``allowed_tools=None`` (skills typically have no ``tools:``
        frontmatter) propagated into the SDK and a downstream consumer
        attempted to iterate it, raising ``'NoneType' object is not
        iterable`` for every scenario — making every grader score 0.
        """
        # Imported here so the module loads cleanly in test environments
        # that mock the SDK or run without it on PYTHONPATH.
        from claude_agent_sdk import ClaudeAgentOptions, query

        spec = _parse_resource_file(resource)

        # Build SDK plugin paths so the invoked resource can resolve
        # Skill, Task, and sub-agent references.  Reuse the discovery
        # logic from ``harness.subagent`` (which already handles
        # marketplace-vs-in-tree precedence + enabled_plugins config).
        # Failing to load the plugin manager must not break grading —
        # fall back to no plugins.
        sdk_plugins: list[dict[str, str]] = []
        try:
            from harness import subagent as _sa

            _sa._load_plugin_agents()  # idempotent; builds _plugin_manager
            if _sa._plugin_manager is not None:
                sdk_plugins = _sa._plugin_manager.get_plugin_paths()
        except Exception:  # noqa: BLE001 — plugin layer must never break a call
            sdk_plugins = []

        # Apply env overrides scoped to the SDK call.  We restore on exit
        # to avoid bleeding into other concurrent harness work.
        env = env or {}
        prior: dict[str, str | None] = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            # F10: allowed_tools must be a list (possibly empty) — never
            # None.  The SDK appears to iterate over allowed_tools in at
            # least one code path; passing None tripped TypeError.
            allowed_tools = spec["tools"] if spec["tools"] else []
            options = ClaudeAgentOptions(
                system_prompt=spec["prompt"],
                model=spec["model"],
                allowed_tools=allowed_tools,
                permission_mode="acceptEdits",
                cwd=str(cwd),
                max_turns=spec["max_turns"],
                plugins=sdk_plugins,
                skills="all",
                setting_sources=["project"],
            )
            async for message in query(prompt=prompt, options=options):
                yield message
        finally:
            for k, original in prior.items():
                if original is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = original

    # ----- assembly + IO -----

    def _error_trial(
        self,
        arm: Arm,
        trial_index: int,
        error: str,
    ) -> TrialResult:
        """Build a TrialResult representing a runtime error before SDK call."""
        return TrialResult(
            arm=arm,
            trial_index=trial_index,
            transcript=AgentTranscript(is_error=True, error_message=error),
            grader_results=[],
            passed=False,
            no_decision=True,
            error=error,
        )

    def _assemble_results(
        self,
        scenarios: list[ScenarioResult],
        suite_path: Path,
        baseline_path: Path,
        candidate_path: Path,
        suite: EvalSuite,
    ) -> EvalResults:
        overall = aggregate_subset(scenarios)
        held_out_subset = [s for s in scenarios if s.held_out]
        held_out_stats = aggregate_subset(held_out_subset) if held_out_subset else None

        # Token / cost sums include the floor arm when present so
        # operator dashboards see the full per-run footprint, not just
        # baseline+candidate.  Phase A refinement 4.2.
        def _all_arms(s: ScenarioResult) -> tuple[ArmResults, ...]:
            arms: tuple[ArmResults, ...] = (s.baseline, s.candidate)
            if s.floor is not None:
                arms = (*arms, s.floor)
            return arms

        total_tokens = sum(
            t.transcript.total_tokens
            for s in scenarios
            for arm in _all_arms(s)
            for t in arm.trials
        )
        total_cost_usd = sum(
            t.transcript.total_cost_usd
            for s in scenarios
            for arm in _all_arms(s)
            for t in arm.trials
        )

        # Phase A refinement 4.2: floor arm aggregate.  We compute a
        # SubsetStats *equivalent* shape but the win-rate axis isn't
        # meaningful for floor (no baseline-vs-floor compare); we
        # populate it with the mean floor pass-rate only.
        floor_scenarios = [s for s in scenarios if s.floor is not None]
        floor_stats: SubsetStats | None = None
        floor_pass_rate: float | None = None
        if floor_scenarios:
            mean_floor_pass = (
                sum(s.floor.pass_rate for s in floor_scenarios if s.floor)
                / len(floor_scenarios)
            )
            floor_pass_rate = mean_floor_pass
            # Reuse SubsetStats shape; win_rate / no_decision_rate not
            # meaningful here so we leave them at 0.0.  Consumers should
            # read ``EvalResults.floor_pass_rate`` for the headline number.
            floor_stats = SubsetStats(
                count=len(floor_scenarios),
                win_rate=0.0,
                baseline_pass_rate=0.0,
                candidate_pass_rate=mean_floor_pass,
                no_decision_rate=0.0,
            )

        # Phase A refinement 4.1: pin judge identity for this run.
        # Resolve via the same helper LLMJudgeGrader uses so the recorded
        # ID matches what the grader actually called.  Suite config
        # overrides env (legacy path), env overrides default.
        judge_model_id = ""
        judge_prompt_hash = ""
        if self._has_llm_judge(suite):
            from harness.optimization.graders.llm_judge import (
                _resolve_judge_model,
            )
            from harness.optimization.graders.llm_judge import (
                judge_prompt_hash as compute_judge_prompt_hash,
            )

            judge_model_id = _resolve_judge_model(suite.config.eval_model)
            # Hash is rubric-shape dependent; record the hash of the
            # first scenario's first llm_judge prompt as a representative
            # fingerprint for the suite.  Phase D's calibration may need
            # per-rubric hashes — defer that until calibration lands.
            for swg in suite.scenarios:
                for g in swg.graders:
                    rubric = getattr(g, "rubric", None)
                    if rubric:
                        # Use the first arm/trial transcript as the
                        # transcript fingerprint, falling back to an
                        # empty one if none ran.
                        first_transcript = None
                        for sr in scenarios:
                            if sr.scenario_id == swg.scenario.id:
                                for trial in sr.baseline.trials:
                                    first_transcript = trial.transcript
                                    break
                                break
                        if first_transcript is None:
                            from harness.optimization.graders.transcript import (
                                AgentTranscript,
                            )

                            first_transcript = AgentTranscript()
                        judge_prompt_hash = compute_judge_prompt_hash(
                            rubric, first_transcript
                        )
                        break
                if judge_prompt_hash:
                    break

        return EvalResults(
            suite_path=str(suite_path),
            baseline_resource=str(baseline_path),
            candidate_resource=str(candidate_path),
            timestamp=datetime.now(UTC).isoformat(),
            scenarios=scenarios,
            win_rate=overall.win_rate,
            baseline_pass_rate=overall.baseline_pass_rate,
            candidate_pass_rate=overall.candidate_pass_rate,
            no_decision_rate=overall.no_decision_rate,
            held_out=held_out_stats,
            by_level=group_by_level(scenarios),
            by_tag=group_by_tag(scenarios),
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            judge_model_id=judge_model_id,
            judge_prompt_hash=judge_prompt_hash,
            floor=floor_stats,
            floor_pass_rate=floor_pass_rate,
        )

    @staticmethod
    def _has_llm_judge(suite: EvalSuite) -> bool:
        """True iff any scenario carries at least one LLMJudgeGrader."""
        for swg in suite.scenarios:
            for g in swg.graders:
                if type(g).__name__ == "LLMJudgeGrader":
                    return True
        return False

    @staticmethod
    def _write_results(results: EvalResults, results_dir: Path) -> Path:
        results_dir.mkdir(parents=True, exist_ok=True)
        out = results_dir / "eval-results.json"
        out.write_text(
            json.dumps(results.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("eval_harness.write_results", path=str(out))
        return out
