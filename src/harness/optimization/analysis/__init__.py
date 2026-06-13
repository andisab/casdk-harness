"""Analysis module for CGF optimization pipeline.

Provides competency mapping, test subset generation, and synthesis utilities
for intelligent targeted optimization.

Example usage:
    from harness.optimization.analysis import (
        load_eval_criteria,
        map_tests_to_competencies,
        assess_coverage,
        is_quantitative_test,
        create_focused_suite,
        write_temp_suite,
    )

    criteria = load_eval_criteria(Path("workspace/dev-python-expert/research/eval_criteria.yaml"))
    mapping = map_tests_to_competencies(test_suite.test_cases, criteria)
    optimizable = assess_coverage(mapping)

    # Create focused suite for agentic sections
    for section in optimizable:
        if section.strategy == OptimizationStrategy.AGENTIC:
            focused = create_focused_suite_for_section(base_suite, section, mapping, criteria)
            path = write_temp_suite(focused, output_dir)
"""

from harness.optimization.analysis.coherence import (
    CoherenceAnalysis,
    CoherenceIssue,
    DetailLevel,
    IssueSeverity,
    IssueType,
    PromptCoherenceAnalyzer,
    SectionAnalysis,
    analyze_prompt_coherence,
    fix_coherence_issues,
)
from harness.optimization.analysis.competency_mapper import (
    CommonMistake,
    Competency,
    EdgeCase,
    EvalCriteria,
    OptimizableSection,
    OptimizationStrategy,
    PromptSection,
    assess_coverage,
    get_section_tests,
    is_deterministic_test,
    is_llm_judge_test,
    is_quantitative_test,
    load_eval_criteria,
    map_tests_to_competencies,
)
from harness.optimization.analysis.conventions import (
    ConventionsChecker,
    QualityLevel,
    QualitySignal,
    StructureQuality,
    get_conventions_checker,
)
from harness.optimization.analysis.synthesizer import (
    ParsedPrompt,
    PromptSynthesizer,
    SynthesisResult,
    extract_all_sections_from_prompt,
    extract_section_from_prompt,
    merge_optimized_sections,
    replace_section_in_prompt,
    save_optimized_prompt,
)
from harness.optimization.analysis.test_subset import (
    create_focused_suite,
    create_focused_suite_for_competency,
    create_focused_suite_for_section,
    create_section_suites,
    load_focused_suite,
    write_temp_suite,
)

__all__ = [
    # Data models
    "Competency",
    "EdgeCase",
    "CommonMistake",
    "EvalCriteria",
    "OptimizableSection",
    "OptimizationStrategy",
    "PromptSection",
    # Competency mapping
    "load_eval_criteria",
    "map_tests_to_competencies",
    "assess_coverage",
    "is_quantitative_test",
    "is_deterministic_test",
    "is_llm_judge_test",
    "get_section_tests",
    # Test subset generation
    "create_focused_suite",
    "create_focused_suite_for_section",
    "create_focused_suite_for_competency",
    "create_section_suites",
    "write_temp_suite",
    "load_focused_suite",
    # Synthesis
    "ParsedPrompt",
    "SynthesisResult",
    "PromptSynthesizer",
    "merge_optimized_sections",
    "extract_all_sections_from_prompt",
    "extract_section_from_prompt",
    "replace_section_in_prompt",
    "save_optimized_prompt",
    # Coherence analysis
    "CoherenceAnalysis",
    "CoherenceIssue",
    "DetailLevel",
    "IssueType",
    "IssueSeverity",
    "PromptCoherenceAnalyzer",
    "SectionAnalysis",
    "analyze_prompt_coherence",
    "fix_coherence_issues",
    # Conventions checking
    "ConventionsChecker",
    "QualityLevel",
    "QualitySignal",
    "StructureQuality",
    "get_conventions_checker",
]
