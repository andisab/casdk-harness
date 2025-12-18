"""Unit tests for CLI pure functions.

Tests the stateless utility functions in cli.py that don't require
Rich console mocking. More comprehensive UI tests will be added
when additional CLI work is done.
"""

from __future__ import annotations

from harness.cli import format_tool_result, is_json_string


class TestIsJsonString:
    """Tests for is_json_string() function."""

    def test_valid_json_object(self) -> None:
        """Valid JSON object returns True."""
        assert is_json_string('{"key": "value"}') is True

    def test_valid_json_array(self) -> None:
        """Valid JSON array returns True."""
        assert is_json_string('[1, 2, 3]') is True

    def test_valid_json_string(self) -> None:
        """Valid JSON string returns True."""
        assert is_json_string('"hello"') is True

    def test_valid_json_number(self) -> None:
        """Valid JSON number returns True."""
        assert is_json_string("42") is True

    def test_valid_json_boolean(self) -> None:
        """Valid JSON boolean returns True."""
        assert is_json_string("true") is True
        assert is_json_string("false") is True

    def test_valid_json_null(self) -> None:
        """Valid JSON null returns True."""
        assert is_json_string("null") is True

    def test_nested_json_object(self) -> None:
        """Nested JSON object returns True."""
        nested = '{"outer": {"inner": [1, 2, {"deep": true}]}}'
        assert is_json_string(nested) is True

    def test_invalid_json_plain_text(self) -> None:
        """Plain text returns False."""
        assert is_json_string("hello world") is False

    def test_invalid_json_incomplete_object(self) -> None:
        """Incomplete JSON object returns False."""
        assert is_json_string('{"key": "value"') is False

    def test_invalid_json_trailing_comma(self) -> None:
        """JSON with trailing comma returns False."""
        assert is_json_string('{"key": "value",}') is False

    def test_invalid_json_single_quotes(self) -> None:
        """JSON with single quotes returns False."""
        assert is_json_string("{'key': 'value'}") is False

    def test_empty_string(self) -> None:
        """Empty string returns False."""
        assert is_json_string("") is False

    def test_whitespace_only(self) -> None:
        """Whitespace-only string returns False."""
        assert is_json_string("   ") is False

    def test_json_with_whitespace(self) -> None:
        """JSON with leading/trailing whitespace returns True."""
        assert is_json_string('  {"key": "value"}  ') is True


class TestFormatToolResult:
    """Tests for format_tool_result() function."""

    def test_string_plain_text(self) -> None:
        """Plain text string returned as-is."""
        result = format_tool_result("Hello world")
        assert result == "Hello world"

    def test_string_json_formatted(self) -> None:
        """JSON string gets formatted with indentation."""
        result = format_tool_result('{"key":"value"}')
        assert result == '{\n  "key": "value"\n}'

    def test_string_invalid_json(self) -> None:
        """Invalid JSON string returned as-is."""
        result = format_tool_result("not {json}")
        assert result == "not {json}"

    def test_dict_formatted_as_json(self) -> None:
        """Dict is formatted as JSON."""
        result = format_tool_result({"key": "value"})
        assert result == '{\n  "key": "value"\n}'

    def test_list_of_text_blocks(self) -> None:
        """List with text blocks extracts and formats text."""
        content = [{"text": '{"nested": true}'}]
        result = format_tool_result(content)
        assert '"nested": true' in result

    def test_list_of_text_blocks_plain_text(self) -> None:
        """List with plain text blocks returns text as-is."""
        content = [{"text": "plain text here"}]
        result = format_tool_result(content)
        assert result == "plain text here"

    def test_list_of_mixed_content(self) -> None:
        """List with mixed content types."""
        content = [
            {"text": '{"json": true}'},
            {"text": "plain text"},
            {"other_key": "other_value"},
        ]
        result = format_tool_result(content)
        # Should contain formatted JSON, plain text, and dict as JSON
        assert '"json": true' in result
        assert "plain text" in result
        assert '"other_key"' in result

    def test_list_without_text_key(self) -> None:
        """List items without 'text' key formatted as JSON."""
        content = [{"data": 123}, {"items": [1, 2, 3]}]
        result = format_tool_result(content)
        assert '"data": 123' in result
        assert '"items"' in result

    def test_empty_list(self) -> None:
        """Empty list returns empty string."""
        result = format_tool_result([])
        assert result == ""

    def test_number_formatted_as_json(self) -> None:
        """Number is formatted as JSON."""
        result = format_tool_result(42)
        assert result == "42"

    def test_boolean_formatted_as_json(self) -> None:
        """Boolean is formatted as JSON."""
        result = format_tool_result(True)
        assert result == "true"

    def test_none_formatted_as_json(self) -> None:
        """None is formatted as JSON null."""
        result = format_tool_result(None)
        assert result == "null"

    def test_nested_dict(self) -> None:
        """Nested dict is formatted with proper indentation."""
        nested = {"outer": {"inner": {"deep": "value"}}}
        result = format_tool_result(nested)
        assert '"outer"' in result
        assert '"inner"' in result
        assert '"deep"' in result
        # Should have indentation
        assert "  " in result

    def test_multiple_list_items_separated(self) -> None:
        """Multiple list items are separated by double newlines."""
        content = [{"text": "first"}, {"text": "second"}]
        result = format_tool_result(content)
        assert "first" in result
        assert "second" in result
        # Items should be separated
        assert "\n\n" in result

    def test_list_with_json_in_text_field(self) -> None:
        """Text field containing JSON gets parsed and formatted."""
        content = [{"text": '{"status":"success","count":5}'}]
        result = format_tool_result(content)
        # Should be formatted with indentation
        assert '"status": "success"' in result
        assert '"count": 5' in result
