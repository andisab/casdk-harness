"""Tests for the eval_harness package (CGF Stage 3 Phase A.4)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness.optimization.eval_harness import (
    ArmResults,
    EvalHarness,
    EvalResults,
    EvalSuite,
    EvalSuiteValidationError,
    ScenarioResult,
    ScenarioWithGraders,
    SubsetStats,
    TrialResult,
    aggregate_arm,
    aggregate_subset,
    compare_arms,
    group_by_level,
    group_by_tag,
    load_eval_suite,
)
from harness.optimization.graders import (
    AgentTranscript,
    GraderResult,
    TranscriptMessage,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_suite_doc() -> dict[str, Any]:
    """Smallest valid eval-suite YAML doc."""
    return {
        "version": "1.0",
        "target_resource": "agents/example.md",
        "config": {"trials_per_scenario": 1, "timeout_seconds": 60},
        "scenarios": [
            {
                "id": "smoke-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
            }
        ],
    }


def _write_yaml(tmp_path: Path, doc: dict[str, Any]) -> Path:
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


def _write_resource(tmp_path: Path, name: str, body: str = "Be helpful.") -> Path:
    """Write a resource file under ``agents/example-v{N}.md`` so that
    F13's target_resource filter (suite default ``agents/example.md``)
    matches.  ``baseline`` → ``-v0``, ``candidate`` → ``-v1`` —
    distinct files on disk that share the same canonical target_key.

    F16: workspace-root marker is ``SPEC.md`` (not ``sessions/``).
    Per-resource sessions/ dirs are legal and must not be mistaken for
    workspace roots.
    """
    suffix = {"baseline": "-v0", "candidate": "-v1"}.get(name, "")
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    # F16: SPEC.md is the canonical workspace marker.
    spec = tmp_path / "SPEC.md"
    if not spec.exists():
        spec.write_text("# test spec")
    p = agents_dir / f"example{suffix}.md"
    p.write_text(
        f"---\nname: example\nmodel: sonnet\ntools: Read, Write\n---\n{body}\n",
        encoding="utf-8",
    )
    return p


def _trial(
    arm: str,
    *,
    passed: bool,
    no_decision: bool = False,
    error: str = "",
    score: float = 1.0,
    final_output: str = "",
    tokens: int = 100,
    grader_type: str = "exact",
) -> TrialResult:
    """Build a TrialResult with one synthetic grader result."""
    transcript = AgentTranscript(
        messages=[TranscriptMessage("assistant", final_output, 1)],
        tool_calls=[],
        final_output=final_output,
        total_turns=1,
        total_tokens=tokens,
        is_error=bool(error),
        error_message=error,
    )
    grader_results = (
        []
        if no_decision and not passed and not error
        else [
            GraderResult(
                passed=passed,
                score=score,
                details="synthetic",
                grader_type=grader_type,  # type: ignore[arg-type]
                no_decision=no_decision,
            )
        ]
    )
    # Re-evaluate passed/no_decision from grader_results so the synthetic
    # trial matches what the runner would produce.
    return TrialResult(
        arm=arm,  # type: ignore[arg-type]
        trial_index=0,
        transcript=transcript,
        grader_results=grader_results,
        passed=passed and not no_decision and not error,
        no_decision=no_decision or bool(error),
        error=error,
    )


def _scenario_result(
    scenario_id: str,
    level: str,
    *,
    held_out: bool = False,
    tags: list[str] | None = None,
    baseline_pass_rate: float = 0.5,
    candidate_pass_rate: float = 1.0,
    decisive: int = 2,
    outcome: str = "candidate_win",
) -> ScenarioResult:
    """Build a ScenarioResult directly for aggregation tests."""
    baseline = ArmResults(
        arm="baseline",
        trials=[],
        decisive=decisive,
        pass_rate=baseline_pass_rate,
        pass_at_k=1.0 if baseline_pass_rate > 0 else 0.0,
        pass_caret_k=1.0 if baseline_pass_rate == 1.0 else 0.0,
        avg_score=baseline_pass_rate,
    )
    candidate = ArmResults(
        arm="candidate",
        trials=[],
        decisive=decisive,
        pass_rate=candidate_pass_rate,
        pass_at_k=1.0 if candidate_pass_rate > 0 else 0.0,
        pass_caret_k=1.0 if candidate_pass_rate == 1.0 else 0.0,
        avg_score=candidate_pass_rate,
    )
    return ScenarioResult(
        scenario_id=scenario_id,
        level=level,
        held_out=held_out,
        tags=tags or [],
        difficulty=None,
        baseline=baseline,
        candidate=candidate,
        outcome=outcome,  # type: ignore[arg-type]
    )


# =============================================================================
# Loader
# =============================================================================


class TestLoader:
    def test_loads_minimal_suite(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        assert isinstance(suite, EvalSuite)
        assert suite.version == "1.0"
        assert suite.target_resource == "agents/example.md"
        assert len(suite.scenarios) == 1
        assert isinstance(suite.scenarios[0], ScenarioWithGraders)
        assert suite.config.trials_per_scenario == 1

    def test_eval_model_unset_defaults_to_none(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        """I6 regression guard: a suite that omits ``eval_model`` must
        load with ``config.eval_model = None`` so the runner falls
        through to ``CGF_JUDGE_MODEL`` env (default opus per Phase A.4.1).

        The pre-I6 loader synthesized a hardcoded sonnet/opus string here,
        which then bypassed the env path at ``runner.py:848`` —
        ``_resolve_judge_model(suite.config.eval_model)`` — because the
        explicit-param branch fired with the synthesized value.
        """
        # minimal_suite_doc has no `config` block; loader returns defaults.
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        assert suite.config.eval_model is None

    def test_eval_model_explicit_override_preserved(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        """An explicit ``eval_model`` set in the suite still propagates.

        I6 only removes the loader's hardcoded default — operators who
        deliberately pin a judge model (e.g. for replay/calibration) are
        unaffected.
        """
        minimal_suite_doc["config"] = {"eval_model": "claude-opus-4-7"}
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        assert suite.config.eval_model == "claude-opus-4-7"

    def test_eval_results_to_dict_includes_verdict_field(self) -> None:
        """I10: ``EvalResults.to_dict()`` must include ``verdict`` so the
        on-disk ``eval-results.json`` carries the gate decision.

        ``EvalHarness.run`` writes the file before the gate fires, so
        the field starts as ``None``; ``execution_eval`` re-stamps it
        post-gate via ``_stamp_verdict_on_disk``.  Either way the key
        is present.
        """
        from harness.optimization.eval_harness.models import EvalResults

        empty = EvalResults(
            suite_path="x.yaml",
            baseline_resource="b.md",
            candidate_resource="c.md",
            timestamp="2026-05-18T00:00:00+00:00",
            scenarios=[],
            win_rate=0.0,
            baseline_pass_rate=0.0,
            candidate_pass_rate=0.0,
            no_decision_rate=0.0,
            held_out=None,
            by_level={},
            by_tag={},
            total_tokens=0,
        )
        d = empty.to_dict()
        assert "verdict" in d
        assert d["verdict"] is None  # default, pre-stamp

        # After stamping, the field round-trips through to_dict.
        empty.verdict = "reject_cost"
        assert empty.to_dict()["verdict"] == "reject_cost"

    def test_stamp_verdict_on_disk_rewrites_eval_results_json(
        self, tmp_path: Path
    ) -> None:
        """I10: ``_stamp_verdict_on_disk`` rewrites the on-disk JSON
        with the stamped verdict; subsequent readers see the gate
        decision rather than ``null``.
        """
        from harness.optimization._orchestrator_phases.execution_eval import (
            _stamp_verdict_on_disk,
        )
        from harness.optimization.eval_harness.models import EvalResults

        results = EvalResults(
            suite_path="x.yaml",
            baseline_resource="b.md",
            candidate_resource="c.md",
            timestamp="2026-05-18T00:00:00+00:00",
            scenarios=[],
            win_rate=0.0,
            baseline_pass_rate=0.5,
            candidate_pass_rate=0.5,
            no_decision_rate=0.0,
            held_out=None,
            by_level={},
            by_tag={},
            total_tokens=0,
        )
        # Simulate EvalHarness writing the file first (no verdict yet).
        results_dir = tmp_path / "eval" / "results" / "x"
        results_dir.mkdir(parents=True)
        out = results_dir / "eval-results.json"
        out.write_text(json.dumps(results.to_dict(), indent=2))
        # Sanity: initial file has verdict=null.
        loaded = json.loads(out.read_text())
        assert loaded["verdict"] is None

        # Stamp + re-read.
        results.verdict = "promote"
        _stamp_verdict_on_disk(results_dir, results)

        loaded = json.loads(out.read_text())
        assert loaded["verdict"] == "promote"
        # Other fields preserved.
        assert loaded["candidate_pass_rate"] == 0.5

    def test_architect_prompt_does_not_hardcode_eval_model(self) -> None:
        """I6 regression guard: the cgf-eval-architect agent's prompt
        must not emit a literal ``eval_model:`` line in its output-schema
        example.

        Run #7 surfaced this — the prompt's example schema had
        ``eval_model: "claude-sonnet-4-5-20250929"`` which the architect
        faithfully copied into every generated eval-suite.yaml, silently
        overriding ``CGF_JUDGE_MODEL=opus`` env at the gate.

        We allow the substring to appear in comments / prose explaining
        why the field is omitted; what we forbid is a real YAML key on
        a non-comment line.
        """
        from pathlib import Path as _Path

        prompt_path = (
            _Path(__file__).resolve().parents[3]
            / "src"
            / "harness"
            / "plugins"
            / "cgf-agents"
            / "agents"
            / "eval"
            / "cgf-eval-architect.md"
        )
        assert prompt_path.exists(), (
            f"architect prompt missing at {prompt_path}"
        )
        for lineno, raw in enumerate(
            prompt_path.read_text().splitlines(), start=1
        ):
            stripped = raw.lstrip()
            # Skip prose, comments, and the markdown headings.
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            # The forbidden form is a YAML key assignment, not the bare
            # substring (which appears in field-name references throughout
            # the doc).  We catch a leading ``eval_model:`` token followed
            # by a non-empty value.
            if stripped.startswith("eval_model:"):
                value = stripped.split(":", 1)[1].strip()
                if value:  # actual value, not just `eval_model:` alone
                    raise AssertionError(
                        f"{prompt_path}:{lineno}: architect prompt hardcodes "
                        f"eval_model — found {raw!r}.  I6 requires omitting "
                        f"this field so CGF_JUDGE_MODEL env wins."
                    )

    def test_loads_with_full_config(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        minimal_suite_doc["config"] = {
            "trials_per_scenario": 5,
            "timeout_seconds": 600,
            "eval_model": "claude-sonnet-4-5-20250929",
            "token_budget": 500000,
            "held_out_fraction": 0.3,
        }
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        assert suite.config.trials_per_scenario == 5
        assert suite.config.timeout_seconds == 600
        assert suite.config.eval_model == "claude-sonnet-4-5-20250929"
        assert suite.config.token_budget == 500000
        assert suite.config.held_out_fraction == 0.3

    def test_constructs_graders(self, tmp_path: Path, minimal_suite_doc: dict) -> None:
        minimal_suite_doc["scenarios"][0]["graders"] = [
            {"type": "exact", "expected": "hi"},
            {
                "type": "trajectory",
                "assertions": [{"kind": "tool_called", "tool": "Read"}],
            },
            {
                "type": "composite",
                "operator": "and",
                "graders": [{"type": "contains", "needle": "ok"}],
            },
        ]
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        graders = suite.scenarios[0].graders
        assert len(graders) == 3
        # Verified by build_grader returning concrete subclass instances.

    def test_held_out_propagates(self, tmp_path: Path, minimal_suite_doc: dict) -> None:
        minimal_suite_doc["scenarios"][0]["held_out"] = True
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        assert suite.scenarios[0].scenario.held_out is True
        assert len(suite.held_out_scenarios) == 1

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_eval_suite(tmp_path / "missing.yaml")

    def test_top_level_not_mapping_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
        with pytest.raises(EvalSuiteValidationError):
            load_eval_suite(path)

    def test_schema_violation_raises(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        del minimal_suite_doc["version"]
        path = _write_yaml(tmp_path, minimal_suite_doc)
        with pytest.raises(EvalSuiteValidationError) as exc:
            load_eval_suite(path)
        assert "version" in str(exc.value).lower() or "<root>" in str(exc.value)

    def test_unknown_grader_type_raises(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        # Schema rejects unknown grader types via oneOf, but make sure
        # the loader surfaces it as EvalSuiteValidationError, not a
        # bare ValueError from build_grader.
        minimal_suite_doc["scenarios"][0]["graders"] = [{"type": "telepathy"}]
        path = _write_yaml(tmp_path, minimal_suite_doc)
        with pytest.raises(EvalSuiteValidationError):
            load_eval_suite(path)

    def test_setup_files_loaded(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        minimal_suite_doc["scenarios"][0]["setup"] = {
            "files": [{"path": "data.txt", "content": "hello"}],
            "env": {"FOO": "bar"},
        }
        path = _write_yaml(tmp_path, minimal_suite_doc)
        suite = load_eval_suite(path)
        scenario = suite.scenarios[0].scenario
        assert scenario.setup.files[0].path == "data.txt"
        assert scenario.setup.env == {"FOO": "bar"}


# =============================================================================
# Aggregation
# =============================================================================


class TestAggregateArm:
    def test_empty_trials(self) -> None:
        r = aggregate_arm("baseline", [])
        assert r.decisive == 0
        assert r.pass_rate == 0.0
        assert r.pass_at_k == 0.0
        assert r.pass_caret_k == 0.0

    def test_all_pass(self) -> None:
        trials = [_trial("baseline", passed=True) for _ in range(3)]
        r = aggregate_arm("baseline", trials)
        assert r.decisive == 3
        assert r.pass_rate == 1.0
        assert r.pass_at_k == 1.0
        assert r.pass_caret_k == 1.0

    def test_all_fail(self) -> None:
        trials = [_trial("baseline", passed=False, score=0.0) for _ in range(3)]
        r = aggregate_arm("baseline", trials)
        assert r.decisive == 3
        assert r.pass_rate == 0.0
        assert r.pass_at_k == 0.0
        assert r.pass_caret_k == 0.0

    def test_mixed_pass_rate(self) -> None:
        trials = [
            _trial("candidate", passed=True),
            _trial("candidate", passed=False, score=0.0),
            _trial("candidate", passed=True),
        ]
        r = aggregate_arm("candidate", trials)
        assert r.decisive == 3
        assert r.pass_rate == pytest.approx(2 / 3)
        assert r.pass_at_k == 1.0
        assert r.pass_caret_k == 0.0

    def test_no_decision_excluded_from_decisive(self) -> None:
        trials = [
            _trial("candidate", passed=True),
            _trial("candidate", passed=False, no_decision=True),
            _trial("candidate", passed=True),
        ]
        r = aggregate_arm("candidate", trials)
        # 2 decisive, both pass
        assert r.decisive == 2
        assert r.pass_rate == 1.0
        assert r.pass_caret_k == 1.0

    def test_all_no_decision(self) -> None:
        trials = [_trial("candidate", passed=False, no_decision=True) for _ in range(3)]
        r = aggregate_arm("candidate", trials)
        assert r.decisive == 0
        assert r.pass_rate == 0.0

    def test_error_excluded_from_decisive(self) -> None:
        trials = [
            _trial("candidate", passed=True),
            _trial("candidate", passed=False, error="timeout"),
        ]
        r = aggregate_arm("candidate", trials)
        assert r.decisive == 1
        assert r.pass_rate == 1.0


class TestCompareArms:
    def test_candidate_win(self) -> None:
        baseline = ArmResults("baseline", [], 3, 0.3, 1.0, 0.0, 0.3)
        candidate = ArmResults("candidate", [], 3, 0.7, 1.0, 0.0, 0.7)
        assert compare_arms(baseline, candidate) == "candidate_win"

    def test_baseline_win(self) -> None:
        baseline = ArmResults("baseline", [], 3, 0.9, 1.0, 0.0, 0.9)
        candidate = ArmResults("candidate", [], 3, 0.4, 1.0, 0.0, 0.4)
        assert compare_arms(baseline, candidate) == "baseline_win"

    def test_tie(self) -> None:
        baseline = ArmResults("baseline", [], 3, 0.5, 1.0, 0.0, 0.5)
        candidate = ArmResults("candidate", [], 3, 0.5, 1.0, 0.0, 0.5)
        assert compare_arms(baseline, candidate) == "tie"

    def test_no_decisive_baseline(self) -> None:
        baseline = ArmResults("baseline", [], 0, 0.0, 0.0, 0.0, 0.0)
        candidate = ArmResults("candidate", [], 3, 1.0, 1.0, 1.0, 1.0)
        assert compare_arms(baseline, candidate) == "no_decision"

    def test_epsilon_tightens_win_threshold(self) -> None:
        baseline = ArmResults("baseline", [], 3, 0.5, 1.0, 0.0, 0.5)
        candidate = ArmResults("candidate", [], 3, 0.55, 1.0, 0.0, 0.55)
        assert compare_arms(baseline, candidate) == "candidate_win"  # eps=0
        assert compare_arms(baseline, candidate, epsilon=0.1) == "tie"


class TestAggregateSubset:
    def test_empty(self) -> None:
        r = aggregate_subset([])
        assert r.count == 0
        assert r.win_rate == 0.0

    def test_all_candidate_wins(self) -> None:
        scenarios = [
            _scenario_result("a", "unit", outcome="candidate_win"),
            _scenario_result("b", "unit", outcome="candidate_win"),
        ]
        r = aggregate_subset(scenarios)
        assert r.count == 2
        assert r.win_rate == 1.0
        assert r.no_decision_rate == 0.0

    def test_mixed_outcomes(self) -> None:
        scenarios = [
            _scenario_result("a", "unit", outcome="candidate_win"),
            _scenario_result("b", "unit", outcome="baseline_win"),
            _scenario_result("c", "unit", outcome="tie"),
            _scenario_result("d", "unit", outcome="no_decision"),
        ]
        r = aggregate_subset(scenarios)
        assert r.count == 4
        assert r.win_rate == 0.25
        assert r.no_decision_rate == 0.25

    def test_pass_rate_weighting(self) -> None:
        scenarios = [
            _scenario_result(
                "a", "unit", baseline_pass_rate=0.0, candidate_pass_rate=1.0
            ),
            _scenario_result(
                "b", "unit", baseline_pass_rate=1.0, candidate_pass_rate=1.0
            ),
        ]
        r = aggregate_subset(scenarios)
        # mean(0.0, 1.0) = 0.5 baseline; mean(1.0, 1.0) = 1.0 candidate
        assert r.baseline_pass_rate == 0.5
        assert r.candidate_pass_rate == 1.0


class TestGroupBy:
    def test_group_by_level(self) -> None:
        scenarios = [
            _scenario_result("a", "unit"),
            _scenario_result("b", "unit"),
            _scenario_result("c", "trajectory"),
            _scenario_result("d", "e2e"),
        ]
        groups = group_by_level(scenarios)
        assert set(groups.keys()) == {"unit", "trajectory", "e2e"}
        assert groups["unit"].count == 2
        assert groups["trajectory"].count == 1
        assert groups["e2e"].count == 1

    def test_group_by_tag_overlap(self) -> None:
        scenarios = [
            _scenario_result("a", "unit", tags=["security", "easy"]),
            _scenario_result("b", "unit", tags=["security"]),
            _scenario_result("c", "unit", tags=["easy"]),
        ]
        groups = group_by_tag(scenarios)
        assert groups["security"].count == 2
        assert groups["easy"].count == 2


# =============================================================================
# Models — to_dict round-trips
# =============================================================================


class TestModelSerialization:
    def test_eval_results_to_dict_is_json_serializable(self) -> None:
        results = EvalResults(
            suite_path="suite.yaml",
            baseline_resource="b.md",
            candidate_resource="c.md",
            timestamp="2026-05-08T00:00:00+00:00",
            scenarios=[_scenario_result("a", "unit")],
            win_rate=1.0,
            baseline_pass_rate=0.5,
            candidate_pass_rate=1.0,
            no_decision_rate=0.0,
            held_out=None,
            by_level={
                "unit": SubsetStats(
                    count=1,
                    win_rate=1.0,
                    baseline_pass_rate=0.5,
                    candidate_pass_rate=1.0,
                    no_decision_rate=0.0,
                )
            },
            by_tag={},
            total_tokens=200,
        )
        as_dict = results.to_dict()
        # Must round-trip through JSON without TypeError
        json.dumps(as_dict)
        assert as_dict["win_rate"] == 1.0
        assert as_dict["scenarios"][0]["scenario_id"] == "a"


# =============================================================================
# Runner — mocked _invoke_from_resource
# =============================================================================


@dataclass
class _MockText:
    text: str
    type: str = "text"


def _make_assistant(text: str) -> Any:
    cls = type("AssistantMessage", (), {})
    instance = cls()
    instance.content = [_MockText(text)]
    return instance


def _make_result(num_turns: int = 1) -> Any:
    cls = type("ResultMessage", (), {})
    instance = cls()
    instance.content = None
    instance.num_turns = num_turns
    instance.usage = type("U", (), {"input_tokens": 50, "output_tokens": 50})()
    instance.is_error = False
    return instance


class _StubHarness(EvalHarness):
    """Override _invoke_from_resource to yield canned messages.

    The mapping is keyed on the resource basename so a single harness
    instance can serve baseline + candidate with different responses.
    """

    def __init__(self, responses: dict[str, str]) -> None:
        super().__init__()
        self.responses = responses
        self.invocations: list[tuple[str, str]] = []  # (resource_name, prompt)

    async def _invoke_from_resource(  # type: ignore[override]
        self,
        resource: Path,
        prompt: str,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> AsyncIterator[Any]:
        self.invocations.append((resource.name, prompt))
        text = self.responses.get(resource.name, "")
        yield _make_assistant(text)
        yield _make_result()


class _RaisingHarness(EvalHarness):
    """Always raises on invocation — used to exercise error → no_decision path."""

    async def _invoke_from_resource(  # type: ignore[override]
        self,
        resource: Path,
        prompt: str,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> AsyncIterator[Any]:
        raise RuntimeError("simulated SDK failure")
        yield  # pragma: no cover — needed for AsyncIterator type


class TestEvalHarnessRunner:
    @pytest.mark.asyncio
    async def test_two_arm_run_baseline_loses(
        self,
        tmp_path: Path,
        minimal_suite_doc: dict,
    ) -> None:
        # Suite expects "hello"; baseline says nothing, candidate says "hello world".
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")

        harness = _StubHarness(
            responses={"example-v0.md": "goodbye", "example-v1.md": "hello world"}
        )
        results = await harness.run(suite_path, baseline, candidate)

        assert results.win_rate == 1.0
        assert len(results.scenarios) == 1
        assert results.scenarios[0].outcome == "candidate_win"
        # Both arms ran (F12: arms execute concurrently — order is
        # not guaranteed).  F13: filenames are the canonical -v0 / -v1.
        assert set(harness.invocations) == {
            ("example-v0.md", "Say hello."),
            ("example-v1.md", "Say hello."),
        }

    @pytest.mark.asyncio
    async def test_baseline_wins_when_candidate_regresses(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        harness = _StubHarness(
            responses={"example-v0.md": "hello yes", "example-v1.md": "no greeting"}
        )
        results = await harness.run(suite_path, baseline, candidate)
        assert results.scenarios[0].outcome == "baseline_win"
        assert results.win_rate == 0.0

    @pytest.mark.asyncio
    async def test_tie_when_both_pass(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        harness = _StubHarness(
            responses={"example-v0.md": "hello", "example-v1.md": "hello"}
        )
        results = await harness.run(suite_path, baseline, candidate)
        assert results.scenarios[0].outcome == "tie"
        assert results.win_rate == 0.0

    @pytest.mark.asyncio
    async def test_runtime_error_becomes_no_decision(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        harness = _RaisingHarness()
        results = await harness.run(suite_path, baseline, candidate)
        # Both arms errored → no decisive trials → outcome is no_decision.
        assert results.scenarios[0].outcome == "no_decision"
        assert results.no_decision_rate == 1.0

    @pytest.mark.asyncio
    async def test_setup_files_materialized(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        # Add a setup file the candidate "reads" (we'll verify via grader on stub output).
        minimal_suite_doc["scenarios"][0]["setup"] = {
            "files": [{"path": "data.txt", "content": "secret-marker"}],
        }
        # Use a code-grader that asserts the cwd had data.txt with the right content.
        # Since we stub _invoke_from_resource, we instead verify materialization by
        # overriding _invoke_from_resource to inspect cwd contents.
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")

        observed_cwds: list[Path] = []

        class _ObservingHarness(EvalHarness):
            async def _invoke_from_resource(  # type: ignore[override]
                self, resource, prompt, cwd, env=None
            ):
                observed_cwds.append(cwd)
                # Verify the setup file is on disk inside cwd at invocation time.
                expected = cwd / "data.txt"
                assert expected.exists(), f"setup file missing: {expected}"
                assert expected.read_text() == "secret-marker"
                yield _make_assistant("hello")
                yield _make_result()

        harness = _ObservingHarness()
        await harness.run(suite_path, baseline, candidate)
        # 1 scenario × 2 arms × 1 trial = 2 invocations.
        assert len(observed_cwds) == 2
        # Each cwd is a distinct tempdir.
        assert observed_cwds[0] != observed_cwds[1]

    @pytest.mark.asyncio
    async def test_writes_results_when_dir_provided(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        results_dir = tmp_path / "results"
        harness = _StubHarness(
            responses={"example-v0.md": "x", "example-v1.md": "hello"}
        )
        await harness.run(suite_path, baseline, candidate, results_dir=results_dir)
        out = results_dir / "eval-results.json"
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["win_rate"] == 1.0
        assert len(loaded["scenarios"]) == 1

    @pytest.mark.asyncio
    async def test_held_out_subset_isolated(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        # Two scenarios: one held out, one not.
        minimal_suite_doc["scenarios"] = [
            {
                "id": "open-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
                "held_out": False,
            },
            {
                "id": "held-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
                "held_out": True,
            },
        ]
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        harness = _StubHarness(
            responses={"example-v0.md": "no", "example-v1.md": "hello"}
        )
        results = await harness.run(suite_path, baseline, candidate)
        # Both scenarios should show candidate_win.
        assert results.win_rate == 1.0
        # held_out subset present and isolated.
        assert results.held_out is not None
        assert results.held_out.count == 1
        assert results.held_out.win_rate == 1.0

    @pytest.mark.asyncio
    async def test_per_level_rollups(
        self, tmp_path: Path, minimal_suite_doc: dict
    ) -> None:
        minimal_suite_doc["scenarios"] = [
            {
                "id": "u-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
            },
            {
                "id": "e-1",
                "level": "e2e",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
            },
        ]
        suite_path = _write_yaml(tmp_path, minimal_suite_doc)
        baseline = _write_resource(tmp_path, "baseline")
        candidate = _write_resource(tmp_path, "candidate")
        harness = _StubHarness(
            responses={"example-v0.md": "no", "example-v1.md": "hello"}
        )
        results = await harness.run(suite_path, baseline, candidate)
        assert "unit" in results.by_level
        assert "e2e" in results.by_level
        assert results.by_level["unit"].count == 1
        assert results.by_level["e2e"].count == 1

    def test_unsupported_runtime_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            EvalHarness(runtime="ephemeral_container")  # type: ignore[arg-type]


# =============================================================================
# F19 — Per-level trial timeout
# =============================================================================


class TestPerLevelTrialTimeout:
    """F19: ``_resolve_trial_timeout`` returns 180s for unit / e2e and
    300s for trajectory by default, with env-var overrides per level."""

    def test_trial_timeout_default_180_for_unit_and_e2e(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from harness.optimization.eval_harness.runner import (
            _resolve_trial_timeout,
        )

        # Make sure no env vars are set.
        monkeypatch.delenv("CGF_EVAL_TRIAL_TIMEOUT", raising=False)
        monkeypatch.delenv("CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT", raising=False)

        # suite_default=300 (a typical pre-F19 value); the F19 default of
        # 180 is tighter and should win for unit / e2e.
        assert _resolve_trial_timeout("unit", suite_default=300) == 180
        assert _resolve_trial_timeout("e2e", suite_default=300) == 180

    def test_trial_timeout_300_for_trajectory_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from harness.optimization.eval_harness.runner import (
            _resolve_trial_timeout,
        )

        monkeypatch.delenv("CGF_EVAL_TRIAL_TIMEOUT", raising=False)
        monkeypatch.delenv("CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT", raising=False)

        # Trajectory needs more wall time than unit/e2e.
        assert _resolve_trial_timeout("trajectory", suite_default=300) == 300

    def test_env_vars_override_per_level_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from harness.optimization.eval_harness.runner import (
            _resolve_trial_timeout,
        )

        monkeypatch.setenv("CGF_EVAL_TRIAL_TIMEOUT", "90")
        monkeypatch.setenv("CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT", "600")

        assert _resolve_trial_timeout("unit", suite_default=300) == 90
        assert _resolve_trial_timeout("e2e", suite_default=300) == 90
        assert _resolve_trial_timeout("trajectory", suite_default=300) == 600

    def test_invalid_env_var_falls_back_to_module_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from harness.optimization.eval_harness.runner import (
            _resolve_trial_timeout,
        )

        monkeypatch.setenv("CGF_EVAL_TRIAL_TIMEOUT", "not-a-number")
        monkeypatch.setenv("CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT", "-5")

        # Bad values silently ignored — both fall back to the F19 default.
        assert _resolve_trial_timeout("unit", suite_default=300) == 180
        assert _resolve_trial_timeout("trajectory", suite_default=300) == 300

    def test_tighter_suite_default_wins_over_module_builtin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A suite that explicitly sets a tighter timeout than the F19
        default should be respected — operator intent is preserved."""
        from harness.optimization.eval_harness.runner import (
            _resolve_trial_timeout,
        )

        monkeypatch.delenv("CGF_EVAL_TRIAL_TIMEOUT", raising=False)
        monkeypatch.delenv("CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT", raising=False)

        # Suite explicitly wants 60s — that's tighter than F19's 180s.
        assert _resolve_trial_timeout("unit", suite_default=60) == 60
