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
    EvalResults,
    EvalSuite,
    ScenarioResult,
    ScenarioWithGraders,
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
    ) -> EvalResults:
        """Run the full eval suite against both arms and return results.

        When ``results_dir`` is provided, the harness writes
        ``eval-results.json`` to that directory.  When omitted, the
        results are returned in-memory only — useful for tests.
        """
        suite_path = Path(eval_suite_path)
        baseline_path = Path(baseline_resource)
        candidate_path = Path(candidate_resource)

        suite = load_eval_suite(suite_path)
        logger.info(
            "eval_harness.run start",
            suite=str(suite_path),
            baseline=str(baseline_path),
            candidate=str(candidate_path),
            scenarios=len(suite.scenarios),
            trials_per_scenario=suite.config.trials_per_scenario,
        )

        scenarios: list[ScenarioResult] = []
        for scenario_with_graders in suite.scenarios:
            scenarios.append(
                await self.run_scenario(
                    scenario_with_graders, baseline_path, candidate_path, suite
                )
            )

        results = self._assemble_results(
            scenarios, suite_path, baseline_path, candidate_path
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
    ) -> ScenarioResult:
        """Run K trials of each arm against one scenario."""
        baseline_trials = await self._run_arm(
            scenario_with_graders, baseline_resource, "baseline", suite
        )
        candidate_trials = await self._run_arm(
            scenario_with_graders, candidate_resource, "candidate", suite
        )

        baseline_results = aggregate_arm("baseline", baseline_trials)
        candidate_results = aggregate_arm("candidate", candidate_trials)
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

            transcript = await self._collect_transcript(
                resource=resource,
                prompt=scenario.prompt,
                cwd=workspace,
                env=env_overrides,
                timeout=suite.config.timeout_seconds,
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
        """
        # Imported here so the module loads cleanly in test environments
        # that mock the SDK or run without it on PYTHONPATH.
        from claude_agent_sdk import ClaudeAgentOptions, query

        spec = _parse_resource_file(resource)

        # Apply env overrides scoped to the SDK call.  We restore on exit
        # to avoid bleeding into other concurrent harness work.
        env = env or {}
        prior: dict[str, str | None] = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            options = ClaudeAgentOptions(
                system_prompt=spec["prompt"],
                model=spec["model"],
                allowed_tools=spec["tools"],
                permission_mode="acceptEdits",
                cwd=str(cwd),
                max_turns=spec["max_turns"],
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
    ) -> EvalResults:
        overall = aggregate_subset(scenarios)
        held_out_subset = [s for s in scenarios if s.held_out]
        held_out_stats = aggregate_subset(held_out_subset) if held_out_subset else None

        total_tokens = sum(
            t.transcript.total_tokens
            for s in scenarios
            for arm in (s.baseline, s.candidate)
            for t in arm.trials
        )

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
        )

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
