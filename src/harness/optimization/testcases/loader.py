"""Test suite loader for YAML and JSON files.

Provides functionality to load test suites from configuration files.

Example usage:
    from harness.optimization.testcases import TestSuiteLoader

    # Load from YAML
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    # Load from JSON
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.json")

    # Load from dict
    suite = TestSuiteLoader.from_dict({
        "name": "test-suite",
        "agent_name": "python-expert",
        "test_cases": [...]
    })
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
import yaml

from harness.optimization.testcases.models import TestSuite

logger = structlog.get_logger(__name__)


class TestSuiteLoaderError(Exception):
    """Error loading test suite."""

    pass


class TestSuiteLoader:
    """Loader for test suite configuration files.

    Supports YAML (.yaml, .yml) and JSON (.json) formats.
    """

    @classmethod
    def load(cls, path: str | Path) -> TestSuite:
        """Load a test suite from a file.

        Args:
            path: Path to the test suite file (YAML or JSON).

        Returns:
            Loaded TestSuite object.

        Raises:
            TestSuiteLoaderError: If file cannot be loaded or parsed.
            FileNotFoundError: If file does not exist.
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Test suite file not found: {path}")

        suffix = path.suffix.lower()

        try:
            if suffix in (".yaml", ".yml"):
                return cls._load_yaml(path)
            elif suffix == ".json":
                return cls._load_json(path)
            else:
                raise TestSuiteLoaderError(
                    f"Unsupported file format: {suffix}. "
                    "Use .yaml, .yml, or .json"
                )
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise TestSuiteLoaderError(f"Failed to parse {path}: {e}") from e
        except (TypeError, KeyError) as e:
            raise TestSuiteLoaderError(
                f"Invalid test suite structure in {path}: {e}"
            ) from e

    @classmethod
    def _load_yaml(cls, path: Path) -> TestSuite:
        """Load test suite from YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            Loaded TestSuite.
        """
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        logger.debug("Loaded test suite from YAML", path=str(path))
        return cls.from_dict(data)

    @classmethod
    def _load_json(cls, path: Path) -> TestSuite:
        """Load test suite from JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            Loaded TestSuite.
        """
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        logger.debug("Loaded test suite from JSON", path=str(path))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestSuite:
        """Create a TestSuite from a dictionary.

        Args:
            data: Dictionary with test suite data.

        Returns:
            TestSuite object.

        Raises:
            TestSuiteLoaderError: If required fields are missing.
        """
        required_fields = ["name", "agent_name", "test_cases"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise TestSuiteLoaderError(
                f"Missing required fields: {', '.join(missing)}"
            )

        if not data["test_cases"]:
            raise TestSuiteLoaderError("Test suite must have at least one test case")

        # Validate test cases have required fields
        for i, tc in enumerate(data["test_cases"]):
            tc_required = ["id", "prompt", "validation"]
            tc_missing = [f for f in tc_required if f not in tc]
            if tc_missing:
                raise TestSuiteLoaderError(
                    f"Test case {i} missing required fields: {', '.join(tc_missing)}"
                )

            # Validate validation config
            validation = tc["validation"]
            if "type" not in validation or "criteria" not in validation:
                raise TestSuiteLoaderError(
                    f"Test case {tc.get('id', i)} validation must have 'type' and 'criteria'"
                )

        return TestSuite(**data)

    @classmethod
    def save(cls, suite: TestSuite, path: str | Path, format: str = "yaml") -> None:
        """Save a test suite to a file.

        Args:
            suite: TestSuite to save.
            path: Output file path.
            format: Output format ("yaml" or "json").

        Raises:
            ValueError: If format is not supported.
        """
        path = Path(path)

        data = cls._to_dict(suite)

        if format == "yaml":
            with path.open("w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        elif format == "json":
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'")

        logger.debug("Saved test suite", path=str(path), format=format)

    @classmethod
    def _to_dict(cls, suite: TestSuite) -> dict[str, Any]:
        """Convert TestSuite to dictionary for serialization.

        Args:
            suite: TestSuite to convert.

        Returns:
            Dictionary representation.
        """
        return {
            "name": suite.name,
            "description": suite.description,
            "agent_name": suite.agent_name,
            "version": suite.version,
            "metadata": suite.metadata,
            "test_cases": [
                {
                    "id": tc.id,
                    "prompt": tc.prompt,
                    "expected_behavior": tc.expected_behavior,
                    "validation": {
                        "type": tc.validation.type.value
                        if hasattr(tc.validation.type, "value")
                        else tc.validation.type,
                        "criteria": tc.validation.criteria,
                        "partial_credit": tc.validation.partial_credit,
                    },
                    "timeout_seconds": tc.timeout_seconds,
                    "tags": tc.tags,
                    "metadata": tc.metadata,
                }
                for tc in suite.test_cases
            ],
        }
