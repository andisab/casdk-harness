"""Tests for the v0→v1 capability-diff helper (Phase A.5 L1.2)."""

from __future__ import annotations

from harness.optimization._orchestrator_helpers import capability_diff


def test_no_baseline_returns_marker():
    out = capability_diff(None, "anything")
    assert "no v0 baseline" in out
    assert "rubric" in out


def test_identical_returns_marker():
    text = "line one\nline two\n"
    out = capability_diff(text, text)
    assert "identical" in out


def test_changed_shows_unified_diff():
    v0 = "use Cluster Autoscaler\nset lowest-price\n"
    v1 = "use Karpenter NodePool\nset price_capacity_optimized\n"
    out = capability_diff(v0, v1, label="skills/aws-eks/SKILL.md")
    # Added + removed lines present.
    assert "+use Karpenter NodePool" in out
    assert "-use Cluster Autoscaler" in out
    # Labels carry into the diff header.
    assert "v0 baseline" in out
    assert "generated candidate" in out
    assert "skills/aws-eks/SKILL.md" in out


def test_truncation_caps_lines_and_marks_elision():
    v0 = "\n".join(f"old-{i}" for i in range(500))
    v1 = "\n".join(f"new-{i}" for i in range(500))
    out = capability_diff(v0, v1, max_lines=50)
    lines = out.splitlines()
    # 50 kept diff lines + 1 truncation marker.
    assert len(lines) == 51
    assert "diff truncated" in lines[-1]


def test_small_diff_not_truncated():
    v0 = "a\nb\nc\n"
    v1 = "a\nB\nc\n"
    out = capability_diff(v0, v1, max_lines=240)
    assert "diff truncated" not in out
    assert "-b" in out and "+B" in out
