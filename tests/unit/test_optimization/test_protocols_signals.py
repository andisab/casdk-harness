"""Unit tests for the signal protocol module."""

from __future__ import annotations

from harness.optimization.protocols.signals import Signal, SignalParser, SignalType


class TestSignalType:
    """Verify all phase signal types exist and have lowercase string values."""

    def test_research_complete_exists(self) -> None:
        assert SignalType.RESEARCH_COMPLETE.value == "research_complete"

    def test_design_complete_exists(self) -> None:
        assert SignalType.DESIGN_COMPLETE.value == "design_complete"

    def test_generate_complete_exists(self) -> None:
        assert SignalType.GENERATE_COMPLETE.value == "generate_complete"

    def test_eval_design_complete_exists(self) -> None:
        assert SignalType.EVAL_DESIGN_COMPLETE.value == "eval_design_complete"

    def test_iterate_complete_exists(self) -> None:
        assert SignalType.ITERATE_COMPLETE.value == "iterate_complete"

    def test_eval_complete_exists(self) -> None:
        assert SignalType.EVAL_COMPLETE.value == "eval_complete"

    def test_validate_complete_exists(self) -> None:
        assert SignalType.VALIDATE_COMPLETE.value == "validate_complete"

    def test_validate_issues_exists(self) -> None:
        assert SignalType.VALIDATE_ISSUES.value == "validate_issues"

    def test_all_values_are_lowercase_strings(self) -> None:
        for member in SignalType:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()
            assert "_" in member.value or member.value.isalpha()


class TestSignal:
    """Verify Signal dataclass creation with and without resource_path."""

    def test_create_signal_with_resource_path(self) -> None:
        signal = Signal(
            type=SignalType.GENERATE_COMPLETE,
            resource_path="agents/iac-analyzer.md",
            metadata={"resource_type": "agent"},
        )
        assert signal.type == SignalType.GENERATE_COMPLETE
        assert signal.resource_path == "agents/iac-analyzer.md"
        assert signal.metadata == {"resource_type": "agent"}

    def test_create_signal_without_resource_path(self) -> None:
        signal = Signal(
            type=SignalType.RESEARCH_COMPLETE,
            metadata={"eval_criteria_path": "research/eval_criteria.yaml"},
        )
        assert signal.type == SignalType.RESEARCH_COMPLETE
        assert signal.resource_path is None
        assert signal.metadata["eval_criteria_path"] == "research/eval_criteria.yaml"

    def test_create_signal_with_empty_metadata(self) -> None:
        signal = Signal(type=SignalType.VALIDATE_COMPLETE)
        assert signal.type == SignalType.VALIDATE_COMPLETE
        assert signal.resource_path is None
        assert signal.metadata == {}

    def test_signal_metadata_defaults_to_empty_dict(self) -> None:
        signal = Signal(type=SignalType.RESEARCH_COMPLETE)
        assert signal.metadata == {}
        # Ensure each instance gets its own dict (no shared mutable default)
        signal2 = Signal(type=SignalType.RESEARCH_COMPLETE)
        signal.metadata["key"] = "val"
        assert "key" not in signal2.metadata


class TestSignalParser:
    """Test parsing of agent response text into structured Signal objects."""

    def setup_method(self) -> None:
        self.parser = SignalParser()

    def test_parse_research_complete(self) -> None:
        response = (
            "Research phase is done.\n"
            "[RESEARCH_COMPLETE]\n"
            "eval_criteria_path: research/eval_criteria.yaml\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.RESEARCH_COMPLETE
        assert signal.resource_path is None
        assert signal.metadata["eval_criteria_path"] == "research/eval_criteria.yaml"

    def test_parse_generate_complete_with_path(self) -> None:
        response = (
            "Generated the agent definition.\n"
            "[GENERATE_COMPLETE:agents/iac-analyzer.md]\n"
            "resource_type: agent\n"
            "word_count: 1250\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.GENERATE_COMPLETE
        assert signal.resource_path == "agents/iac-analyzer.md"
        assert signal.metadata["resource_type"] == "agent"
        assert signal.metadata["word_count"] == "1250"

    def test_parse_iterate_complete_with_quality_scores(self) -> None:
        response = (
            "Optimization iteration complete.\n"
            "[ITERATE_COMPLETE:agents/iac-analyzer.md]\n"
            "quality_overall: 0.87\n"
            "quality_completeness: 0.90\n"
            "quality_accuracy: 0.85\n"
            "quality_clarity: 0.88\n"
            "word_count: 1340\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.ITERATE_COMPLETE
        assert signal.resource_path == "agents/iac-analyzer.md"
        assert signal.metadata["quality_overall"] == "0.87"
        assert signal.metadata["quality_completeness"] == "0.90"
        assert signal.metadata["quality_accuracy"] == "0.85"
        assert signal.metadata["quality_clarity"] == "0.88"
        assert signal.metadata["word_count"] == "1340"

    def test_parse_validate_issues_with_count(self) -> None:
        response = (
            "Validation found some issues.\n"
            "[VALIDATE_ISSUES:3]\n"
            "issue_1: Missing error handling section\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.VALIDATE_ISSUES
        assert signal.resource_path is None
        assert signal.metadata["issue_count"] == 3
        assert signal.metadata["issue_1"] == "Missing error handling section"

    def test_parse_validate_complete_with_coherence_score(self) -> None:
        response = (
            "All checks passed.\n"
            "[VALIDATE_COMPLETE]\n"
            "coherence_score: 0.92\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.VALIDATE_COMPLETE
        assert signal.resource_path is None
        assert signal.metadata["coherence_score"] == "0.92"

    def test_parse_no_signals_in_plain_text(self) -> None:
        response = (
            "This is just a regular response without any signals.\n"
            "It mentions RESEARCH_COMPLETE in text but not as a signal.\n"
            "No bracketed tags here.\n"
        )
        signals = self.parser.parse(response)
        assert len(signals) == 0

    def test_parse_multiple_signals_in_one_response(self) -> None:
        response = (
            "Generated two resources.\n"
            "[GENERATE_COMPLETE:agents/first.md]\n"
            "resource_type: agent\n"
            "word_count: 500\n"
            "\n"
            "Now the second one.\n"
            "[GENERATE_COMPLETE:skills/helper.md]\n"
            "resource_type: skill\n"
            "word_count: 300\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 2

        assert signals[0].type == SignalType.GENERATE_COMPLETE
        assert signals[0].resource_path == "agents/first.md"
        assert signals[0].metadata["resource_type"] == "agent"
        assert signals[0].metadata["word_count"] == "500"

        assert signals[1].type == SignalType.GENERATE_COMPLETE
        assert signals[1].resource_path == "skills/helper.md"
        assert signals[1].metadata["resource_type"] == "skill"
        assert signals[1].metadata["word_count"] == "300"

    def test_parse_design_complete(self) -> None:
        response = (
            "Resource plan created.\n"
            "[DESIGN_COMPLETE]\n"
            "resource_plan_path: sessions/resource_plan.yaml\n"
            "total_resources: 5\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == SignalType.DESIGN_COMPLETE
        assert signal.resource_path is None
        assert signal.metadata["resource_plan_path"] == "sessions/resource_plan.yaml"
        assert signal.metadata["total_resources"] == "5"

    def test_parse_validate_issues_zero_count(self) -> None:
        response = "[VALIDATE_ISSUES:0]\n"
        signals = self.parser.parse(response)

        assert len(signals) == 1
        assert signals[0].metadata["issue_count"] == 0

    def test_parse_signal_with_no_metadata(self) -> None:
        response = "Done.\n[RESEARCH_COMPLETE]\n"
        signals = self.parser.parse(response)

        assert len(signals) == 1
        assert signals[0].type == SignalType.RESEARCH_COMPLETE
        assert signals[0].metadata == {}

    def test_parse_metadata_stops_at_next_signal(self) -> None:
        """Metadata lines between two signals should be attributed correctly."""
        response = (
            "[RESEARCH_COMPLETE]\n"
            "eval_criteria_path: research/eval_criteria.yaml\n"
            "[VALIDATE_COMPLETE]\n"
            "coherence_score: 0.95\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 2
        assert signals[0].type == SignalType.RESEARCH_COMPLETE
        assert signals[0].metadata["eval_criteria_path"] == "research/eval_criteria.yaml"
        assert "coherence_score" not in signals[0].metadata

        assert signals[1].type == SignalType.VALIDATE_COMPLETE
        assert signals[1].metadata["coherence_score"] == "0.95"

    def test_parse_metadata_with_leading_whitespace(self) -> None:
        response = (
            "[GENERATE_COMPLETE:agents/test.md]\n"
            "  resource_type: agent\n"
            "  word_count: 800\n"
        )
        signals = self.parser.parse(response)

        assert len(signals) == 1
        assert signals[0].metadata["resource_type"] == "agent"
        assert signals[0].metadata["word_count"] == "800"

    def test_parse_signal_wrapped_in_inline_code_backticks(self) -> None:
        """Agents that wrap the signal in inline-code (`[...]`) should still
        be detected. Observed in cgf-eval-architect output during the
        2026-05-11 smoke-fixture run."""
        response = "`[EVAL_DESIGN_COMPLETE]`\n"
        signals = self.parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.EVAL_DESIGN_COMPLETE

    def test_parse_signal_wrapped_in_bold_markdown(self) -> None:
        """Agents that bold the signal with **[...]**."""
        response = "**[VALIDATE_COMPLETE]**\n"
        signals = self.parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.VALIDATE_COMPLETE

    def test_parse_signal_with_argument_in_backticks(self) -> None:
        """Path-carrying signals still parse when backtick-wrapped."""
        response = "`[GENERATE_COMPLETE:agents/foo.md]`\n"
        signals = self.parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.GENERATE_COMPLETE
        assert signals[0].resource_path == "agents/foo.md"

    def test_parse_signal_with_leading_indentation(self) -> None:
        """Indented signals (4-space code block style) still parse."""
        response = "    [RESEARCH_COMPLETE]\n"
        signals = self.parser.parse(response)
        assert len(signals) == 1
        assert signals[0].type == SignalType.RESEARCH_COMPLETE

    def test_parse_rejects_signal_with_trailing_content(self) -> None:
        """Signals that share a line with prose are NOT detected — the
        metadata-collection model relies on signals being on their own line."""
        response = "I will emit [RESEARCH_COMPLETE] when done.\n"
        signals = self.parser.parse(response)
        assert signals == []
