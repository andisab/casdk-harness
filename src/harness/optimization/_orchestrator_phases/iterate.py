"""ITERATE phase implementation.

Delegates to the ``cgf-prompt-optimizer`` agent (one or more iterations
per resource).  Parses ``[ITERATE_COMPLETE:{path}]`` and quality scores;
loops until quality crosses the configured threshold or
``max_iterations`` is reached.  Maintains a multi-resource CHANGELOG of
quality deltas.

Phase F4: per-resource iteration runs in parallel under an
``asyncio.Semaphore`` bounded by ``CGF_ITERATE_CONCURRENCY`` (default
4).  The inner iteration while-loop (1..N rounds for a single resource)
stays sequential within each coroutine — only the outer fan-out across
resources is parallel.  State and CHANGELOG writes use
``self._state_lock``.

Functions mounted onto :class:`MultiResourceOrchestrator` as:

- ``_delegate_iteration`` ← :func:`delegate`
- ``_evaluate_resource_quality`` ← :func:`evaluate_resource_quality`
- ``_evaluate_resource_quality_full`` ← :func:`evaluate_resource_quality_full`
- ``_parse_iteration_result`` ← :func:`parse_iteration_result`
- ``_create_changelog_header`` ← :func:`create_changelog_header`
- ``_format_iteration_entry`` ← :func:`format_iteration_entry`
- ``_insert_changelog_entry`` ← :func:`insert_changelog_entry`
- ``_update_changelog`` ← :func:`update_changelog`
- ``_get_word_count`` ← :func:`get_word_count`
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from harness.monitoring import record_iteration
from harness.optimization._orchestrator_helpers import (
    AGENT_ITERATE,
    validate_write_path,
    versioned_path,
)
from harness.optimization.protocols.signals import SignalType
from harness.progress import ResourceQuality, ResourceStatus

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)

DEFAULT_ITERATE_CONCURRENCY = 4


def _resolve_concurrency(env_var: str, default: int) -> int:
    """Read an integer concurrency knob from the environment.

    Mirrors :func:`generate._resolve_concurrency` to avoid a cross-phase
    import (these modules are otherwise independent).
    """
    raw = os.environ.get(env_var)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate resource iteration to cgf-prompt-optimizer agent.

    Phase F4: dispatches per-resource iteration coroutines in parallel
    under a semaphore.  Each coroutine runs its own iteration while-loop
    sequentially (state of iter N depends on iter N-1).  Per-resource
    exceptions stay confined to their own coroutine.
    """
    if not self._state or not self._spec:
        return

    # Get resources that need optimization
    resources_to_optimize = (
        self._state.get_generated_resources()
        + self._state.get_needs_refinement_resources()
    )

    concurrency = _resolve_concurrency(
        "CGF_ITERATE_CONCURRENCY", DEFAULT_ITERATE_CONCURRENCY
    )

    logger.info(
        "ITERATE: Starting optimization",
        total=len(resources_to_optimize),
        threshold=self.config.quality_threshold,
        concurrency=concurrency,
    )

    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(resource: ResourceStatus) -> None:
        async with semaphore:
            try:
                await _iterate_single_resource(self, resource)
            except Exception as exc:  # noqa: BLE001 — isolate per-resource
                logger.error(
                    "ITERATE: Unhandled exception in resource coroutine",
                    path=resource.path,
                    error=str(exc)[:300],
                )
                try:
                    async with self._state_lock:
                        self._state.update_resource(
                            resource.path,
                            status="failed",
                            error=f"Unhandled exception: {exc}",
                        )
                        self._save_state()
                except Exception:  # noqa: BLE001 — defensive
                    pass

    if resources_to_optimize:
        await asyncio.gather(
            *[_bounded(r) for r in resources_to_optimize]
        )

    logger.info(
        "ITERATE: Complete",
        optimized=len(self._state.get_optimized_resources()),
        needs_refinement=len(self._state.get_needs_refinement_resources()),
        failed=len(self._state.get_failed_resources()),
    )


async def _iterate_single_resource(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
) -> None:
    """Run the inner iteration loop for one resource.

    Extracted from :func:`delegate` so the outer dispatch can fan out
    across resources.  All state and CHANGELOG writes go through
    ``self._state_lock``; the inner loop itself stays sequential because
    iteration N consumes the output of iteration N-1.
    """
    if not self._state or not self._spec:
        return

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir

    # Guard: skip resources with no file (e.g. failed generation)
    if resource.version == 0:
        resource_file = workspace / resource.path
        if not resource_file.exists():
            logger.warning(
                "ITERATE: Skipping - no file exists",
                path=resource.path,
            )
            async with self._state_lock:
                self._state.update_resource(
                    resource.path,
                    status="failed",
                    error="No file available for optimization",
                )
                self._save_state()
            return

    async with self._state_lock:
        self._state.update_resource(resource.path, status="in_progress")
        self._save_state()

    iteration = 0
    current_quality = 0.0

    while iteration < self.config.max_iterations:
        iteration += 1

        # Surface per-resource iteration to Prometheus (Grafana D70 /
        # D00 iteration panels).  Multi-resource path historically
        # didn't emit this — see OBSERVABILITY.md § 3.4 (resolved 2026-05-14).
        record_iteration(resource.path, iteration)

        # Phase A.5: include eval feedback when this resource was
        # flagged for refinement by EXECUTION_EVAL on a prior round.
        feedback_block = _build_feedback_block(
            self._state.feedback_history, resource.path
        )

        # Build prompt for optimizer
        prompt = f"""Optimize resource for multi-resource plugin.

Workspace: {workspace}
Resource: {workspace / resource.path}
Resource type: {resource.resource_type}
Iteration: {iteration}/{self.config.max_iterations}
Quality threshold: {self.config.quality_threshold}

Plugin context:
- Name: {self._spec.name}
- Purpose: {self._spec.purpose}
{feedback_block}
Run agentic optimization (default mode).
Load eval_criteria from research/eval_criteria.yaml if available.
Apply research heuristics and self-critique.

Save optimized version to:
{workspace / versioned_path(resource.path, resource.version + 1)}

DO NOT write any sessions/*.summary.json file — Python writes the canonical
machine-readable summary from the signals below.  Your job is the resource
file plus the signals; the JSON is generated for you.

When complete, emit signals:
[ITERATE_COMPLETE:{resource.path}]
version: {resource.version + 1}
quality_overall: {{0.0-1.0}}
quality_completeness: {{0.0-1.0}}
quality_accuracy: {{0.0-1.0}}
quality_clarity: {{0.0-1.0}}
word_count: {{count}}
[SUMMARY]
{{1-2 sentence prose summary of what changed and why}}
[/SUMMARY]
[KEY_IMPROVEMENTS]
- {{bullet point: one concrete improvement}}
- {{bullet point: another}}
- {{...up to ~7 bullets, brief — these surface in the per-resource report}}
[/KEY_IMPROVEMENTS]
"""

        logger.info(
            "ITERATE: Running iteration",
            path=resource.path,
            iteration=iteration,
            timeout=self.config.iterate_timeout,
        )
        self._emit_progress(
            "ITERATE", resource.path, f"iteration {iteration}"
        )

        try:
            # Pass timeout directly to agent
            response = await call_agent_simple(
                AGENT_ITERATE,
                prompt,
                verbose=self.config.verbose or self.config.follow_logs,
                timeout=float(self.config.iterate_timeout),
            )

            # Parse signal and quality
            iter_signals = self._signal_parser.parse(response)
            iter_complete = [
                s for s in iter_signals
                if s.type == SignalType.ITERATE_COMPLETE
                and s.resource_path == resource.path
            ]
            if iter_complete:
                # Parse iteration result
                result = self._parse_iteration_result(response)

                # Get quality score with all dimensions
                quality_full = None
                if result["quality_overall"] is not None:
                    current_quality = result["quality_overall"]
                else:
                    # Fallback: use evaluator for full quality
                    quality_full = await self._evaluate_resource_quality_full(
                        resource
                    )
                    current_quality = (
                        quality_full.overall if quality_full else 0.0
                    )

                # Get word counts for CHANGELOG
                original_path = workspace / resource.path
                word_count_before = self._get_word_count(original_path)
                word_count_after = (
                    result["word_count"]
                    if result["word_count"]
                    else word_count_before
                )

                # Get quality before this iteration
                quality_before = (
                    resource.quality.overall if resource.quality else 0.0
                )

                # CHANGELOG writes touch shared on-disk state — serialize.
                async with self._state_lock:
                    self._update_changelog(
                        resource=resource,
                        iteration=iteration,
                        quality_before=quality_before,
                        quality_after=current_quality,
                        word_count_before=word_count_before,
                        word_count_after=word_count_after,
                        summary=result["summary"] or "",
                    )

                # Update state with full quality dimensions
                if quality_full:
                    quality = quality_full
                else:
                    quality = ResourceQuality(
                        overall=current_quality,
                        completeness=result.get(
                            "quality_completeness", 0.0
                        ),
                        accuracy=result.get("quality_accuracy", 0.0),
                        clarity=result.get("quality_clarity", 0.0),
                    )
                # Capture new version BEFORE update_resource, which mutates
                # resource.version in-place (progress.py:1007).  Without
                # this, the summary path would silently double-bump.
                new_version = resource.version + 1
                async with self._state_lock:
                    self._state.update_resource(
                        resource.path,
                        version=new_version,
                        iterations=iteration,
                        quality=quality,
                    )
                    self._save_state()

                # Python owns the canonical summary.json — agent contributes
                # only the narrative via [SUMMARY] / [KEY_IMPROVEMENTS]
                # signals (now embedded in `result`).
                self._write_summary_json(
                    resource=resource,
                    version=new_version,
                    parsed=result,
                    quality=quality,
                    iteration=iteration,
                    word_count=word_count_after,
                )

                logger.info(
                    "ITERATE: Iteration complete",
                    path=resource.path,
                    iteration=iteration,
                    quality=f"{current_quality:.2f}",
                )

                # Check threshold
                if current_quality >= self.config.quality_threshold:
                    async with self._state_lock:
                        self._state.update_resource(
                            resource.path, status="optimized"
                        )
                        # Immediately finalize this resource
                        self._finalize_single_resource(resource.path)
                    logger.info(
                        "ITERATE: Resource meets threshold",
                        path=resource.path,
                        quality=f"{current_quality:.2f}",
                    )
                    self._emit_progress(
                        "ITERATE",
                        resource.path,
                        "complete",
                        current_quality,
                    )
                    break

            else:
                # Fallback: check if versioned file was created
                versioned_file = workspace / versioned_path(
                    resource.path, resource.version + 1
                )
                if versioned_file.exists():
                    # File exists - use evaluator for full quality
                    fallback_quality = (
                        await self._evaluate_resource_quality_full(resource)
                    )
                    current_quality = (
                        fallback_quality.overall if fallback_quality else 0.0
                    )

                    if current_quality > 0:
                        quality = (
                            fallback_quality
                            if fallback_quality
                            else ResourceQuality(overall=current_quality)
                        )
                        # Capture new version BEFORE update_resource — see
                        # the signal-branch comment above for the rationale.
                        new_version = resource.version + 1
                        async with self._state_lock:
                            self._state.update_resource(
                                resource.path,
                                version=new_version,
                                iterations=iteration,
                                quality=quality,
                            )
                            self._save_state()

                        # Signal-less fallback: agent didn't emit narrative,
                        # but the resource file exists.  Still write the
                        # canonical summary so the report has metrics.
                        fallback_words = self._get_word_count(versioned_file)
                        self._write_summary_json(
                            resource=resource,
                            version=new_version,
                            parsed={},
                            quality=quality,
                            iteration=iteration,
                            word_count=fallback_words,
                        )

                        logger.info(
                            "ITERATE: File created (no signal)",
                            path=resource.path,
                            quality=f"{current_quality:.2f}",
                        )

                        if current_quality >= self.config.quality_threshold:
                            async with self._state_lock:
                                self._state.update_resource(
                                    resource.path, status="optimized"
                                )
                                # Immediately finalize this resource
                                self._finalize_single_resource(resource.path)
                            break
                else:
                    logger.warning(
                        "ITERATE: No completion signal or file",
                        path=resource.path,
                        iteration=iteration,
                    )

        except TimeoutError:
            logger.error(
                "ITERATE: Iteration timed out",
                path=resource.path,
                iteration=iteration,
                timeout=self.config.iterate_timeout,
            )
            self._emit_progress(
                "ITERATE", resource.path,
                f"iteration {iteration} timeout"
            )
            break
        except Exception as e:
            logger.error(
                "ITERATE: Iteration failed",
                path=resource.path,
                iteration=iteration,
                error=str(e),
            )
            break

    # Final status if not already optimized
    async with self._state_lock:
        if self._state.resources[resource.path].status != "optimized":
            if current_quality > 0:
                self._state.update_resource(
                    resource.path, status="needs_refinement"
                )
            else:
                self._state.update_resource(
                    resource.path,
                    status="failed",
                    error="Optimization failed to produce quality score",
                )

        self._save_state()


async def evaluate_resource_quality(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
) -> float:
    """Evaluate resource quality using the quality evaluator.

    Args:
        resource: Resource to evaluate.

    Returns:
        Quality score (0.0-1.0).
    """
    quality = await self._evaluate_resource_quality_full(resource)
    return quality.overall if quality else 0.0


async def evaluate_resource_quality_full(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
) -> ResourceQuality | None:
    """Evaluate resource quality and return full dimension scores.

    Args:
        resource: Resource to evaluate.

    Returns:
        ResourceQuality with all dimension scores, or None on failure.
    """
    if not self._evaluator or not self._spec:
        return None

    workspace = self.config.workspace_dir

    # Find latest version - preserve parent directory structure
    version = resource.version
    if version > 0:
        path = workspace / versioned_path(resource.path, version)
    else:
        path = workspace / resource.path

    if not path.exists():
        return None

    content = path.read_text()

    score = await self._evaluator.evaluate(
        resource_content=content,
        resource_type=resource.resource_type,
        spec=self._spec,
        resource_name=Path(resource.path).stem,
    )

    # Map QualityScore to ResourceQuality
    return ResourceQuality(
        completeness=score.completeness,
        accuracy=score.accuracy,
        clarity=score.clarity,
        overall=score.overall,
    )


# ---------------------------------------------------------------------------
# CHANGELOG management
# ---------------------------------------------------------------------------


def parse_iteration_result(
    self: MultiResourceOrchestrator,
    response: str,
) -> dict[str, Any]:
    """Parse agent response for quality, word count, and summary.

    Args:
        response: Raw response from cgf-prompt-optimizer agent.

    Returns:
        Dict with keys: quality_overall, word_count, summary
    """
    result: dict[str, Any] = {
        "quality_overall": None,
        "word_count": None,
        "summary": None,
        "key_improvements": [],
    }

    # Extract quality_overall: X.XX (multiple patterns for permissiveness)
    quality_patterns = [
        r"quality_overall:\s*([\d.]+)",
        r"quality:\s*([\d.]+)",
        r"overall[_\s]?score:\s*([\d.]+)",
        r"score:\s*([\d.]+)",
    ]
    for pattern in quality_patterns:
        quality_match = re.search(pattern, response, re.IGNORECASE)
        if quality_match:
            val = float(quality_match.group(1))
            # Ensure it's a valid quality score (0.0-1.0)
            if 0.0 <= val <= 1.0:
                result["quality_overall"] = val
                break

    # Extract dimension scores (completeness, accuracy, clarity)
    for dim in ["completeness", "accuracy", "clarity"]:
        for pattern in [
            rf"quality_{dim}:\s*([\d.]+)",
            rf"{dim}:\s*([\d.]+)",
        ]:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                val = float(match.group(1))
                if 0.0 <= val <= 1.0:
                    result[f"quality_{dim}"] = val
                    break

    # Extract word_count: XXX
    word_match = re.search(r"word_count:\s*(\d+)", response)
    if word_match:
        result["word_count"] = int(word_match.group(1))

    # Extract [SUMMARY]...[/SUMMARY]
    summary_match = re.search(
        r"\[SUMMARY\]\s*(.*?)\s*\[/SUMMARY\]", response, re.DOTALL
    )
    if summary_match:
        result["summary"] = summary_match.group(1).strip()

    # Extract [KEY_IMPROVEMENTS]...[/KEY_IMPROVEMENTS] as a bullet list.
    # Each non-empty line starting with `-`, `*`, or a digit is one bullet;
    # leading marker + whitespace is stripped.  Empty block → empty list.
    improvements_match = re.search(
        r"\[KEY_IMPROVEMENTS\]\s*(.*?)\s*\[/KEY_IMPROVEMENTS\]",
        response,
        re.DOTALL,
    )
    if improvements_match:
        block = improvements_match.group(1)
        bullets: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^[\-\*•]\s+", "", line)
            line = re.sub(r"^\d+[\.\)]\s+", "", line)
            if line:
                bullets.append(line)
        result["key_improvements"] = bullets

    return result


def canonical_summary_path(resource_path: str, version: int) -> Path:
    """Canonical location for the per-version ``*.summary.json``.

    Mirrors :func:`versioned_path` for the resource file: for a resource at
    ``{parent}/{name}.md`` v``N``, the summary lives at
    ``{parent}/sessions/{name}-v{N}.summary.json``.  Matches what most agents
    historically emit and what the renderer's
    ``workspace_root.glob("**/sessions/*.summary.json")`` picks up.

    Returns a relative path.  The caller is responsible for resolving against
    the workspace root and validating with :func:`validate_write_path`.
    """
    versioned = versioned_path(resource_path, version)
    return versioned.parent / "sessions" / f"{versioned.stem}.summary.json"


def write_summary_json(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
    version: int,
    parsed: dict[str, Any],
    quality: ResourceQuality,
    iteration: int,
    word_count: int | None = None,
) -> None:
    """Write the canonical per-version summary file.

    The orchestrator owns this file (Python writes it, not the agent).
    The schema is fixed; the agent contributes only the narrative fields
    (``summary`` prose + ``key_improvements`` bullets), both parsed from
    signal blocks in the agent response by :func:`parse_iteration_result`.

    Best-effort: any I/O or path-validation failure is logged and
    swallowed so iteration progress is never blocked by a summary write
    going wrong.
    """
    if not self.config or not self.config.workspace_dir:
        return

    workspace = self.config.workspace_dir
    rel_path = canonical_summary_path(resource.path, version)
    target = workspace / rel_path

    try:
        validate_write_path(target, workspace)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning(
            "SUMMARY_JSON: refusing to write outside workspace",
            path=str(target),
            error=str(exc),
        )
        return

    resource_id = Path(resource.path).stem
    if resource_id == "SKILL":  # skill resources: use parent dir name
        resource_id = Path(resource.path).parent.name or resource_id

    versioned_resource = versioned_path(resource.path, version)
    payload: dict[str, Any] = {
        "resource_path": resource.path,
        "resource_id": resource_id,
        "version": version,
        "output_path": str(versioned_resource),
        "timestamp": datetime.now(UTC).isoformat(),
        "iteration": f"{iteration}/{self.config.max_iterations}",
        "iterations": iteration,
        "quality": {
            "overall": round(quality.overall, 4) if quality.overall else 0.0,
            "completeness": round(quality.completeness, 4)
            if quality.completeness
            else 0.0,
            "accuracy": round(quality.accuracy, 4) if quality.accuracy else 0.0,
            "clarity": round(quality.clarity, 4) if quality.clarity else 0.0,
        },
        "word_count": word_count if word_count is not None else 0,
        "summary": parsed.get("summary") or "",
        "key_improvements": list(parsed.get("key_improvements") or []),
        "_written_by": "orchestrator",
    }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        logger.info(
            "SUMMARY_JSON: wrote summary",
            path=str(target),
            version=version,
        )
    except OSError as exc:
        logger.warning(
            "SUMMARY_JSON: failed to write",
            path=str(target),
            error=str(exc),
        )
        return

    # I8 — defensive cleanup: remove any stray summary files the agent
    # wrote despite the system prompt forbidding it.  Run #7 surfaced two
    # naming conventions coexisting in the same workspace (Python's
    # ``{stem}-v{N}.summary.json`` and agent-emitted
    # ``{slug}-v{N}.summary.json``), which broke ``sessions/`` cleanup
    # semantics and the run-report glob.  Keep only the canonical one.
    try:
        sessions_dir = target.parent
        canonical_name = target.name
        for stray in sessions_dir.glob(f"*-v{version}.summary.json"):
            if stray.name == canonical_name:
                continue
            try:
                stray.unlink()
                logger.info(
                    "SUMMARY_JSON: removed stray agent-written summary",
                    canonical=str(target),
                    stray=str(stray),
                )
            except OSError as exc:
                logger.warning(
                    "SUMMARY_JSON: could not remove stray summary",
                    path=str(stray),
                    error=str(exc),
                )
    except OSError as exc:  # noqa: BLE001 — glob failure must not block
        logger.debug(
            "SUMMARY_JSON: stray-cleanup glob failed",
            sessions_dir=str(target.parent),
            error=str(exc),
        )


def create_changelog_header(
    self: MultiResourceOrchestrator,
    changelog_path: Path,
) -> None:
    """Create CHANGELOG.md with header.

    Args:
        changelog_path: Path to write CHANGELOG.md
    """
    if not self._spec:
        return

    # Determine resource counts from state
    resource_counts: dict[str, int] = {}
    if self._state:
        for resource in self._state.resources.values():
            rtype = resource.resource_type
            resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

    counts_str = ", ".join(
        f"{count} {rtype}{'s' if count > 1 else ''}"
        for rtype, count in sorted(resource_counts.items())
    )

    header = f"""# CGF Optimization Changelog: {self._spec.name}

**Plugin:** {self._spec.name}
**Resources:** {counts_str or 'TBD'}
**Mode:** agentic
**Started:** {datetime.now(UTC).strftime('%Y-%m-%d')}
**Status:** IN_PROGRESS

---
"""
    # Validate path
    validate_write_path(changelog_path, self.config.workspace_dir)

    changelog_path.write_text(header)
    logger.info("CHANGELOG: Created", path=str(changelog_path))


def format_iteration_entry(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
    iteration: int,
    quality_before: float,
    quality_after: float,
    word_count_before: int,
    word_count_after: int,
    summary: str,
) -> str:
    """Format a single iteration entry for CHANGELOG.

    Args:
        resource: The resource being optimized
        iteration: Iteration number
        quality_before: Quality score before this iteration
        quality_after: Quality score after this iteration
        word_count_before: Word count before
        word_count_after: Word count after
        summary: Summary of changes from agent

    Returns:
        Formatted markdown entry
    """
    # Calculate deltas
    quality_delta = quality_after - quality_before
    quality_pct = (
        f"+{quality_delta * 100:.0f}%"
        if quality_delta >= 0
        else f"{quality_delta * 100:.0f}%"
    )

    word_delta = word_count_after - word_count_before
    word_pct = (
        f"+{(word_delta / word_count_before * 100):.0f}%"
        if word_count_before > 0
        else "N/A"
    )

    version = resource.version + 1
    versioned = versioned_path(resource.path, version)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    entry = f"""
### Iteration {iteration} ({date_str})

**Output:** {versioned}
**Quality:** {quality_before:.2f} → {quality_after:.2f} ({quality_pct})
**Words:** {word_count_before} → {word_count_after} ({word_pct})

#### Summary

{summary or 'No summary provided.'}

---
"""
    return entry


def insert_changelog_entry(
    self: MultiResourceOrchestrator,
    changelog_path: Path,
    resource_path: str,
    entry: str,
) -> None:
    """Insert entry into appropriate resource section of CHANGELOG.

    For multi-resource, organizes entries by resource path.

    Args:
        changelog_path: Path to CHANGELOG.md
        resource_path: Resource path for section header
        entry: Formatted iteration entry
    """
    content = changelog_path.read_text()

    # Resource section header
    section_header = f"## Resource: {resource_path}"

    if section_header in content:
        # Insert after section header (before first ### Iteration)
        section_start = content.index(section_header)
        after_header = section_start + len(section_header)
        # Find the next line after section header
        next_newline = content.find("\n", after_header)
        if next_newline == -1:
            next_newline = len(content)
        insert_pos = next_newline + 1
        content = content[:insert_pos] + entry + content[insert_pos:]
    else:
        # Create new resource section
        # Insert before first resource section or at end of header
        first_resource = content.find("\n## Resource:")
        if first_resource != -1:
            # Insert before existing resource sections
            insert_pos = first_resource + 1
        else:
            # Insert after header separator
            header_end = content.find("---\n")
            insert_pos = header_end + 4 if header_end != -1 else len(content)

        new_section = f"\n{section_header}\n{entry}"
        content = content[:insert_pos] + new_section + content[insert_pos:]

    # Validate path
    validate_write_path(changelog_path, self.config.workspace_dir)

    changelog_path.write_text(content)
    logger.info(
        "CHANGELOG: Entry added",
        resource=resource_path,
        path=str(changelog_path),
    )


def update_changelog(
    self: MultiResourceOrchestrator,
    resource: ResourceStatus,
    iteration: int,
    quality_before: float,
    quality_after: float,
    word_count_before: int,
    word_count_after: int,
    summary: str,
) -> None:
    """Update unified CHANGELOG.md with resource iteration entry.

    Creates header on first call. Appends to resource section on subsequent
    calls. For multi-resource, organizes entries by resource path.

    Args:
        resource: The resource being optimized
        iteration: Iteration number
        quality_before: Quality score before iteration
        quality_after: Quality score after iteration
        word_count_before: Word count before
        word_count_after: Word count after
        summary: Summary of improvements from agent
    """
    changelog_path = self.config.workspace_dir / "CHANGELOG.md"

    # Build iteration entry
    entry = self._format_iteration_entry(
        resource,
        iteration,
        quality_before,
        quality_after,
        word_count_before,
        word_count_after,
        summary,
    )

    if not changelog_path.exists():
        # Create with header
        self._create_changelog_header(changelog_path)

    # Insert entry into appropriate resource section
    self._insert_changelog_entry(changelog_path, resource.path, entry)


def get_word_count(
    self: MultiResourceOrchestrator,
    path: Path,
) -> int:
    """Get word count from a file.

    Args:
        path: Path to file

    Returns:
        Word count, or 0 if file doesn't exist
    """
    if not path.exists():
        return 0
    content = path.read_text()
    return len(content.split())


# ---------------------------------------------------------------------------
# Phase A.5 feedback injection
# ---------------------------------------------------------------------------


def _build_feedback_block(
    feedback_history: list[dict[str, Any]],
    resource_path: str,
) -> str:
    """Render an EXECUTION_EVAL feedback block for the optimizer prompt.

    Returns an empty string when there's no feedback for this resource;
    otherwise a markdown section describing which scenarios the previous
    candidate failed.  Held-out scenarios are excluded by the writer
    (:mod:`._orchestrator_phases.execution_eval`), so this function only
    sees scenarios safe to surface.
    """
    if not feedback_history:
        return ""

    # Collect entries for this specific resource, most-recent first.
    # I15: also propagate the gate verdict + cost-stage inputs so the
    # optimizer's verdict-branched refinement strategy can fire.
    entries: list[dict[str, Any]] = []
    for entry in feedback_history:
        for resource_entry in entry.get("regressions", []):
            if resource_entry.get("path") == resource_path:
                entries.append(
                    {
                        "feedback_iteration": entry.get(
                            "feedback_iteration", "?"
                        ),
                        "verdict": resource_entry.get("verdict", "refine"),
                        "candidate_pass_rate": resource_entry.get(
                            "candidate_pass_rate", 0.0
                        ),
                        "baseline_pass_rate": resource_entry.get(
                            "baseline_pass_rate", 0.0
                        ),
                        "floor_pass_rate": resource_entry.get("floor_pass_rate"),
                        "win_rate": resource_entry.get("win_rate", 0.0),
                        "baseline_cost_per_success": resource_entry.get(
                            "baseline_cost_per_success"
                        ),
                        "candidate_cost_per_success": resource_entry.get(
                            "candidate_cost_per_success"
                        ),
                        "cost_per_success_delta_pct": resource_entry.get(
                            "cost_per_success_delta_pct"
                        ),
                        "cost_tolerance": resource_entry.get("cost_tolerance"),
                        "effective_cost_tolerance": resource_entry.get(
                            "effective_cost_tolerance"
                        ),
                        "failing_scenarios": resource_entry.get(
                            "failing_scenarios", []
                        ),
                    }
                )

    if not entries:
        return ""

    # Use the most-recent entry — older ones are stale and would confuse.
    latest = entries[-1]
    failing = latest["failing_scenarios"][:8]  # cap to keep prompt bounded
    scenario_lines = "\n".join(
        f"  - {s.get('scenario_id', '?')} ({s.get('level', '?')}, "
        f"baseline {s.get('baseline_pass_rate', 0.0):.2f} → "
        f"candidate {s.get('candidate_pass_rate', 0.0):.2f}) — {s.get('outcome', '?')}"
        for s in failing
    )
    overflow = (
        f"  ... plus {len(latest['failing_scenarios']) - 8} more"
        if len(latest["failing_scenarios"]) > 8
        else ""
    )

    # I15: verdict-specific framing so the optimizer's verdict-branched
    # refinement strategy in cgf-prompt-optimizer.md can fire correctly.
    verdict = latest["verdict"]
    floor_pr = latest["floor_pass_rate"]
    b_cps = latest["baseline_cost_per_success"]
    c_cps = latest["candidate_cost_per_success"]
    cps_delta = latest["cost_per_success_delta_pct"]
    base_tau = latest["cost_tolerance"]
    eff_tau = latest["effective_cost_tolerance"]

    cost_block_lines: list[str] = []
    if b_cps is not None and c_cps is not None:
        cost_block_lines.append(
            f"  baseline cost-per-success:  ${b_cps:.4f}"
        )
        cost_block_lines.append(
            f"  candidate cost-per-success: ${c_cps:.4f}"
        )
        if cps_delta is not None:
            cost_block_lines.append(
                f"  cps delta:                  {cps_delta:+.1%}"
            )
        if base_tau is not None and eff_tau is not None:
            cost_block_lines.append(
                f"  cost tolerance (τ):         base {base_tau:.1%} → "
                f"effective {eff_tau:.1%} (after quality-bonus scaling)"
            )
    cost_block = "\n".join(cost_block_lines)
    floor_line = (
        f"  floor (bare-model) pass_rate: {floor_pr:.2f}"
        if floor_pr is not None
        else ""
    )

    # Verdict-specific action header — this is what the optimizer's
    # system-prompt CASE table keys off.
    verdict_actions = {
        "reject_floor": (
            "REJECTED — below floor.  The bare-model arm scored "
            "higher than your candidate.  Your prompt engineering "
            "is net-negative.\n"
            "Action: TRIM AGGRESSIVELY.  Remove rules / framing that "
            "boxes the agent in.  Question every constraint."
        ),
        "reject_cost": (
            "REJECTED — cost regression.  Quality matched the "
            "incumbent, but cost-per-success exceeded the cost-gate "
            "allowance.\n"
            "Action: TRIM TOKENS.  Cut verbose anti-pattern "
            "explanations, redundant examples, long preambles.  "
            "Target ≤ baseline word count.  Do NOT add new content "
            "unless it lifts quality enough to earn extra cost "
            "headroom (each +1pp quality grants ~+1% τ)."
        ),
        "refine": (
            "REFINEMENT — quality below incumbent.\n"
            "Action: ADD COMPETENCY COVERAGE for failing scenarios.  "
            "Preserve length envelope; inflate only where it directly "
            "addresses a failure."
        ),
    }
    action_header = verdict_actions.get(verdict, verdict_actions["refine"])

    return f"""

## Feedback from previous EXECUTION_EVAL (round {latest["feedback_iteration"]})

**Verdict: `{verdict}`** — {action_header}

Aggregate scores:
  candidate pass_rate: {latest["candidate_pass_rate"]:.2f}
  baseline pass_rate:  {latest["baseline_pass_rate"]:.2f}
{floor_line}
  win_rate:            {latest["win_rate"]:.2f}
{cost_block}

Scenarios where the candidate did NOT beat the baseline:
{scenario_lines}
{overflow}

Use these failures to guide this iteration, following the verdict-specific
strategy above.  Held-out scenarios are intentionally not shown — do not
infer or attempt to enumerate them.
"""
